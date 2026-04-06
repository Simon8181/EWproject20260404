from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from .db import ALLOWED_STATUS, ensure_schema, is_import_done, now_iso, set_import_done
from .mapping import LoadMapping, TabConfig
from .sheet_colors import fetch_column_a_color_labels

_SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)


STATUS_PRIORITY = {
    "quote": 1,
    "ordered": 2,
    "ready_to_pick": 3,
    "carrier_assigned": 4,
    "picked": 5,
    "complete": 6,
    "cancel": 7,
}


@dataclass
class ImportStats:
    rows_read: int = 0
    rows_written: int = 0
    rows_skipped: int = 0


def _normalize(v: Any) -> str:
    return ("" if v is None else str(v)).strip()


def _rows_to_dicts(values: list[list[Any]]) -> list[dict[str, str]]:
    if not values:
        return []
    header = [_normalize(x) for x in values[0]]
    out: list[dict[str, str]] = []
    for row in values[1:]:
        d: dict[str, str] = {}
        for idx, key in enumerate(header):
            d[key] = _normalize(row[idx]) if idx < len(row) else ""
        out.append(d)
    return out


def _col_val(row: list[Any], col_letter: str) -> str:
    idx = ord(col_letter.upper()) - ord("A")
    if idx < 0 or idx >= len(row):
        return ""
    return _normalize(row[idx])


def _rows_from_start(values: list[list[Any]], start_row: int) -> list[list[Any]]:
    start_idx = max(0, start_row - 1)
    return values[start_idx:] if start_idx < len(values) else []


def _resolve_status(tab: TabConfig, row: dict[str, str]) -> str:
    if tab.status_mode == "fixed":
        s = tab.status_value or tab.status_default
        return s if s in ALLOWED_STATUS else tab.status_default
    if tab.status_mode == "keyword":
        text = row.get(tab.status_column_letter or "", "").strip().lower()
        for key, mapped in tab.status_map.items():
            if key and key in text and mapped in ALLOWED_STATUS:
                return mapped
        return tab.status_default if tab.status_default in ALLOWED_STATUS else "quote"
    return tab.status_default if tab.status_default in ALLOWED_STATUS else "quote"


def _resolve_trouble_case(tab: TabConfig, row: dict[str, str]) -> bool:
    if not tab.trouble_column_letter:
        return False
    val = row.get(tab.trouble_column_letter, "").strip().lower()
    return val in tab.trouble_truthy


def _higher_priority_status(current: str, incoming: str) -> str:
    a = STATUS_PRIORITY.get(current, 0)
    b = STATUS_PRIORITY.get(incoming, 0)
    return incoming if b >= a else current


def _sheet_service(credentials_file: str) -> Any:
    creds = Credentials.from_service_account_file(
        credentials_file,
        scopes=_SCOPES,
        always_use_jwt_access=True,
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _fetch_rows(
    svc: Any,
    *,
    spreadsheet_id: str,
    worksheet: str,
    data_start_row: int,
) -> list[list[str]]:
    title = worksheet.replace("'", "''")
    a1 = f"'{title}'!A{max(1, data_start_row)}:U"
    resp = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=a1)
        .execute()
    )
    return resp.get("values") or []


