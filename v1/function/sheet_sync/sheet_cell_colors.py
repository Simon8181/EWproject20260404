"""Cell background colors via Sheets API v4 — gspread `get_all_values()` has no formatting."""

from __future__ import annotations

from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from .config import credentials_path

_SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)

_service: Any = None


def _get_service() -> Any:
    global _service
    if _service is None:
        creds = Credentials.from_service_account_file(str(credentials_path()), scopes=_SCOPES)
        _service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _service


def _a1_range(sheet_title: str, col_letter: str, start_row: int, end_row: int) -> str:
    t = sheet_title.replace("'", "''")
    return f"'{t}'!{col_letter}{start_row}:{col_letter}{end_row}"


def _rgb_from_bg(bg: dict[str, Any] | None) -> tuple[float, float, float]:
    if not bg:
        return (1.0, 1.0, 1.0)
    return (
        float(bg.get("red") or 0),
        float(bg.get("green") or 0),
        float(bg.get("blue") or 0),
    )


def classify_fill(rgb: tuple[float, float, float]) -> str:
    """Map fill RGB (0–1) to labels: 红→待找车，绿→已经安排。"""
    r, g, b = rgb
    if r > 0.92 and g > 0.92 and b > 0.92:
        return ""
    if r >= g + 0.12 and r >= b + 0.12 and r >= 0.35:
        return "待找车"
    if g >= r + 0.12 and g >= b + 0.12 and g >= 0.35:
        return "已经安排"
    return ""


def fetch_column_fill_labels(
    spreadsheet_id: str,
    sheet_title: str,
    column_letter: str,
    data_start_row: int,
    row_count: int,
) -> list[str]:
    """
    One label per data row (same order as value rows from data_start_row).
    Uses effectiveFormat.backgroundColor when present.
    """
    if row_count <= 0:
        return []
    col = column_letter.strip().upper()
    end_row = data_start_row + row_count - 1
    rng = _a1_range(sheet_title, col, data_start_row, end_row)
    svc = _get_service()
    resp = (
        svc.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id.strip(),
            ranges=[rng],
            includeGridData=True,
            # Narrow payload; effectiveFormat includes backgroundColor when set
            fields="sheets(data(rowData(values(effectiveFormat))))",
        )
        .execute()
    )
    sheets_out = resp.get("sheets") or []
    if not sheets_out:
        return [""] * row_count
    data_blocks = sheets_out[0].get("data") or []
    if not data_blocks:
        return [""] * row_count
    row_data = data_blocks[0].get("rowData") or []
    out: list[str] = []
    for i in range(row_count):
        if i >= len(row_data) or row_data[i] is None:
            out.append("")
            continue
        vals = row_data[i].get("values") or []
        if not vals:
            out.append("")
            continue
        cell = vals[0]
        eff = (cell.get("effectiveFormat") or {}).get("backgroundColor")
        rgb = _rgb_from_bg(eff)
        out.append(classify_fill(rgb))
    return out
