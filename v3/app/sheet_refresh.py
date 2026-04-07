"""Core Sheet 刷新：按 core/ai_sheet_rules.yaml 拉取表头（第 1 行）与数据区。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.settings import load_env
from core.config_paths import ai_sheet_rules_yaml

_SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)
_COL_LAST = "U"
# 不设 max_rows 时按此大小分批请求 Google API，直至读到表网格末尾
_FETCH_CHUNK_ROWS = 10_000

router = APIRouter(prefix="/api/core", tags=["core"])


def _cell_at(row: Any, idx: int) -> str:
    if not isinstance(row, list):
        return ""
    if idx < 0 or idx >= len(row):
        return ""
    v = row[idx]
    return ("" if v is None else str(v)).strip()


def _b_column_nonblank(row: Any) -> bool:
    return bool(_cell_at(row, 1))


def _quote_extend_fetch_enabled(sheet_cfg: dict[str, Any]) -> bool:
    v = sheet_cfg.get("quote_extend_fetch_for_b_tail")
    if v is None:
        return True
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _quote_extend_max_total_rows(sheet_cfg: dict[str, Any]) -> int:
    v = sheet_cfg.get("quote_extend_fetch_max_total_rows")
    if v is None:
        return 12_000
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 12_000
    return max(1, min(n, 50_000))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_spreadsheet_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", s)
    if m:
        return m.group(1)
    return s


def _credentials_path() -> Path:
    load_env()
    repo = _repo_root()
    v2_root = repo / "v2"
    raw = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        str(v2_root / "config" / "service_account.json"),
    )
    p = Path(raw)
    if not p.is_absolute():
        p = (v2_root / p).resolve()
    if p.is_file():
        return p
    local_default = v2_root / "config" / "service_account.json"
    if local_default.is_file():
        return local_default
    return p


def _sheet_service(credentials_file: str) -> Any:
    creds = Credentials.from_service_account_file(
        credentials_file,
        scopes=_SCOPES,
        always_use_jwt_access=True,
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _a1_range(worksheet: str, start_row: int, end_row: int) -> str:
    title = worksheet.replace("'", "''")
    return f"'{title}'!A{start_row}:{_COL_LAST}{end_row}"


def _worksheet_row_counts(svc: Any, spreadsheet_id: str) -> dict[str, int]:
    """工作表标题 → 网格行数（含空行）。values.get 会裁掉区间尾部全空行，需据此对齐下一起始行。"""
    resp = (
        svc.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(title,gridProperties(rowCount)))",
        )
        .execute()
    )
    out: dict[str, int] = {}
    for sh in resp.get("sheets") or []:
        props = sh.get("properties") or {}
        title = str(props.get("title", ""))
        gp = props.get("gridProperties") or {}
        rc = gp.get("rowCount")
        if title and isinstance(rc, int) and rc >= 1:
            out[title] = rc
    return out


def _pad_values_chunk(chunk: list[Any], *, expected_rows: int) -> list[Any]:
    """Google API 不返回区间内尾部全空行，补齐为 expected_rows 行以保持与表行号一一对应。"""
    if expected_rows <= 0:
        return []
    out = [list(r) if isinstance(r, list) else [] for r in chunk]
    while len(out) < expected_rows:
        out.append([])
    return out[:expected_rows]


def load_ai_sheet_rules() -> dict[str, Any]:
    path = ai_sheet_rules_yaml()
    if not path.is_file():
        raise FileNotFoundError(f"缺少 ai_sheet_rules: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def sheet_first_data_row_1based(rules: dict[str, Any]) -> int:
    """sheet 级默认：第一条数据行的 1-based 行号（表头仍固定读第 1 行）。"""
    sheet_cfg = rules.get("sheet") or {}
    v = sheet_cfg.get("first_data_row_1based")
    if v is None:
        return 2
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 2
    return max(1, min(n, 1_000_000))


def tab_first_data_row_1based(tab: dict[str, Any], rules: dict[str, Any]) -> int:
    """tab 可设 first_data_row_1based 覆盖 sheet 默认值；与 refresh 拉数起始行一致。"""
    v = tab.get("first_data_row_1based")
    if v is not None:
        try:
            n = int(v)
            return max(1, min(n, 1_000_000))
        except (TypeError, ValueError):
            pass
    return sheet_first_data_row_1based(rules)


def fetch_tab_header_row_only(*, tab_key: str) -> list[Any]:
    """
    仅读指定 tab 工作表第 1 行（表头 A–U），供 Tab 页补 AI 等轻量场景。
    避免 refresh_sheet 整表分页拉取。
    """
    rules = load_ai_sheet_rules()
    sheet_cfg = rules.get("sheet") or {}
    sid = _normalize_spreadsheet_id(str(sheet_cfg.get("spreadsheet_id", "")).strip())
    if not sid:
        raise ValueError("ai_sheet_rules.yaml 中 sheet.spreadsheet_id 为空")
    tabs_raw = sheet_cfg.get("tabs") or []
    if not isinstance(tabs_raw, list):
        raise ValueError("sheet.tabs 必须是列表")
    worksheet = ""
    for tab in tabs_raw:
        if not isinstance(tab, dict):
            continue
        if str(tab.get("key", "")).strip() != tab_key.strip():
            continue
        worksheet = str(tab.get("worksheet", "")).strip()
        break
    if not worksheet:
        raise ValueError(f"sheet.tabs 中未找到 key={tab_key!r}")
    creds_path = _credentials_path()
    if not creds_path.is_file():
        raise FileNotFoundError(
            f"未找到 Google 凭证文件: {creds_path}（可设 GOOGLE_APPLICATION_CREDENTIALS）"
        )
    svc = _sheet_service(str(creds_path))
    hdr_resp = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=sid, range=_a1_range(worksheet, 1, 1))
        .execute()
    )
    return list((hdr_resp.get("values") or [[]])[0])


def refresh_sheet(*, tab_key: str | None, max_rows: int | None = None) -> dict[str, Any]:
    """
    max_rows：每表最多读取的数据行数（不含表头）；``None`` 或 ``<=0`` 表示不限制，
    按 `_FETCH_CHUNK_ROWS` 分页直至工作表网格末尾（quote 连续拉取仍受 yaml 总上限约束）。
    """
    rules = load_ai_sheet_rules()
    sheet_cfg = rules.get("sheet") or {}
    sid = _normalize_spreadsheet_id(str(sheet_cfg.get("spreadsheet_id", "")).strip())
    if not sid:
        raise ValueError("ai_sheet_rules.yaml 中 sheet.spreadsheet_id 为空")

    tabs_raw = sheet_cfg.get("tabs") or []
    if not isinstance(tabs_raw, list):
        raise ValueError("sheet.tabs 必须是列表")

    creds_path = _credentials_path()
    if not creds_path.is_file():
        raise FileNotFoundError(
            f"未找到 Google 凭证文件: {creds_path}（可设 GOOGLE_APPLICATION_CREDENTIALS）"
        )

    unlimited = max_rows is None
    if not unlimited:
        try:
            if int(max_rows) <= 0:
                unlimited = True
        except (TypeError, ValueError):
            unlimited = True
    if unlimited:
        per_chunk = _FETCH_CHUNK_ROWS
        max_rows_out: int | None = None
    else:
        per_chunk = max(1, min(int(max_rows), 1_000_000))
        max_rows_out = per_chunk
    svc = _sheet_service(str(creds_path))
    row_counts = _worksheet_row_counts(svc, sid)
    out_tabs: list[dict[str, Any]] = []
    errors: list[str] = []

    for tab in tabs_raw:
        if not isinstance(tab, dict):
            continue
        key = str(tab.get("key", "")).strip()
        worksheet = str(tab.get("worksheet", "")).strip()
        if not worksheet:
            continue
        if tab_key and key != tab_key:
            continue
        try:
            hdr_resp = (
                svc.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range=_a1_range(worksheet, 1, 1))
                .execute()
            )
            header_row = (hdr_resp.get("values") or [[]])[0]
            dr = tab_first_data_row_1based(tab, rules)
            # 与 API 返回的标题一致；若未查到网格行数则退化为大上限，仅依赖批大小推进（易与表不符时产生多余请求）
            grid_max = int(row_counts.get(worksheet) or 2_097_152)
            extend_quote = (key or "").strip() == "quote" and _quote_extend_fetch_enabled(
                sheet_cfg
            )
            max_total = _quote_extend_max_total_rows(sheet_cfg)
            cur = dr
            rows: list[Any] = []
            rounds = 0
            quote_fetch_capped = False
            while True:
                rounds += 1
                if extend_quote:
                    remaining = max_total - len(rows)
                    if remaining <= 0:
                        if rows and _b_column_nonblank(rows[-1]):
                            quote_fetch_capped = True
                        break
                    this_batch = min(per_chunk, remaining)
                else:
                    if unlimited:
                        this_batch = min(per_chunk, grid_max - cur + 1)
                        if this_batch <= 0:
                            break
                    else:
                        this_batch = per_chunk
                end_data = min(cur + this_batch - 1, grid_max)
                if cur > grid_max or cur > end_data:
                    break
                data_resp = (
                    svc.spreadsheets()
                    .values()
                    .get(
                        spreadsheetId=sid,
                        range=_a1_range(worksheet, cur, end_data),
                    )
                    .execute()
                )
                raw_chunk = data_resp.get("values") or []
                expected_len = end_data - cur + 1
                chunk = _pad_values_chunk(raw_chunk, expected_rows=expected_len)
                rows.extend(chunk)
                if not extend_quote:
                    if unlimited:
                        cur = end_data + 1
                        if cur > grid_max:
                            break
                        continue
                    break
                cur = end_data + 1
                if cur > grid_max:
                    break
            entry: dict[str, Any] = {
                "key": key or worksheet,
                "worksheet": worksheet,
                "header_row": header_row,
                "first_data_row_1based": dr,
                "row_count": len(rows),
                "rows": rows,
            }
            if extend_quote:
                entry["quote_fetch_extend_rounds"] = int(rounds)
                entry["quote_extend_fetch_max_total_rows"] = int(max_total)
                if quote_fetch_capped:
                    entry["quote_fetch_capped"] = True
            out_tabs.append(entry)
        except Exception as e:
            errors.append(f"{key or worksheet}: {e!s}")

    if tab_key and not out_tabs and not errors:
        raise ValueError(f"未找到 tab key: {tab_key!r}")

    return {
        "spreadsheet_id": sid,
        "rules_path": str(ai_sheet_rules_yaml()),
        "max_rows": max_rows_out,
        "tabs": out_tabs,
        "errors": errors,
    }


@router.get("/sheet/refresh")
def api_sheet_refresh(
    tab: str | None = Query(
        None,
        description="仅刷新指定 tab 的 key（如 quote）；省略则刷新配置中全部 tab",
    ),
    max_rows: int | None = Query(
        None,
        ge=0,
        le=1_000_000,
        description="每表数据行上限；省略或 0 表示读至表网格末尾（分页拉取）",
    ),
) -> dict[str, Any]:
    try:
        mr: int | None = None if max_rows is None else int(max_rows)
        if mr is not None and mr <= 0:
            mr = None
        return refresh_sheet(
            tab_key=tab.strip() if tab else None,
            max_rows=mr,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
