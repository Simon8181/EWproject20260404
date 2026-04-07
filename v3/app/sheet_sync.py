"""前四个 Sheet tab：拉取、四表合并规则、load 预览；可选 apply=true 写入 v2 SQLite。"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.settings import get_settings
from app.sheet_refresh import (
    _quote_extend_fetch_enabled,
    load_ai_sheet_rules,
    refresh_sheet,
    sheet_first_data_row_1based,
    tab_first_data_row_1based,
)
from app.sheet_row_ai import (
    AiEnrichRunStats,
    ai_batch_max_rows,
    ai_parallel_batch_workers,
    apply_ai_delta_to_load,
    build_ai_allowlist,
    build_enrich_prompt,
    build_payload_rows_from_jobs,
    enrich_generation_config,
    enrich_loads_batches_parallel,
    run_enrich_generate,
    sanitize_enrich_delta,
    v3_sheet_row_ai_enabled,
)

router = APIRouter(prefix="/api/core", tags=["core"])

_LONG_TASK_LOCK = threading.Lock()
LONG_TASK_PROGRESS: dict[str, Any] = {}


def _long_task_progress_begin(ai: bool) -> dict[str, Any] | None:
    """ai=false 时不追踪；否则重置并返回与 LONG_TASK_PROGRESS 同一对象供就地更新。"""
    if not ai:
        return None
    with _LONG_TASK_LOCK:
        LONG_TASK_PROGRESS.clear()
        LONG_TASK_PROGRESS.update(
            {
                "active": True,
                "phase": "sheet",
                "merge_rows": 0,
                "merge_total": None,
                "ai_done": 0,
                "ai_total": 0,
                "ai_formatting_ews": [],
                "ai_formatting_ews_more": 0,
            }
        )
    return LONG_TASK_PROGRESS


def _long_task_progress_finish() -> None:
    with _LONG_TASK_LOCK:
        LONG_TASK_PROGRESS["active"] = False
        LONG_TASK_PROGRESS["phase"] = "done"
        LONG_TASK_PROGRESS["ai_formatting_ews"] = []
        LONG_TASK_PROGRESS["ai_formatting_ews_more"] = 0
        LONG_TASK_PROGRESS["merge_rows"] = 0
        LONG_TASK_PROGRESS["merge_total"] = None
        LONG_TASK_PROGRESS["ai_done"] = 0
        LONG_TASK_PROGRESS["ai_total"] = 0


def long_task_progress_snapshot() -> dict[str, Any]:
    with _LONG_TASK_LOCK:
        out = dict(LONG_TASK_PROGRESS)
        ews = out.get("ai_formatting_ews")
        if isinstance(ews, list):
            out["ai_formatting_ews"] = list(ews)
        return out

_TAB_DEFAULT_STATUS: dict[str, str] = {
    "quote": "pending_quote",
    "order": "ordered",
    "complete": "complete",
    "cancel": "cancel",
}

_MERGE_STAGE_ORDER = ("cancel", "complete", "order", "quote")
_STATUS_QUOTE_NO_CUSTOMER_RESPONSE = "quote_no_customer_response"


def sheet_import_data_source(rules: dict[str, Any]) -> str:
    """与当前 ai_sheet_rules 中 Sheet 链路对应的数据来源标识（写入 load.data_source）。"""
    return str((rules.get("sheet") or {}).get("data_source") or "").strip()


def _quote_column_a_stale_cancel_days(rules: dict[str, Any]) -> int:
    """sheet.quote_column_a_stale_cancel_days：A 列日期早于今天超过此天数则将 quote 行 status 置为 cancel；0 关闭。"""
    v = (rules.get("sheet") or {}).get("quote_column_a_stale_cancel_days")
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    return max(0, min(n, 3650))


def _parse_quote_sheet_column_a_date(raw: str) -> date | None:
    """解析报价表 A 列常见日期字符串（本地日）；无法解析则 None。"""
    s = (raw or "").strip()
    if not s:
        return None
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        try:
            serial = float(s)
        except ValueError:
            return None
        if 20000 <= serial <= 80000:
            base = date(1899, 12, 30)
            try:
                return base + timedelta(days=int(round(serial)))
            except (OverflowError, ValueError):
                return None
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")[:10]).date()
    except ValueError:
        pass
    return None


def _apply_quote_stale_cancel_by_column_a(
    load: dict[str, Any],
    cells: dict[str, str],
    rules: dict[str, Any],
) -> bool:
    """
    quote 表：若 A 列日期早于今天超过配置天数，status → cancel。
    返回是否被置为 cancel。
    """
    thr = _quote_column_a_stale_cancel_days(rules)
    if thr <= 0:
        return False
    d = _parse_quote_sheet_column_a_date(cells.get("A", ""))
    if d is None:
        return False
    if (date.today() - d).days > thr:
        load["status"] = "cancel"
        return True
    return False


_v2_db_mod: Any = None
_v2_note_mod: Any = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_v2_submodule(module_basename: str) -> Any:
    path = _repo_root() / "v2" / "app" / f"{module_basename}.py"
    name = "ew_v2__" + module_basename.replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 v2 模块: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_v2_db() -> Any:
    global _v2_db_mod
    if _v2_db_mod is None:
        _v2_db_mod = _load_v2_submodule("db")
    return _v2_db_mod


def _get_v2_note_def_extract() -> Any:
    global _v2_note_mod
    if _v2_note_mod is None:
        _v2_note_mod = _load_v2_submodule("note_def_extract")
    return _v2_note_mod


def _col(row: list[str], idx: int) -> str:
    if idx < 0 or idx >= len(row):
        return ""
    return ("" if row[idx] is None else str(row[idx])).strip()


def _letters_to_row_dict(row: list[str]) -> dict[str, str]:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:21]
    return {ch: _col(row, i) for i, ch in enumerate(letters)}


def _ew_id_from_row(row: list[str]) -> str:
    return _col(row, 2)


def _quote_no_fold_key(qn: str) -> str:
    """合并去重用：避免 quote 与 order 等 tab 仅大小写不一致时重复计入 remainder。"""
    return (qn or "").strip().casefold()


def _row_has_column_b_data(row: list[Any]) -> bool:
    """B 列为必填业务字段：无内容则整行不参与合并/预览写库（不合规）。"""
    return isinstance(row, list) and bool(_col(row, 1))


def _col_p_customer_quote(row: list[Any]) -> str:
    """P 列：给客人报价。"""
    return _col(row, ord("P") - ord("A"))


def _apply_quoted_when_p_non_empty(
    remainder_rows: list[list[Any]], statuses: list[str]
) -> None:
    """P 列有给客价则记为 quoted（不算待报价），覆盖 B 尾比例结果。"""
    for i, row in enumerate(remainder_rows):
        if not isinstance(row, list):
            continue
        if _col_p_customer_quote(row):
            statuses[i] = "quoted"


def _quote_tab_extend_fetch_applied(tab: dict[str, Any], rules: dict[str, Any]) -> bool:
    if str(tab.get("key", "")).strip() != "quote":
        return False
    sheet_cfg = rules.get("sheet") or {}
    return _quote_extend_fetch_enabled(sheet_cfg)


def _sheet_quote_b_tail_percent(rules: dict[str, Any]) -> int:
    sheet_cfg = rules.get("sheet") or {}
    v = sheet_cfg.get("quote_b_column_tail_percent")
    if v is None:
        return 0
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    if n <= 0 or n > 100:
        return 0
    return n


def _slice_quote_rows_by_b_tail(
    rows_raw: list[Any],
    percent: int,
    *,
    first_data_row_1based: int = 2,
    max_rows_request: int | None = None,
    quote_extend_fetch_applied: bool = False,
    quote_fetch_capped: bool = False,
    quote_extend_fetch_max_total_rows: int | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """
    在「自第一行数据到 B 列最后有值的行」这一段内，只保留末尾 percent% 的行（向上取整，至少 1 行）。
    """
    if percent <= 0:
        return list(rows_raw), {"applied": False}
    last_b = -1
    for i, row in enumerate(rows_raw):
        if not isinstance(row, list):
            continue
        if _col(row, 1):
            last_b = i
    if last_b < 0:
        return list(rows_raw), {"applied": False, "reason": "no_column_b_data"}
    span = last_b + 1
    k = max(1, math.ceil(span * percent / 100.0))
    start = span - k
    sliced = rows_raw[start : last_b + 1]
    last_row = rows_raw[last_b]
    last_b_ew_id = _ew_id_from_row(last_row) if isinstance(last_row, list) else ""
    last_b_column_b = _col(last_row, 1) if isinstance(last_row, list) else ""
    last_b_sheet_row_1based = last_b + int(first_data_row_1based)
    nraw = len(rows_raw)
    meta = {
        "applied": True,
        "tail_percent": percent,
        "first_data_row_1based": int(first_data_row_1based),
        "last_b_data_row_index": last_b,
        "last_b_sheet_row_1based": last_b_sheet_row_1based,
        "last_b_ew_id": last_b_ew_id,
        "last_b_column_b": last_b_column_b,
        "span_row_count": span,
        "kept_row_count": len(sliced),
        "first_kept_row_index": start,
        "rows_fetched_in_batch": nraw,
    }
    if quote_extend_fetch_applied:
        if quote_fetch_capped:
            meta["last_b_may_be_truncated_by_quote_cap"] = True
            if quote_extend_fetch_max_total_rows is not None:
                meta["quote_extend_fetch_max_total_rows"] = int(
                    quote_extend_fetch_max_total_rows
                )
    elif (
        max_rows_request
        and nraw >= int(max_rows_request)
        and last_b == nraw - 1
    ):
        meta["last_b_may_be_truncated_by_max_rows"] = True
        meta["max_rows_request"] = int(max_rows_request)
    return sliced, meta


def _quote_tab_last_b_scan(
    rows_raw: list[list[Any]],
    *,
    first_data_row_1based: int,
    max_rows_request: int | None = None,
    quote_extend_fetch_applied: bool = False,
    quote_fetch_capped: bool = False,
    quote_extend_fetch_max_total_rows: int | None = None,
) -> dict[str, Any]:
    """
    在整张 quote 表本批行列表上找 B 列最后非空（不按 cancel/complete/order 过滤）。
    用于与 quote remainder 上的 B 尾计算区分展示。
    """
    last_b = -1
    for i, row in enumerate(rows_raw):
        if not isinstance(row, list):
            continue
        if _col(row, 1):
            last_b = i
    if last_b < 0:
        return {
            "applied": False,
            "reason": "no_column_b_data",
            "scope": "quote_tab_full_batch",
        }
    last_row = rows_raw[last_b]
    nraw = len(rows_raw)
    meta: dict[str, Any] = {
        "applied": True,
        "scope": "quote_tab_full_batch",
        "first_data_row_1based": int(first_data_row_1based),
        "last_b_data_row_index": last_b,
        "last_b_sheet_row_1based": last_b + int(first_data_row_1based),
        "last_b_ew_id": _ew_id_from_row(last_row) if isinstance(last_row, list) else "",
        "last_b_column_b": _col(last_row, 1) if isinstance(last_row, list) else "",
        "rows_fetched_in_batch": nraw,
    }
    if quote_extend_fetch_applied:
        if quote_fetch_capped:
            meta["last_b_may_be_truncated_by_quote_cap"] = True
            if quote_extend_fetch_max_total_rows is not None:
                meta["quote_extend_fetch_max_total_rows"] = int(
                    quote_extend_fetch_max_total_rows
                )
    elif (
        max_rows_request
        and nraw >= int(max_rows_request)
        and last_b == nraw - 1
    ):
        meta["last_b_may_be_truncated_by_max_rows"] = True
        meta["max_rows_request"] = int(max_rows_request)
    return meta


def _assign_quote_remainder_statuses(
    remainder_rows: list[list[Any]],
    percent: int,
    *,
    quote_row_indices_in_tab: list[int] | None = None,
    first_data_row_1based: int = 2,
    quote_tab_total_rows_fetched: int | None = None,
    max_rows_request: int | None = None,
    quote_extend_fetch_applied: bool = False,
    quote_fetch_capped: bool = False,
    quote_extend_fetch_max_total_rows: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """
    与四表合并一致：进入 remainder 的行已保证 B 列有数据（否则在合并层整行丢弃）。
    仅在 remainder 上计算 B 列 span：底部 percent% 为 pending_quote，上部与 B 空尾行为 quote_no_customer_response。
    percent<=0 时先全标 pending_quote，再由 P 列非空改为 quoted。
    remainder 为空返回 empty_remainder；若竟无 B（不应发生）则 no_column_b_data。

    quote_row_indices_in_tab: 与 remainder 每行对应的「quote 表 rows_raw 内下标」。
    first_data_row_1based: rows_raw[0] 对应的工作表行号（与 sheet_refresh 一致）。
    """
    n = len(remainder_rows)
    if n == 0:
        return [], {"applied": False, "reason": "empty_remainder"}
    if percent <= 0:
        st0 = ["pending_quote"] * n
        _apply_quoted_when_p_non_empty(remainder_rows, st0)
        return st0, {"applied": False, "reason": "tail_percent_disabled_or_empty"}

    last_b = -1
    for i, row in enumerate(remainder_rows):
        if isinstance(row, list) and _col(row, 1):
            last_b = i
    if last_b < 0:
        st0 = [_STATUS_QUOTE_NO_CUSTOMER_RESPONSE] * n
        _apply_quoted_when_p_non_empty(remainder_rows, st0)
        return st0, {"applied": False, "reason": "no_column_b_data"}

    span_len = last_b + 1
    k = max(1, math.ceil(span_len * percent / 100.0))
    start = span_len - k
    statuses: list[str] = []
    for i in range(n):
        if i <= last_b:
            statuses.append("pending_quote" if i >= start else _STATUS_QUOTE_NO_CUSTOMER_RESPONSE)
        else:
            statuses.append(_STATUS_QUOTE_NO_CUSTOMER_RESPONSE)
    _apply_quoted_when_p_non_empty(remainder_rows, statuses)
    last_row = remainder_rows[last_b]
    last_b_ew_id = _ew_id_from_row(last_row) if isinstance(last_row, list) else ""
    last_b_column_b = _col(last_row, 1) if isinstance(last_row, list) else ""
    meta = {
        "applied": True,
        "scope": "quote_remainder",
        "tail_percent": percent,
        "last_b_data_row_index": last_b,
        "last_b_ew_id": last_b_ew_id,
        "last_b_column_b": last_b_column_b,
        "span_row_count": span_len,
        "pending_quote_row_count": sum(1 for s in statuses if s == "pending_quote"),
        "quoted_p_row_count": sum(1 for s in statuses if s == "quoted"),
        "quote_no_customer_response_row_count": sum(
            1 for s in statuses if s == _STATUS_QUOTE_NO_CUSTOMER_RESPONSE
        ),
        "first_pending_quote_row_index_in_remainder": start,
    }
    if (
        quote_row_indices_in_tab is not None
        and len(quote_row_indices_in_tab) == n
        and last_b >= 0
    ):
        tab_i = quote_row_indices_in_tab[last_b]
        meta["last_b_quote_tab_row_index_0based"] = tab_i
        meta["first_data_row_1based"] = int(first_data_row_1based)
        meta["last_b_sheet_row_1based"] = tab_i + int(first_data_row_1based)
        if quote_extend_fetch_applied:
            if quote_fetch_capped:
                meta["last_b_may_be_truncated_by_quote_cap"] = True
                if quote_extend_fetch_max_total_rows is not None:
                    meta["quote_extend_fetch_max_total_rows"] = int(
                        quote_extend_fetch_max_total_rows
                    )
            if quote_tab_total_rows_fetched is not None:
                meta["quote_tab_rows_fetched"] = int(quote_tab_total_rows_fetched)
        elif (
            max_rows_request
            and quote_tab_total_rows_fetched is not None
            and quote_tab_total_rows_fetched >= int(max_rows_request)
            and tab_i == quote_tab_total_rows_fetched - 1
        ):
            meta["last_b_may_be_truncated_by_max_rows"] = True
            meta["max_rows_request"] = int(max_rows_request)
            meta["quote_tab_rows_fetched"] = int(quote_tab_total_rows_fetched)
    return statuses, meta


def _load_preview(*, tab_key: str, cells: dict[str, str], quote_no: str) -> dict[str, Any]:
    """与将写入 `load` 的列一致（不含时间戳；broker/carriers 仍为空，合并写库前会 parse_def_notes）。"""
    status = _TAB_DEFAULT_STATUS.get(tab_key, "pending_quote")
    return {
        "quote_no": quote_no,
        "status": status,
        "is_trouble_case": 0,
        "customer_name": cells.get("B", ""),
        "note_d_raw": cells.get("D", ""),
        "note_e_raw": cells.get("E", ""),
        "note_f_raw": cells.get("F", ""),
        "broker": "",
        "actual_driver_rate_raw": "",
        "carriers": "",
        "pieces_raw": cells.get("G", ""),
        "commodity_desc": cells.get("H", ""),
        "ship_from_raw": cells.get("I", ""),
        "consignee_contact": cells.get("J", ""),
        "ship_to_raw": cells.get("K", ""),
        "weight_raw": cells.get("L", ""),
        "dimension_raw": cells.get("M", ""),
        "volume_raw": cells.get("N", ""),
        "cargo_value_raw": cells.get("O", ""),
        "customer_quote_raw": cells.get("P", ""),
        "driver_rate_raw": cells.get("U", ""),
        "source_tabs": tab_key,
    }


def _preview_to_import_item(load: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    """与 v2 sheet_import upsert 使用的 item 字典形状一致；另附 _v3_ai_patch 供写回 AI 列与时间戳。"""
    st = str(load.get("source_tabs", "quote"))
    allow = build_ai_allowlist(rules)
    ai_patch: dict[str, Any] = {}
    for k in allow:
        if k not in load:
            continue
        v = load.get(k)
        if v is None:
            continue
        if isinstance(v, bool):
            if v:
                ai_patch[k] = 1
            continue
        if isinstance(v, (int, float)):
            ai_patch[k] = v
            continue
        sv = str(v).strip()
        if sv:
            ai_patch[k] = sv
    base: dict[str, Any] = {
        "quote_no": load["quote_no"],
        "status": load["status"],
        "is_trouble_case": bool(load.get("is_trouble_case")),
        "customer_name": load.get("customer_name", ""),
        "note_d_raw": load.get("note_d_raw", ""),
        "note_e_raw": load.get("note_e_raw", ""),
        "note_f_raw": load.get("note_f_raw", ""),
        "broker": load.get("broker", ""),
        "actual_driver_rate_raw": load.get("actual_driver_rate_raw", ""),
        "carriers": load.get("carriers", ""),
        "pieces_raw": load.get("pieces_raw", ""),
        "commodity_desc": load.get("commodity_desc", ""),
        "ship_from_raw": load.get("ship_from_raw", ""),
        "consignee_contact": load.get("consignee_contact", ""),
        "ship_to_raw": load.get("ship_to_raw", ""),
        "weight_raw": load.get("weight_raw", ""),
        "dimension_raw": load.get("dimension_raw", ""),
        "volume_raw": load.get("volume_raw", ""),
        "cargo_value_raw": load.get("cargo_value_raw", ""),
        "customer_quote_raw": load.get("customer_quote_raw", ""),
        "driver_rate_raw": load.get("driver_rate_raw", ""),
        "source_tabs": st,
    }
    if ai_patch:
        base["_v3_ai_patch"] = ai_patch
    return base


def _apply_def_notes_to_item(item: dict[str, Any]) -> None:
    note = _get_v2_note_def_extract()
    p = note.parse_def_notes(
        str(item.get("note_d_raw", "")),
        str(item.get("note_e_raw", "")),
        str(item.get("note_f_raw", "")),
    )
    item["broker"] = p["broker"]
    item["actual_driver_rate_raw"] = p["actual_driver_rate_raw"]
    item["carriers"] = p["carriers"]


def _debug_find_sheet_row_for_ew(
    tabs_by_key: dict[str, dict[str, Any]],
    ew: str,
) -> tuple[str, list[Any], dict[str, Any]] | None:
    """按 cancel→complete→order→quote 顺序找首个合规行；C 列与 ew 匹配（大小写不敏感 folding）。"""
    fk = _quote_no_fold_key(ew)
    if not fk:
        return None
    for stage in _MERGE_STAGE_ORDER:
        tab = tabs_by_key.get(stage) or {}
        for row in tab.get("rows") or []:
            if not isinstance(row, list):
                continue
            if not _row_has_column_b_data(row):
                continue
            qn = _ew_id_from_row(row)
            if _quote_no_fold_key(qn) != fk:
                continue
            return stage, row, tab
    return None


def _rows_raw_lists(tab: dict[str, Any]) -> list[list[Any]]:
    out: list[list[Any]] = []
    for row in tab.get("rows") or []:
        if isinstance(row, list):
            out.append(row)
    return out


def _build_merge_validation(
    stats: dict[str, int],
    quote_tab_last_b_full: dict[str, Any],
    quote_remainder_b_tail: dict[str, Any],
) -> dict[str, Any]:
    """合并路径上的行级合法性统计（与 ai_sheet_rules 中 B/C 列约定一致）。"""
    sk = stats
    breakdown_keys = (
        "skipped_non_list_row",
        "skipped_non_compliant_no_column_b",
        "skipped_non_compliant_no_ew_id",
        "skipped_ew_in_earlier_stage",
        "skipped_duplicate_ew_same_tab",
    )
    skipped_breakdown = {k: int(sk.get(k, 0)) for k in breakdown_keys}
    total_skip = sum(skipped_breakdown.values())
    fetch_notes: list[str] = []
    if quote_tab_last_b_full.get("last_b_may_be_truncated_by_quote_cap"):
        fetch_notes.append(
            "quote 表可能未拉全（连续拉取达 yaml 上限且末行 B 仍非空）"
        )
    if quote_tab_last_b_full.get("last_b_may_be_truncated_by_max_rows"):
        fetch_notes.append("quote 表可能未拉全（本批 max_rows 截断）")
    if quote_remainder_b_tail.get("last_b_may_be_truncated_by_quote_cap"):
        fetch_notes.append("quote remainder：提示可能因拉取上限未含全部行")
    if quote_remainder_b_tail.get("last_b_may_be_truncated_by_max_rows"):
        fetch_notes.append("quote remainder：提示可能因 max_rows 截断")
    return {
        "merged_unique_ew": int(sk.get("total", 0)),
        "skipped_row_breakdown": skipped_breakdown,
        "skipped_rows_total": total_skip,
        "fetch_completeness_notes": fetch_notes,
        "rules_zh": [
            "B 列无内容：整行不参与合并",
            "C 列无 EW 单号：整行不参与合并",
            "同一 EW 已在 cancel→complete→order 中出现：quote 等后续表中重复行忽略",
            "同一表内重复 EW：仅首次计入合并",
        ],
    }


def _merge_db_ai_into_loads_for_skip(
    merged_loads: list[dict[str, Any]],
    *,
    snapshot_by_qn: dict[str, dict[str, Any]],
    allowlist: frozenset[str],
    skip_qnos: set[str],
) -> None:
    """库内已打过 v3 Sheet AI 时间戳的行：把 allowlist 列从 DB 补进 load（仅当 Sheet 侧该字段为空）。"""
    for load in merged_loads:
        qn = str(load.get("quote_no") or "").strip()
        if qn not in skip_qnos:
            continue
        patch = snapshot_by_qn.get(qn) or {}
        for k, v in patch.items():
            if k not in allowlist:
                continue
            cur = load.get(k)
            empty = cur is None or (isinstance(cur, str) and not str(cur).strip())
            if not empty:
                continue
            if v is None:
                continue
            if isinstance(v, str) and not str(v).strip():
                continue
            load[k] = v


def _sheet_row_ai_partition_merge_and_enrich(
    ai_jobs: list[tuple[dict[str, Any], list[Any], str, dict[str, str]]],
    merged_loads: list[dict[str, Any]],
    rules: dict[str, Any],
    *,
    ai_stats: AiEnrichRunStats,
    ai_overwrite: bool,
    progress: dict[str, Any] | None,
) -> set[str]:
    """
    按 quote_no + data_source 查库：已有 v3_sheet_ai_enriched_at 则跳过 Gemini，并从 DB 合并 allowlist 快照到 load；
    否则参与批量 enrich。返回本 run API 成功写回 load 的 quote_no。
    """
    v2db = _get_v2_db()
    path = get_settings().db_path
    conn = v2db.open_db(path)
    v2db.ensure_schema(conn)
    try:
        ds = sheet_import_data_source(rules)
        qns = [str(j[0]["quote_no"]).strip() for j in ai_jobs if str(j[0].get("quote_no") or "").strip()]
        done = v2db.fetch_quote_nos_v3_sheet_ai_done(conn, qns, data_source=ds)
        allow = build_ai_allowlist(rules)
        if done:
            snap = v2db.fetch_load_allowlist_snapshot_for_quote_nos(
                conn, list(done), allow, data_source=ds
            )
            _merge_db_ai_into_loads_for_skip(
                merged_loads,
                snapshot_by_qn=snap,
                allowlist=allow,
                skip_qnos=done,
            )
        to_call = [
            j
            for j in ai_jobs
            if str(j[0].get("quote_no") or "").strip() not in done
        ]
        ai_stats.skipped_db = len(ai_jobs) - len(to_call)
        if progress is not None:
            progress["ai_total"] = len(to_call)
            progress["ai_done"] = 0
            progress["phase"] = "ai"
        return enrich_loads_batches_parallel(
            to_call,
            rules=rules,
            batch_size=ai_batch_max_rows(rules),
            max_workers=ai_parallel_batch_workers(rules),
            overwrite=ai_overwrite,
            stats=ai_stats,
            progress=progress,
            progress_lock=_LONG_TASK_LOCK,
        )
    finally:
        conn.close()


def _merge_four_tabs_to_import_items(
    tabs_by_key: dict[str, dict[str, Any]],
    rules: dict[str, Any],
    *,
    quote_first_data_row_1based: int | None = None,
    max_rows_request: int | None = None,
    ai_enrich: bool = False,
    ai_overwrite: bool = False,
    progress: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    placed_keys: set[str] = set()
    merged_loads: list[dict[str, Any]] = []
    stats: dict[str, int] = {
        "cancel": 0,
        "complete": 0,
        "order": 0,
        "quote_pending_quote": 0,
        "quote_quoted": 0,
        "quote_no_customer_response": 0,
        "quote_stale_cancel": 0,
        "skipped_non_list_row": 0,
        "skipped_non_compliant_no_column_b": 0,
        "skipped_non_compliant_no_ew_id": 0,
        "skipped_ew_in_earlier_stage": 0,
        "skipped_duplicate_ew_same_tab": 0,
        "total": 0,
    }
    quote_b_meta: dict[str, Any] = {"applied": False}
    quote_tab_last_b_full: dict[str, Any] = {
        "applied": False,
        "reason": "not_computed",
        "scope": "quote_tab_full_batch",
    }
    ai_stats: AiEnrichRunStats | None = None
    ai_jobs: list[
        tuple[dict[str, Any], list[Any], str, dict[str, str]]
    ] | None = None
    if ai_enrich:
        if not v3_sheet_row_ai_enabled():
            raise ValueError(
                "Sheet 行 AI 未启用：请将环境变量 V3_SHEET_ROW_AI_ENABLED 设为 1（或 true）"
            )
        ai_stats = AiEnrichRunStats()
        ai_jobs = []

    for stage in _MERGE_STAGE_ORDER:
        tab = tabs_by_key.get(stage) or {}
        rows_raw = _rows_raw_lists(tab)
        if stage != "quote":
            tab_nq = tabs_by_key.get(stage) or {}
            header_row_nq = tab_nq.get("header_row") or []
            seen_local_keys: set[str] = set()
            for row in rows_raw:
                if not isinstance(row, list):
                    stats["skipped_non_list_row"] += 1
                    continue
                if not _row_has_column_b_data(row):
                    stats["skipped_non_compliant_no_column_b"] += 1
                    continue
                qn = _ew_id_from_row(row)
                fk = _quote_no_fold_key(qn)
                if not fk:
                    stats["skipped_non_compliant_no_ew_id"] += 1
                    continue
                if fk in placed_keys:
                    stats["skipped_ew_in_earlier_stage"] += 1
                    continue
                if fk in seen_local_keys:
                    stats["skipped_duplicate_ew_same_tab"] += 1
                    continue
                seen_local_keys.add(fk)
                placed_keys.add(fk)
                cells = _letters_to_row_dict(row)
                load = _load_preview(tab_key=stage, cells=cells, quote_no=qn)
                if ai_jobs is not None:
                    ai_jobs.append((load, list(header_row_nq), stage, dict(cells)))
                merged_loads.append(load)
                if progress is not None:
                    progress["merge_rows"] = len(merged_loads)
                stats[stage] += 1
                stats["total"] += 1
            continue

        pct = _sheet_quote_b_tail_percent(rules)
        dr = int(quote_first_data_row_1based or sheet_first_data_row_1based(rules))
        full_quote_n = len(rows_raw)
        q_tab = tabs_by_key.get("quote") or {}
        header_row_q = q_tab.get("header_row") or []
        quote_extend_applied = _quote_tab_extend_fetch_applied(q_tab, rules)
        quote_fetch_capped = bool(q_tab.get("quote_fetch_capped"))
        q_cap_max = q_tab.get("quote_extend_fetch_max_total_rows")
        quote_cap_max_i = int(q_cap_max) if q_cap_max is not None else None
        quote_tab_last_b_full = _quote_tab_last_b_scan(
            rows_raw,
            first_data_row_1based=dr,
            max_rows_request=max_rows_request,
            quote_extend_fetch_applied=quote_extend_applied,
            quote_fetch_capped=quote_fetch_capped,
            quote_extend_fetch_max_total_rows=quote_cap_max_i,
        )

        remainder_entries: list[tuple[str, list[Any], int]] = []
        for tab_row_i, row in enumerate(rows_raw):
            if not isinstance(row, list):
                stats["skipped_non_list_row"] += 1
                continue
            if not _row_has_column_b_data(row):
                stats["skipped_non_compliant_no_column_b"] += 1
                continue
            qn = _ew_id_from_row(row)
            fk = _quote_no_fold_key(qn)
            if not fk:
                stats["skipped_non_compliant_no_ew_id"] += 1
                continue
            if fk in placed_keys:
                stats["skipped_ew_in_earlier_stage"] += 1
                continue
            remainder_entries.append((qn, row, tab_row_i))

        rem_rows = [r for _, r, _ in remainder_entries]
        tab_indices = [i for _, _, i in remainder_entries]
        statuses, quote_b_meta = _assign_quote_remainder_statuses(
            rem_rows,
            pct,
            quote_row_indices_in_tab=tab_indices,
            first_data_row_1based=dr,
            quote_tab_total_rows_fetched=full_quote_n,
            max_rows_request=max_rows_request,
            quote_extend_fetch_applied=quote_extend_applied,
            quote_fetch_capped=quote_fetch_capped,
            quote_extend_fetch_max_total_rows=quote_cap_max_i,
        )

        seen_q_keys: set[str] = set()
        for (qn, row, _tab_i), st in zip(remainder_entries, statuses):
            fk = _quote_no_fold_key(qn)
            if fk in seen_q_keys:
                stats["skipped_duplicate_ew_same_tab"] += 1
                continue
            seen_q_keys.add(fk)
            placed_keys.add(fk)
            cells = _letters_to_row_dict(row)
            load = _load_preview(tab_key="quote", cells=cells, quote_no=qn)
            load["status"] = st
            if _apply_quote_stale_cancel_by_column_a(load, cells, rules):
                stats["quote_stale_cancel"] += 1
            elif load["status"] == "pending_quote":
                stats["quote_pending_quote"] += 1
            elif load["status"] == "quoted":
                stats["quote_quoted"] += 1
            else:
                stats["quote_no_customer_response"] += 1
            if ai_jobs is not None:
                ai_jobs.append((load, list(header_row_q), "quote", dict(cells)))
            merged_loads.append(load)
            if progress is not None:
                progress["merge_rows"] = len(merged_loads)
            stats["total"] += 1

        if quote_b_meta.get("applied") and quote_tab_last_b_full.get("applied"):
            if quote_b_meta.get("last_b_ew_id") != quote_tab_last_b_full.get(
                "last_b_ew_id"
            ):
                quote_b_meta["remainder_differs_from_full_tab_last_b"] = True

    if progress is not None:
        progress["merge_total"] = len(merged_loads)
        progress["merge_rows"] = len(merged_loads)

    validation = _build_merge_validation(stats, quote_tab_last_b_full, quote_b_meta)

    api_enriched: set[str] = set()
    if ai_jobs is not None and ai_stats is not None:
        if progress is not None:
            progress["phase"] = "validate"
        api_enriched = _sheet_row_ai_partition_merge_and_enrich(
            ai_jobs,
            merged_loads,
            rules,
            ai_stats=ai_stats,
            ai_overwrite=ai_overwrite,
            progress=progress,
        )

    items = [_preview_to_import_item(ld, rules) for ld in merged_loads]
    ai_meta: dict[str, Any] = {
        "ai_enrich_enabled": bool(ai_enrich),
        "ai_enrich_calls": int(ai_stats.calls) if ai_stats else 0,
        "ai_enrich_rows": int(ai_stats.rows) if ai_stats else 0,
        "ai_enrich_failures": int(ai_stats.failures) if ai_stats else 0,
        "ai_enrich_errors": list((ai_stats.errors if ai_stats else [])[:30]),
        "ai_enrich_parallel_batch_workers": (
            int(ai_parallel_batch_workers(rules)) if ai_enrich else 0
        ),
        "ai_enrich_merge_row_count": len(merged_loads),
        "ai_enrich_skipped_db": int(ai_stats.skipped_db) if ai_stats else 0,
        "ai_enrich_api_quote_nos": sorted(api_enriched),
    }
    return items, {
        "stats": stats,
        "quote_tab_last_b_full": quote_tab_last_b_full,
        "quote_remainder_b_tail": quote_b_meta,
        "validation": validation,
        **ai_meta,
    }


def _tab_to_sync_payload(
    tab: dict[str, Any],
    rules: dict[str, Any],
    *,
    apply_quote_b_tail: bool = True,
    max_rows_request: int | None = None,
    ai_enrich: bool = False,
    ai_overwrite: bool = False,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tab_key = str(tab.get("key", "")).strip()
    worksheet = str(tab.get("worksheet", "")).strip()
    header_row = tab.get("header_row") or []
    rows_raw: list[Any] = list(tab.get("rows") or [])

    b_tail_meta: dict[str, Any] | None = None
    if tab_key == "quote" and apply_quote_b_tail:
        pct = _sheet_quote_b_tail_percent(rules)
        if pct > 0:
            dr = tab_first_data_row_1based(tab, rules)
            q_ext = _quote_tab_extend_fetch_applied(tab, rules)
            q_cap = bool(tab.get("quote_fetch_capped"))
            q_mt = tab.get("quote_extend_fetch_max_total_rows")
            q_mt_i = int(q_mt) if q_mt is not None else None
            rows_raw, b_tail_meta = _slice_quote_rows_by_b_tail(
                rows_raw,
                pct,
                first_data_row_1based=dr,
                max_rows_request=max_rows_request,
                quote_extend_fetch_applied=q_ext,
                quote_fetch_capped=q_cap,
                quote_extend_fetch_max_total_rows=q_mt_i,
            )

    parsed: list[dict[str, Any]] = []
    for row in rows_raw:
        if not isinstance(row, list):
            continue
        ew_id = _ew_id_from_row(row)
        if not ew_id:
            continue
        if not _row_has_column_b_data(row):
            continue
        cells = _letters_to_row_dict(row)
        load = _load_preview(tab_key=tab_key, cells=cells, quote_no=ew_id)
        if tab_key == "quote" and cells.get("P", "").strip():
            load["status"] = "quoted"
        if tab_key == "quote":
            _apply_quote_stale_cancel_by_column_a(load, cells, rules)
        parsed.append(
            {
                "ew_id": ew_id,
                "cells": cells,
                "load": load,
            }
        )
        if progress is not None:
            progress["merge_rows"] = len(parsed)
    api_enriched: set[str] = set()
    if ai_enrich:
        if not v3_sheet_row_ai_enabled():
            raise ValueError(
                "Sheet 行 AI 未启用：请将环境变量 V3_SHEET_ROW_AI_ENABLED 设为 1（或 true）"
            )
        ai_stats = AiEnrichRunStats()
        ai_jobs = [
            (p["load"], list(header_row), tab_key, dict(p["cells"])) for p in parsed
        ]
        merged_for_ai = [p["load"] for p in parsed]
        n = len(ai_jobs)
        if progress is not None:
            progress["merge_total"] = n
            progress["merge_rows"] = n
        api_enriched = _sheet_row_ai_partition_merge_and_enrich(
            ai_jobs,
            merged_for_ai,
            rules,
            ai_stats=ai_stats,
            ai_overwrite=ai_overwrite,
            progress=progress,
        )
    else:
        ai_stats = None

    out: dict[str, Any] = {
        "key": tab_key,
        "worksheet": worksheet,
        "header_row": header_row,
        "default_status": _TAB_DEFAULT_STATUS.get(tab_key, "pending_quote"),
        "rows": parsed,
        "row_count": len(parsed),
    }
    if b_tail_meta is not None:
        out["quote_b_tail_filter"] = b_tail_meta
    out["ai_enrich_enabled"] = bool(ai_enrich)
    out["ai_enrich_calls"] = int(ai_stats.calls) if ai_stats else 0
    out["ai_enrich_rows"] = int(ai_stats.rows) if ai_stats else 0
    out["ai_enrich_failures"] = int(ai_stats.failures) if ai_stats else 0
    out["ai_enrich_errors"] = list((ai_stats.errors if ai_stats else [])[:30])
    out["ai_enrich_parallel_batch_workers"] = (
        int(ai_parallel_batch_workers(rules)) if ai_enrich else 0
    )
    out["ai_enrich_skipped_db"] = int(ai_stats.skipped_db) if ai_stats else 0
    out["ai_enrich_api_quote_nos"] = sorted(api_enriched)
    return out


def _first_four_tab_keys(rules: dict[str, Any]) -> list[str]:
    sheet_cfg = rules.get("sheet") or {}
    tabs_cfg = sheet_cfg.get("tabs") or []
    if not isinstance(tabs_cfg, list):
        raise ValueError("sheet.tabs 无效")
    first_four = [t for t in tabs_cfg[:4] if isinstance(t, dict)]
    if len(first_four) < 4:
        raise ValueError("ai_sheet_rules 需至少配置前四个 tab")
    return [str(t.get("key", "")).strip() for t in first_four]


def _persist_merge_items(
    import_items: list[dict[str, Any]],
    *,
    rows_read: int,
    data_source: str,
    ai_api_quote_nos: set[str] | None = None,
) -> int:
    v2db = _get_v2_db()
    path = get_settings().db_path
    conn = v2db.open_db(path)
    v2db.ensure_schema(conn)
    now = v2db.now_iso()
    written = 0
    skipped = 0
    with conn:
        for item in import_items:
            item = dict(item)
            _apply_def_notes_to_item(item)
            item["data_source"] = data_source
            qn = str(item["quote_no"]).strip()
            ai_patch = item.pop("_v3_ai_patch", None)
            v2db.upsert_load_from_sheet_import(
                conn,
                quote_no=str(item["quote_no"]),
                item=item,
                source_tabs=str(item["source_tabs"]),
                now=now,
            )
            if ai_api_quote_nos is not None and qn in ai_api_quote_nos:
                patch_d = dict(ai_patch) if isinstance(ai_patch, dict) else {}
                v2db.patch_load_v3_sheet_ai_columns(
                    conn, qn, patch_d, now=now
                )
            written += 1
        conn.execute(
            """
            INSERT INTO load_sync_log(
              run_at, trigger, rows_read, rows_written, rows_skipped, success, error_message
            )
            VALUES (?, ?, ?, ?, ?, 1, '')
            """,
            (now, "v3_sheet_merge", int(rows_read), int(written), int(skipped)),
        )
    return written


def build_sync_load_preview(
    *,
    max_rows: int | None = None,
    tab_key: str | None = None,
    apply: bool = False,
    ai: bool = False,
    ai_overwrite: bool = False,
) -> dict[str, Any]:
    if ai and not v3_sheet_row_ai_enabled():
        raise ValueError(
            "Sheet 行 AI 未启用：请将环境变量 V3_SHEET_ROW_AI_ENABLED 设为 1（或 true）"
        )
    prog = _long_task_progress_begin(ai)
    try:
        rules = load_ai_sheet_rules()
        first_four_keys = _first_four_tab_keys(rules)
        single = (tab_key or "").strip() or None
        if apply and single:
            raise ValueError("apply=true 仅支持四表合并，请不要传 tab 参数")

        if single:
            if single not in first_four_keys:
                raise ValueError(
                    f"sync-load 参数 tab 必须是前四个 key 之一 {first_four_keys!r}，收到 {single!r}"
                )
            if prog is not None:
                prog["phase"] = "sheet"
            payload = refresh_sheet(tab_key=single, max_rows=max_rows)
            tabs_in = [t for t in (payload.get("tabs") or []) if isinstance(t, dict)]
            raw_mr = payload.get("max_rows")
            try:
                mr = int(raw_mr) if raw_mr is not None else None
            except (TypeError, ValueError):
                mr = None
            if mr is not None and mr <= 0:
                mr = None
            if prog is not None:
                prog["phase"] = "merge"
            out_tabs = [
                _tab_to_sync_payload(
                    t,
                    rules,
                    apply_quote_b_tail=True,
                    max_rows_request=mr,
                    ai_enrich=ai,
                    ai_overwrite=ai_overwrite,
                    progress=prog,
                )
                for t in tabs_in
            ]
            return {
                "spreadsheet_id": payload.get("spreadsheet_id"),
                "rules_path": payload.get("rules_path"),
                "max_rows": payload.get("max_rows"),
                "first_data_row_1based": sheet_first_data_row_1based(rules),
                "persisted": False,
                "data_source": sheet_import_data_source(rules),
                "tabs": out_tabs,
                "errors": payload.get("errors") or [],
            }

        if prog is not None:
            prog["phase"] = "sheet"
        payload = refresh_sheet(tab_key=None, max_rows=max_rows)
        tabs_by_key = {
            str(t.get("key", "")).strip(): t
            for t in (payload.get("tabs") or [])
            if isinstance(t, dict)
        }
        tabs_data = [tabs_by_key[k] for k in first_four_keys if k in tabs_by_key]

        if prog is not None:
            prog["phase"] = "merge"
        # 四表路径：AI 只在 _merge_four_tabs_to_import_items 内对「合并后」行跑一次。
        # 若此处传 ai_enrich=ai，会对 cancel/complete/order/quote 各跑一遍全表 Gemini，
        # 耗时长且 progress=None，前端长期卡在 phase=merge。
        out_tabs = [
            _tab_to_sync_payload(
                t,
                rules,
                apply_quote_b_tail=False,
                ai_enrich=False,
                ai_overwrite=ai_overwrite,
                progress=None,
            )
            for t in tabs_data
        ]

        merge_source = {
            k: tabs_by_key[k]
            for k in _MERGE_STAGE_ORDER
            if k in tabs_by_key and k in first_four_keys
        }
        merge_keys = list(merge_source.keys())
        quote_tab_payload = merge_source.get("quote") or {}
        q_dr = quote_tab_payload.get("first_data_row_1based")
        raw_mr_m = payload.get("max_rows")
        try:
            mr_merge = int(raw_mr_m) if raw_mr_m is not None else None
        except (TypeError, ValueError):
            mr_merge = None
        if mr_merge is not None and mr_merge <= 0:
            mr_merge = None
        import_items, merge_meta = _merge_four_tabs_to_import_items(
            merge_source,
            rules,
            quote_first_data_row_1based=int(q_dr) if q_dr is not None else None,
            max_rows_request=mr_merge,
            ai_enrich=ai,
            ai_overwrite=ai_overwrite,
            progress=prog,
        )

        # 预览列表包含全部合并行（含 quoted）；后续若要做条件过滤可加查询参数再裁剪。
        preview_rows: list[dict[str, Any]] = [
            {
                "quote_no": it["quote_no"],
                "status": it["status"],
                "customer_name": it.get("customer_name", ""),
                "source_tabs": it.get("source_tabs", ""),
            }
            for it in import_items
        ]
        preview_quoted_hidden = 0

        rows_read = sum(len(_rows_raw_lists(merge_source[k])) for k in merge_keys)
        persisted = False
        rows_written = 0
        if apply:
            if prog is not None:
                prog["phase"] = "persist"
            api_qns = set(merge_meta.get("ai_enrich_api_quote_nos") or [])
            rows_written = _persist_merge_items(
                import_items,
                rows_read=rows_read,
                data_source=sheet_import_data_source(rules),
                ai_api_quote_nos=api_qns if ai else None,
            )
            persisted = True

        val_body = dict(merge_meta.get("validation") or {})
        val_body["sheet_refresh_errors"] = list(payload.get("errors") or [])
        merge_response = {
            "preview_rows": preview_rows,
            "preview_quoted_hidden_count": preview_quoted_hidden,
            **{k: v for k, v in merge_meta.items() if k != "validation"},
            "validation": val_body,
        }

        return {
            "spreadsheet_id": payload.get("spreadsheet_id"),
            "rules_path": payload.get("rules_path"),
            "max_rows": payload.get("max_rows"),
            "first_data_row_1based": sheet_first_data_row_1based(rules),
            "persisted": persisted,
            "rows_written": rows_written,
            "data_source": sheet_import_data_source(rules),
            "merged_unique_ew": int((merge_meta.get("stats") or {}).get("total", 0)),
            "tabs": out_tabs,
            "merge": merge_response,
            "errors": payload.get("errors") or [],
        }
    finally:
        if prog is not None:
            _long_task_progress_finish()


def merge_refresh_clear_quote_then_apply(
    *,
    max_rows: int | None = None,
    ai: bool = False,
    ai_overwrite: bool = False,
    clear_quote: bool = False,
) -> dict[str, Any]:
    """
    刷新入库：拉四表 → 合并（行级校验）→ 可选多线程 Gemini → upsert（有则更新、无则新增）。
    clear_quote=true 时先删除库中本 data_source 且 source_tabs 含 quote 的 load 行，再写入。
    """
    rules = load_ai_sheet_rules()
    ds = sheet_import_data_source(rules)
    deleted = 0
    if clear_quote:
        v2db = _get_v2_db()
        path = get_settings().db_path
        conn = v2db.open_db(path)
        v2db.ensure_schema(conn)
        deleted = v2db.clear_load_quote_for_data_source(conn, data_source=ds)
        conn.close()
    sync = build_sync_load_preview(
        max_rows=max_rows,
        tab_key=None,
        apply=True,
        ai=ai,
        ai_overwrite=ai_overwrite,
    )
    merge_block = dict(sync.get("merge") or {})
    # 入库 API 不需要上万行 preview_rows；整包 JSON 过大易导致编码/内存/代理超时 → 500。
    _pr = merge_block.get("preview_rows")
    if isinstance(_pr, list):
        merge_block["preview_row_count"] = len(_pr)
        merge_block["preview_rows"] = []
    return {
        "data_source": ds,
        "clear_quote_before_apply": bool(clear_quote),
        "deleted_quote_tab_load_rows": int(deleted),
        "rows_written": sync.get("rows_written"),
        "spreadsheet_id": sync.get("spreadsheet_id"),
        "errors": sync.get("errors") or [],
        "merge_stats": merge_block.get("stats"),
        "merge": merge_block,
    }


@router.get("/sheet/long-task-progress")
def api_sheet_long_task_progress() -> dict[str, Any]:
    """供前端轮询：拉表 / 合并 / 校验 / AI / 写库 等阶段（仅 sync-load 且 ai=true 时更新）。"""
    return long_task_progress_snapshot()


@router.post("/sheet/debug-row-ai")
def api_sheet_debug_row_ai(
    ew: str | None = Query(None, description="EW 单号（C 列）"),
    quote_no: str | None = Query(
        None, description="与 ew 二选一；二者至少填一个（trim 后非空）"
    ),
    max_rows: int | None = Query(
        None,
        ge=0,
        le=1_000_000,
        description="拉表行数上限；省略或 0 为不限制",
    ),
    prompt_only: bool = Query(
        False,
        description="true：只构建 prompt，不调 Gemini，且不要求 V3_SHEET_ROW_AI_ENABLED",
    ),
    ai_overwrite: bool = Query(
        False,
        description="false：AI 输出仅填补空字段；true：可覆盖已有非空（见 load_after_ai）",
    ),
) -> dict[str, Any]:
    """
    调试：按现拉 Sheet 在四表中定位一行，生成与合并路径一致的 enrich prompt，可选调用 Gemini。
    quote 行 status 使用 P 列规则，与四表合并 B 尾批量状态可能不一致。
    """
    ident = (ew or quote_no or "").strip()
    if not ident:
        raise HTTPException(
            status_code=400,
            detail="请提供查询参数 ew 或 quote_no",
        )
    try:
        rules = load_ai_sheet_rules()
        mr_dbg = int(max_rows) if max_rows is not None and int(max_rows) > 0 else None
        payload = refresh_sheet(tab_key=None, max_rows=mr_dbg)
        tabs_by_key = {
            str(t.get("key", "")).strip(): t
            for t in (payload.get("tabs") or [])
            if isinstance(t, dict)
        }
        hit = _debug_find_sheet_row_for_ew(tabs_by_key, ident)
        if hit is None:
            raise HTTPException(
                status_code=404,
                detail="在四表合规行（B 列非空）中未找到该 EW 单号",
            )
        tab_key, row, tab = hit
        worksheet = str(tab.get("worksheet", "")).strip()
        header_row = tab.get("header_row") or []
        cells = _letters_to_row_dict(row)
        qn = _ew_id_from_row(row)
        load = _load_preview(tab_key=tab_key, cells=cells, quote_no=qn)
        if tab_key == "quote" and cells.get("P", "").strip():
            load["status"] = "quoted"
        if tab_key == "quote":
            _apply_quote_stale_cancel_by_column_a(load, cells, rules)

        jobs = [(load, list(header_row), tab_key, dict(cells))]
        payload_rows = build_payload_rows_from_jobs(jobs, rules)
        prompt = build_enrich_prompt(rules, payload_rows)
        gen_cfg = enrich_generation_config(rules)

        out: dict[str, Any] = {
            "found": {
                "tab_key": tab_key,
                "worksheet": worksheet,
                "header_row": header_row,
                "cells": cells,
                "load_before_ai": copy.deepcopy(load),
            },
            "prompt": prompt,
            "generation_config": gen_cfg,
            "prompt_only": prompt_only,
            "gemini_raw": None,
            "model_text": "",
            "parsed_json": None,
            "merge_error": None,
            "load_after_ai": None,
            "spreadsheet_id": payload.get("spreadsheet_id"),
            "errors": payload.get("errors") or [],
        }

        if prompt_only:
            return out

        if not v3_sheet_row_ai_enabled():
            raise HTTPException(
                status_code=400,
                detail="Sheet 行 AI 未启用：请将环境变量 V3_SHEET_ROW_AI_ENABLED 设为 1（或 true）",
            )

        raw, text = run_enrich_generate(rules, prompt)
        if isinstance(raw, str):
            out["merge_error"] = raw[:800] if len(raw) > 800 else raw
            out["model_text"] = text or ""
            return out

        out["gemini_raw"] = raw
        out["model_text"] = text
        if not text:
            out["merge_error"] = "AI_EMPTY_TEXT"
            return out
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            out["merge_error"] = "AI_BAD_JSON"
            return out
        out["parsed_json"] = parsed
        if not isinstance(parsed, list):
            out["merge_error"] = "AI_NOT_ARRAY"
            return out
        if len(parsed) != 1:
            out["merge_error"] = f"AI_LEN_MISMATCH want=1 got={len(parsed)}"
            return out
        delta = sanitize_enrich_delta(parsed[0], rules)
        load_after = copy.deepcopy(load)
        apply_ai_delta_to_load(load_after, delta, overwrite=ai_overwrite)
        out["load_after_ai"] = load_after
        return out
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sheet/sync-load")
def api_sheet_sync_load(
    max_rows: int | None = Query(
        None,
        ge=0,
        le=1_000_000,
        description="每表数据行上限；省略或 0 表示读全表（分页）",
    ),
    tab: str | None = Query(
        None,
        description="仅同步指定 tab 的 key（quote/order/complete/cancel）；省略则拉取前四个 tab 并合并预览",
    ),
    apply: bool = Query(
        False,
        description="true：四表合并结果写入 V2_DB_PATH 的 load 表（勿与 tab 同用）",
    ),
    ai: bool = Query(
        False,
        description="true：合并/单 tab 预览路径上对每行 load 调用 Gemini 补缺（需 V3_SHEET_ROW_AI_ENABLED 与 API key）",
    ),
    ai_overwrite: bool = Query(
        False,
        description="true：AI 可覆盖 load 已有非空字段；默认仅填空",
    ),
) -> dict[str, Any]:
    try:
        t = tab.strip() if tab else None
        mr = int(max_rows) if max_rows is not None and int(max_rows) > 0 else None
        return build_sync_load_preview(
            max_rows=mr, tab_key=t, apply=apply, ai=ai, ai_overwrite=ai_overwrite
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sheet/merge-refresh")
def api_sheet_merge_refresh(
    max_rows: int | None = Query(
        None,
        ge=0,
        le=1_000_000,
        description="每表数据行上限；省略或 0 为不限制（quote 仍受 yaml 连续拉取总上限约束）",
    ),
    ai: bool = Query(
        False,
        description="true：校验与合并后，多线程按批调用 Gemini 补缺，再 upsert（需 V3_SHEET_ROW_AI_ENABLED）",
    ),
    ai_overwrite: bool = Query(
        False,
        description="true：AI 可覆盖已有非空字段；默认仅填空",
    ),
    clear_quote: bool = Query(
        False,
        description=(
            "true：写库前先删除本 data_source 且 source_tabs 含 quote 的 load 行；"
            "false：直接 upsert（有则更新、无则新增）"
        ),
    ),
) -> dict[str, Any]:
    """拉 Sheet → 四表合并与行级校验 → 可选 Gemini（并发）→ 写入 V2_DB_PATH。"""
    try:
        mr = int(max_rows) if max_rows is not None and int(max_rows) > 0 else None
        return merge_refresh_clear_quote_then_apply(
            max_rows=mr,
            ai=ai,
            ai_overwrite=ai_overwrite,
            clear_quote=clear_quote,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
