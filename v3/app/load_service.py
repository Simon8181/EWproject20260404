"""Read-only queries against v2 `load` for tab lists (aligned with v2 Debug)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

TAB_KEYS = ("quote", "order", "complete", "cancel")

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 200
# 匹配行过多时暂不逐页排序（占内存）；请用 data_source 等缩小范围
ROWS_SORT_SCAN_MAX = 80_000

_LOAD_ROW_SELECT = """
            quote_no, status, is_trouble_case, customer_name, commodity_desc,
                   note_d_raw, note_e_raw, note_f_raw,
                   broker, actual_driver_rate_raw, carriers,
                   ship_from_raw, consignee_contact, shipper_info, consignee_info,
                   ship_to_raw, weight_raw, dimension_raw, volume_raw,
                   distance_miles, origin_land_use, dest_land_use, validate_ok,
                   validate_error,
                   used_ai_retry, ai_confidence, origin_normalized, dest_normalized,
                   customer_quote_raw, driver_rate_raw,
                   pickup_eta, delivery_eta, pickup_tz, delivery_tz,
                   cargo_ready, carrier_note, operator_updated_by, operator_updated_at,
                   source_tabs, data_source, updated_at,
                   v3_sheet_ai_enriched_at
""".strip()


def _order_load_state_status_filter(
    load_state: str | None,
) -> tuple[str, tuple[str, ...]] | None:
    v = (load_state or "").strip().lower()
    if v in ("", "all"):
        return None
    if v == "waiting":
        return ("status = ?", ("ordered",))
    if v == "found":
        return ("status = ?", ("carrier_assigned",))
    if v == "transit":
        return ("status = ?", ("picked",))
    return None


def normalize_order_load_state(load_state: str | None) -> str | None:
    v = (load_state or "").strip().lower()
    return v if v in ("waiting", "found", "transit") else None


def order_tab_ui_state(load_state: str | None) -> tuple[str, str | None]:
    """Returns (all|waiting|found|transit, filter arg for SQL or None)."""
    if (load_state or "").strip().lower() in ("waiting", "found", "transit"):
        v = (load_state or "").strip().lower()
        return v, normalize_order_load_state(load_state)
    return "all", None


def ew_number_desc_sort_key(quote_no: str | None) -> tuple[int, str]:
    """
    用于列表排序：EW 号末尾数字越大越靠前（如 ew18380 在 ew17700 之上）。
    无末尾数字时退化为字符串 casefold。
    """
    s = (quote_no or "").strip()
    m = re.search(r"(\d+)$", s, re.IGNORECASE)
    num = int(m.group(1)) if m else -1
    return (-num, s.casefold())


def _tab_rows_filter_sql(
    tab_key: str,
    load_state: str | None,
    data_source: str | None,
) -> tuple[str, list[Any]]:
    extra_where = ""
    params: list[Any] = [tab_key]
    if tab_key == "order":
        filt = _order_load_state_status_filter(load_state)
        if filt:
            frag, frag_params = filt
            extra_where = f" AND {frag}"
            params.extend(list(frag_params))
    ds = (data_source or "").strip()
    if ds:
        extra_where += " AND TRIM(COALESCE(data_source, '')) = ?"
        params.append(ds)
    return extra_where, params


def open_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri()
    conn = sqlite3.connect(f"{uri}?mode=ro", uri=True, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_tab_rows(
    db_path: Path,
    tab_key: str,
    *,
    offset: int = 0,
    limit: int = PAGE_SIZE_DEFAULT,
    load_state: str | None = None,
    data_source: str | None = None,
) -> tuple[list[dict[str, Any]], int, str | None]:
    """
    按 source_tabs 匹配 tab_key，按 EW 尾号降序分页取 load。
    Returns (rows, total_count, error_code)。
    """
    if tab_key not in TAB_KEYS:
        return [], 0, "invalid_tab"
    if limit < 1 or limit > PAGE_SIZE_MAX:
        return [], 0, "invalid_limit"
    if offset < 0:
        return [], 0, "invalid_offset"
    if not db_path.is_file():
        return [], 0, "db_missing"
    conn: sqlite3.Connection | None = None
    try:
        conn = open_readonly(db_path)
        extra_where, params = _tab_rows_filter_sql(tab_key, load_state, data_source)
        id_rows = conn.execute(
            f"""
            SELECT rowid AS __rid, quote_no
            FROM load
            WHERE instr(',' || source_tabs || ',', ',' || ? || ',') > 0
            {extra_where}
            """,
            tuple(params),
        ).fetchall()
        n_match = len(id_rows)
        if n_match > ROWS_SORT_SCAN_MAX:
            return [], n_match, "too_many_rows"
        sorted_rids: list[int] = [
            int(r["__rid"])
            for r in sorted(
                id_rows,
                key=lambda row: ew_number_desc_sort_key(str(row["quote_no"] or "")),
            )
        ]
        total = len(sorted_rids)
        page_rids = sorted_rids[offset : offset + limit]
        if not page_rids:
            return [], total, None
        placeholders = ",".join("?" * len(page_rids))
        qparams: list[Any] = list(page_rids)
        rows = conn.execute(
            f"""
            SELECT rowid AS __rid, {_LOAD_ROW_SELECT}
            FROM load
            WHERE rowid IN ({placeholders})
            """,
            tuple(qparams),
        ).fetchall()
        by_rid = {int(dict(r)["__rid"]): dict(r) for r in rows}
        ordered: list[dict[str, Any]] = []
        for rid in page_rids:
            d = by_rid.get(rid)
            if not d:
                continue
            d = {k: v for k, v in d.items() if k != "__rid"}
            ordered.append(d)
        return ordered, total, None
    except sqlite3.Error:
        return [], 0, "query_failed"
    finally:
        if conn is not None:
            conn.close()
