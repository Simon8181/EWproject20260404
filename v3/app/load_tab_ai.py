"""Tab 列表页：当前页尚未 Sheet 行 AI 格式化的 load，多线程 Gemini 写回（轻量：只拉表头 + 用 DB 反推 A–U cells）。"""

from __future__ import annotations

import copy
from typing import Any

from app.settings import get_settings
from app.sheet_refresh import fetch_tab_header_row_only, load_ai_sheet_rules
from app.sheet_row_ai import AiEnrichRunStats, v3_sheet_row_ai_enabled
from app.sheet_sync import (
    _get_v2_db,
    _preview_to_import_item,
    _sheet_row_ai_partition_merge_and_enrich,
    sheet_import_data_source,
)


def _synthetic_sheet_cells_from_db_row(row: dict[str, Any]) -> dict[str, str]:
    """与 _letters_to_row_dict / _load_preview 互逆，用库存字段拼 A–U（仅前 21 列）。"""
    qn = str(row.get("quote_no") or "").strip()
    return {
        "A": "",
        "B": str(row.get("customer_name") or "").strip(),
        "C": qn,
        "D": str(row.get("note_d_raw") or "").strip(),
        "E": str(row.get("note_e_raw") or "").strip(),
        "F": str(row.get("note_f_raw") or "").strip(),
        "G": str(row.get("pieces_raw") or "").strip(),
        "H": str(row.get("commodity_desc") or "").strip(),
        "I": str(row.get("ship_from_raw") or "").strip(),
        "J": str(row.get("consignee_contact") or "").strip(),
        "K": str(row.get("ship_to_raw") or "").strip(),
        "L": str(row.get("weight_raw") or "").strip(),
        "M": str(row.get("dimension_raw") or "").strip(),
        "N": str(row.get("volume_raw") or "").strip(),
        "O": str(row.get("cargo_value_raw") or "").strip(),
        "P": str(row.get("customer_quote_raw") or "").strip(),
        "Q": "",
        "R": "",
        "S": "",
        "T": "",
        "U": str(row.get("driver_rate_raw") or "").strip(),
    }


def ensure_tab_page_row_ai_enrich(
    *,
    tab_key: str,
    page_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    对 page_rows 中 v3_sheet_ai_enriched_at 为空且 data_source 与当前规则一致的行：
    只请求 Google Sheet **表头一行**；格内上下文用 **数据库当前列** 反推 A–U，再按 merge 同款多线程 enrich 写库。
    （旧实现整表 refresh_sheet，quote 表极慢；现已避免。）
    """
    out: dict[str, Any] = {
        "ensure_ai_ran": False,
        "ensure_ai_skipped": None,
        "ensure_ai_refetch": False,
        "ensure_ai_api_quote_nos": [],
        "ensure_ai_sheet_note": None,
        "ensure_ai_errors": [],
        "ensure_ai_sheet_mode": "header_only_db_cells",
    }
    if not page_rows:
        out["ensure_ai_skipped"] = "empty_page"
        return out
    if not v3_sheet_row_ai_enabled():
        out["ensure_ai_skipped"] = "ai_disabled"
        return out

    rules = load_ai_sheet_rules()
    ds_rules = str(sheet_import_data_source(rules) or "").strip()
    rows_to_enrich: list[dict[str, Any]] = []
    for r in page_rows:
        if str(r.get("v3_sheet_ai_enriched_at") or "").strip():
            continue
        qn = str(r.get("quote_no") or "").strip()
        if not qn:
            continue
        ds_row = str(r.get("data_source") or "").strip()
        if ds_rules and ds_row != ds_rules:
            continue
        rows_to_enrich.append(r)
    if not rows_to_enrich:
        out["ensure_ai_skipped"] = "all_have_ai_or_mismatch_ds"
        return out

    try:
        header_row = fetch_tab_header_row_only(tab_key=tab_key)
    except (FileNotFoundError, ValueError, OSError) as e:
        out["ensure_ai_errors"] = [str(e)]
        return out

    ai_jobs: list[tuple[dict[str, Any], list[Any], str, dict[str, str]]] = []
    merged: list[dict[str, Any]] = []
    hdr = list(header_row)
    for r in rows_to_enrich:
        load = copy.deepcopy(dict(r))
        cells = _synthetic_sheet_cells_from_db_row(r)
        ai_jobs.append((load, hdr, tab_key, cells))
        merged.append(load)

    ai_stats = AiEnrichRunStats()
    api_enriched = _sheet_row_ai_partition_merge_and_enrich(
        ai_jobs,
        merged,
        rules,
        ai_stats=ai_stats,
        ai_overwrite=False,
        progress=None,
    )

    v2db = _get_v2_db()
    path = get_settings().db_path
    conn = v2db.open_db(path)
    v2db.ensure_schema(conn)
    now = v2db.now_iso()
    written = 0
    try:
        with conn:
            for ld in merged:
                qn = str(ld.get("quote_no") or "").strip()
                if not qn or qn not in api_enriched:
                    continue
                item = _preview_to_import_item(ld, rules)
                patch = item.get("_v3_ai_patch")
                patch_d = dict(patch) if isinstance(patch, dict) else {}
                v2db.patch_load_v3_sheet_ai_columns(conn, qn, patch_d, now=now)
                written += 1
    finally:
        conn.close()

    out["ensure_ai_ran"] = True
    out["ensure_ai_refetch"] = written > 0
    out["ensure_ai_api_quote_nos"] = sorted(api_enriched)
    out["ensure_ai_errors"] = list((ai_stats.errors or [])[:20])
    out["ensure_ai_calls"] = ai_stats.calls
    out["ensure_ai_failures"] = ai_stats.failures
    out["ensure_ai_skipped_db"] = ai_stats.skipped_db
    return out
