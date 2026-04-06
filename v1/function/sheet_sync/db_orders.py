"""Load `ew_orders` rows from Postgres for the order list UI (Sheet → DB via sync)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from function.sheet_sync.config import database_url


def _cell_to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def row_dict_all_str(row: dict[str, Any]) -> dict[str, str]:
    return {k: _cell_to_str(v) for k, v in row.items()}


def load_ew_orders_from_db(limit: int | None = None) -> list[dict[str, str]]:
    """
    Return all columns from `ew_orders` as string dicts (compatible with order_view).
    Caller should apply `sort_order_rows_for_display` and optional limit slice.
    """
    url = database_url()
    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "ew_orders"')
            raw = cur.fetchall()
    rows = [row_dict_all_str(dict(r)) for r in raw]
    return rows


def max_ew_orders_synced_at() -> str | None:
    """Latest `synced_at` across rows, ISO string, or None if empty/missing."""
    url = database_url()
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT MAX("synced_at") FROM "ew_orders"')
            row = cur.fetchone()
    if not row or row[0] is None:
        return None
    v = row[0]
    return v.isoformat() if isinstance(v, datetime) else str(v)