def run_one_time_import(
    conn: sqlite3.Connection,
    mapping: LoadMapping,
    *,
    credentials_file: str,
    app_env: str,
    force_reimport: bool = False,
    trigger: str = "manual",
) -> ImportStats:
    ensure_schema(conn)
    if is_import_done(conn) and not force_reimport:
        return ImportStats()
    if app_env == "prod" and force_reimport:
        raise RuntimeError("生产环境禁止 force_reimport")

    svc = _sheet_service(credentials_file)
    now = now_iso()
    aggregate: dict[str, dict[str, Any]] = {}
    stats = ImportStats()

    for tab in mapping.tabs:
        raw_rows = _fetch_rows(
            svc,
            spreadsheet_id=mapping.spreadsheet_id,
            worksheet=tab.worksheet,
            data_start_row=tab.data_start_row,
        )
        color_labels: list[str] = [""] * len(raw_rows)
        if tab.use_color_status:
            color_labels = fetch_column_a_color_labels(
                spreadsheet_id=mapping.spreadsheet_id,
                worksheet_title=tab.worksheet,
                start_row=tab.data_start_row,
                row_count=len(raw_rows),
                credentials_file=credentials_file,
            )
        rows: list[dict[str, str]] = []
        for i, raw in enumerate(raw_rows):
            d = {
                "A": _col_val(raw, "A"),
                "B": _col_val(raw, "B"),
                "C": _col_val(raw, "C"),
                "D": _col_val(raw, "D"),
                "E": _col_val(raw, "E"),
                "F": _col_val(raw, "F"),
                "G": _col_val(raw, "G"),
                "H": _col_val(raw, "H"),
                "I": _col_val(raw, "I"),
                "J": _col_val(raw, "J"),
                "K": _col_val(raw, "K"),
                "L": _col_val(raw, "L"),
                "M": _col_val(raw, "M"),
                "N": _col_val(raw, "N"),
                "O": _col_val(raw, "O"),
                "P": _col_val(raw, "P"),
                "U": _col_val(raw, "U"),
                "_A_COLOR": color_labels[i] if i < len(color_labels) else "",
            }
            rows.append(d)
        stats.rows_read += len(rows)
        for row in rows:
            quote_no = row.get(tab.key_column_letter, "").strip()
            if not quote_no:
                stats.rows_skipped += 1
                continue
            status = _resolve_status(tab, row)
            color_key = row.get("_A_COLOR", "").strip().lower()
            if tab.use_color_status and color_key in tab.color_status_map:
                mapped = tab.color_status_map[color_key]
                if mapped in ALLOWED_STATUS:
                    status = _higher_priority_status(status, mapped)
            is_trouble = _resolve_trouble_case(tab, row)
            prev = aggregate.get(quote_no)
            if not prev:
                sf = row.get("I", "")
                cc = row.get("J", "")
                st = row.get("K", "")
                aggregate[quote_no] = {
                    "quote_no": quote_no,
                    "status": status,
                    "is_trouble_case": is_trouble,
                    "customer_name": row.get("B", ""),
                    "note_d_raw": row.get("D", ""),
                    "note_e_raw": row.get("E", ""),
                    "note_f_raw": row.get("F", ""),
                    "pieces_raw": row.get("G", ""),
                    "commodity_desc": row.get("H", ""),
                    "ship_from_raw": sf,
                    "consignee_contact": cc,
                    "ship_to_raw": st,
                    "weight_raw": row.get("L", ""),
                    "dimension_raw": row.get("M", ""),
                    "volume_raw": row.get("N", ""),
                    "cargo_value_raw": row.get("O", ""),
                    "customer_quote_raw": row.get("P", ""),
                    "driver_rate_raw": row.get("U", ""),
                    "source_tabs": {tab.key or tab.worksheet},
                }
                continue
            prev["status"] = _higher_priority_status(prev["status"], status)
            prev["is_trouble_case"] = bool(prev["is_trouble_case"] or is_trouble)
            # Fill empty fields only; avoid noisy overwrite from later tabs.
            sf = row.get("I", "")
            cc = row.get("J", "")
            st = row.get("K", "")
            for field, val in (
                ("customer_name", row.get("B", "")),
                ("note_d_raw", row.get("D", "")),
                ("note_e_raw", row.get("E", "")),
                ("note_f_raw", row.get("F", "")),
                ("pieces_raw", row.get("G", "")),
                ("commodity_desc", row.get("H", "")),
                ("ship_from_raw", sf),
                ("consignee_contact", cc),
                ("ship_to_raw", st),
                ("weight_raw", row.get("L", "")),
                ("dimension_raw", row.get("M", "")),
                ("volume_raw", row.get("N", "")),
                ("cargo_value_raw", row.get("O", "")),
                ("customer_quote_raw", row.get("P", "")),
                ("driver_rate_raw", row.get("U", "")),
            ):
                if not str(prev.get(field, "")).strip() and str(val).strip():
                    prev[field] = val
            prev["source_tabs"].add(tab.key or tab.worksheet)

    with conn:
        for quote_no, item in aggregate.items():
            source_tabs = ",".join(sorted(item["source_tabs"]))
            conn.execute(
                """
                INSERT INTO load (
                  quote_no, status, is_trouble_case,
                  customer_name, note_d_raw, note_e_raw, note_f_raw, pieces_raw, commodity_desc,
                  ship_from_raw, consignee_contact, ship_to_raw,
                  weight_raw, dimension_raw,
                  volume_raw, cargo_value_raw, customer_quote_raw, driver_rate_raw,
                  source_tabs,
                  first_seen_at, last_seen_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(quote_no) DO UPDATE SET
                  status = excluded.status,
                  is_trouble_case = excluded.is_trouble_case,
                  customer_name = excluded.customer_name,
                  note_d_raw = excluded.note_d_raw,
                  note_e_raw = excluded.note_e_raw,
                  note_f_raw = excluded.note_f_raw,
                  pieces_raw = excluded.pieces_raw,
                  commodity_desc = excluded.commodity_desc,
                  ship_from_raw = excluded.ship_from_raw,
                  consignee_contact = excluded.consignee_contact,
                  ship_to_raw = excluded.ship_to_raw,
                  weight_raw = excluded.weight_raw,
                  dimension_raw = excluded.dimension_raw,
                  volume_raw = excluded.volume_raw,
                  cargo_value_raw = excluded.cargo_value_raw,
                  customer_quote_raw = excluded.customer_quote_raw,
                  driver_rate_raw = excluded.driver_rate_raw,
                  source_tabs = excluded.source_tabs,
                  last_seen_at = excluded.last_seen_at,
                  updated_at = excluded.updated_at
                """,
                (
                    quote_no,
                    item["status"],
                    1 if item["is_trouble_case"] else 0,
                    item.get("customer_name", ""),
                    item.get("note_d_raw", ""),
                    item.get("note_e_raw", ""),
                    item.get("note_f_raw", ""),
                    item.get("pieces_raw", ""),
                    item.get("commodity_desc", ""),
                    item.get("ship_from_raw", ""),
                    item.get("consignee_contact", ""),
                    item.get("ship_to_raw", ""),
                    item.get("weight_raw", ""),
                    item.get("dimension_raw", ""),
                    item.get("volume_raw", ""),
                    item.get("cargo_value_raw", ""),
                    item.get("customer_quote_raw", ""),
                    item.get("driver_rate_raw", ""),
                    source_tabs,
                    now,
                    now,
                    now,
                    now,
                ),
            )
            stats.rows_written += 1
        conn.execute(
            """
            INSERT INTO load_sync_log(run_at, trigger, rows_read, rows_written, rows_skipped, success, error_message)
            VALUES (?, ?, ?, ?, ?, 1, '')
            """,
            (now, trigger, stats.rows_read, stats.rows_written, stats.rows_skipped),
        )
    set_import_done(conn)
    return stats

