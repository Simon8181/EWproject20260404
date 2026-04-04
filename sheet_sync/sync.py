from __future__ import annotations

import logging
from typing import Any

import gspread
import psycopg

from .config import (
    AppConfig,
    ReadingRules,
    SheetSyncJob,
    column_letter_to_index,
    credentials_path,
    database_url,
    is_column_letters,
)

logger = logging.getLogger(__name__)


def _open_sheet_client() -> gspread.Client:
    path = credentials_path()
    return gspread.service_account(filename=str(path))


def probe_sheet(
    spreadsheet_id: str,
    worksheet_id: int | None = None,
    worksheet_name: str | None = None,
) -> None:
    """Print tab title, row count, and first row (header) sample — no database."""
    if worksheet_id is None and not worksheet_name:
        raise ValueError("Provide worksheet_id (gid) or worksheet (tab title)")
    gc = _open_sheet_client()
    sh = gc.open_by_key(spreadsheet_id.strip())
    if worksheet_id is not None:
        ws = sh.get_worksheet_by_id(worksheet_id)
    else:
        ws = sh.worksheet(worksheet_name)  # type: ignore[arg-type]
    values = ws.get_all_values()
    print(f"spreadsheet_id: {spreadsheet_id}")
    print(f"worksheet title: {ws.title!r}")
    print(f"data rows (including header): {len(values)}")
    if values:
        hdr = [str(h).strip() for h in values[0]]
        preview = hdr[:25]
        print(f"header columns (first {len(preview)} of {len(hdr)}): {preview}")


def _rows_to_dicts(header: list[str], rows: list[list[Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        d: dict[str, Any] = {}
        for i, key in enumerate(header):
            if i < len(row):
                val = row[i]
                d[key] = "" if val is None else val
            else:
                d[key] = ""
        out.append(d)
    return out


def _normalize_cell(val: Any, rules: ReadingRules) -> str:
    s = "" if val is None else str(val)
    if rules.trim_strings:
        s = s.strip()
    for tok in rules.error_tokens_as_empty:
        if s == tok:
            return ""
    return s


def normalize_row_strings(row: dict[str, Any], rules: ReadingRules) -> dict[str, str]:
    return {k: _normalize_cell(v, rules) for k, v in row.items()}


def row_passes_filters(row: dict[str, str], rules: ReadingRules, job: SheetSyncJob) -> bool:
    for ref in rules.skip_if_empty:
        ref = str(ref).strip()
        if job.column_map_mode == "letter" and is_column_letters(ref):
            pg = job.columns[ref.upper()]
            if not str(row.get(pg, "")).strip():
                return False
        else:
            if not str(row.get(ref, "")).strip():
                return False
    return True


def fetch_worksheet_rows(
    gc: gspread.Client, spreadsheet_id: str, job: SheetSyncJob
) -> tuple[list[str], list[dict[str, Any]]]:
    sh = gc.open_by_key(spreadsheet_id)
    if job.worksheet_id is not None:
        ws = sh.get_worksheet_by_id(job.worksheet_id)
    else:
        assert job.worksheet_name is not None
        ws = sh.worksheet(job.worksheet_name)
    values = ws.get_all_values()
    if not values:
        return [], []
    hr = job.header_row - 1
    dr = job.data_start_row - 1
    if hr < 0 or hr >= len(values):
        raise ValueError(
            f"header_row {job.header_row} is out of range (sheet has {len(values)} rows)"
        )
    if dr < hr:
        raise ValueError("data_start_row must be >= header_row")
    if job.column_map_mode == "letter":
        body = values[dr:] if dr < len(values) else []
        max_idx = max(column_letter_to_index(L) for L in job.columns.keys())
        rows: list[dict[str, Any]] = []
        for raw in body:
            cells = list(raw)
            if len(cells) <= max_idx:
                cells.extend([""] * (max_idx + 1 - len(cells)))
            d: dict[str, Any] = {}
            for letter, pg in job.columns.items():
                L = letter.upper()
                idx = column_letter_to_index(L)
                d[pg] = cells[idx] if idx < len(cells) else ""
            rows.append(d)
        return [], rows

    header = [str(h).strip() for h in values[hr]]
    body = values[dr:] if dr < len(values) else []
    rows = _rows_to_dicts(header, body)
    return header, rows


def upsert_job(conn: psycopg.Connection, job: SheetSyncJob, rows: list[dict[str, Any]]) -> int:
    if not rows:
        logger.info("No data rows for %s -> %s", job.label, job.table)
        return 0

    pg_cols = list(job.columns.values())
    pk_set = set(job.primary_key)
    update_cols = [c for c in pg_cols if c not in pk_set]

    col_list = ", ".join(f'"{c}"' for c in pg_cols)
    placeholders = ", ".join(["%s"] * len(pg_cols))
    conflict_cols = ", ".join(f'"{c}"' for c in job.primary_key)

    if update_cols:
        set_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
        sql = (
            f'INSERT INTO "{job.table}" ({col_list}) VALUES ({placeholders}) '
            f"ON CONFLICT ({conflict_cols}) "
            f"DO UPDATE SET {set_clause}"
        )
    else:
        sql = (
            f'INSERT INTO "{job.table}" ({col_list}) VALUES ({placeholders}) '
            f"ON CONFLICT ({conflict_cols}) DO NOTHING"
        )

    n = 0
    with conn.cursor() as cur:
        for r in rows:
            values: list[Any] = []
            missing = False
            for src_key, pg_col in job.columns.items():
                if job.column_map_mode == "letter":
                    val = r.get(pg_col)
                else:
                    if src_key not in r:
                        logger.warning(
                            "Sheet header %r not in row keys (worksheet %s); skipping row",
                            src_key,
                            job.label,
                        )
                        missing = True
                        break
                    val = r[src_key]
                values.append(val)
            if missing:
                continue
            cur.execute(sql, values)
            n += cur.rowcount if cur.rowcount >= 0 else 1
    return n


def run_sync(cfg: AppConfig) -> dict[str, int]:
    gc = _open_sheet_client()
    url = database_url()
    counts: dict[str, int] = {}

    with psycopg.connect(url) as conn:
        conn.execute("SELECT 1")
        for job in cfg.jobs:
            _, rows = fetch_worksheet_rows(gc, cfg.spreadsheet_id, job)
            mapped_rows: list[dict[str, Any]] = []
            for r in rows:
                nr = normalize_row_strings(r, job.reading)
                if not row_passes_filters(nr, job.reading, job):
                    continue
                if job.column_map_mode == "letter":
                    mapped_rows.append(
                        {pg: nr.get(pg, "") for pg in job.columns.values()}
                    )
                else:
                    mapped_rows.append(
                        {
                            pg: nr.get(src_key, "")
                            for src_key, pg in job.columns.items()
                        }
                    )
            n = upsert_job(conn, job, mapped_rows)
            conn.commit()
            counts[f"{job.label}->{job.table}"] = n
            logger.info("Upserted %s rows for %s -> %s", n, job.label, job.table)

    return counts
