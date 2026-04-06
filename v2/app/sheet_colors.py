from __future__ import annotations

from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

_SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)


def _service(credentials_file: str) -> Any:
    creds = Credentials.from_service_account_file(
        credentials_file,
        scopes=_SCOPES,
        always_use_jwt_access=True,
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _rgb_from_bg(bg: dict[str, Any] | None) -> tuple[float, float, float]:
    if not bg:
        return (1.0, 1.0, 1.0)
    return (
        float(bg.get("red") or 0),
        float(bg.get("green") or 0),
        float(bg.get("blue") or 0),
    )


def _classify_fill(rgb: tuple[float, float, float]) -> str:
    r, g, b = rgb
    if r > 0.92 and g > 0.92 and b > 0.92:
        return ""
    if r >= g + 0.12 and r >= b + 0.12 and r >= 0.35:
        return "red"
    if g >= r + 0.12 and g >= b + 0.12 and g >= 0.35:
        return "green"
    return ""


def fetch_column_a_color_labels(
    *,
    spreadsheet_id: str,
    worksheet_title: str,
    start_row: int,
    row_count: int,
    credentials_file: str,
) -> list[str]:
    if row_count <= 0:
        return []
    title = worksheet_title.replace("'", "''")
    end_row = start_row + row_count - 1
    rng = f"'{title}'!A{start_row}:A{end_row}"
    svc = _service(credentials_file)
    resp = (
        svc.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id.strip(),
            ranges=[rng],
            includeGridData=True,
            fields="sheets(data(rowData(values(effectiveFormat))))",
        )
        .execute()
    )
    sheets = resp.get("sheets") or []
    if not sheets:
        return [""] * row_count
    blocks = sheets[0].get("data") or []
    if not blocks:
        return [""] * row_count
    row_data = blocks[0].get("rowData") or []
    out: list[str] = []
    for i in range(row_count):
        if i >= len(row_data) or row_data[i] is None:
            out.append("")
            continue
        vals = row_data[i].get("values") or []
        if not vals:
            out.append("")
            continue
        bg = (vals[0].get("effectiveFormat") or {}).get("backgroundColor")
        out.append(_classify_fill(_rgb_from_bg(bg)))
    return out

