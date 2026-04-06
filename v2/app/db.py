from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_STATUS = (
    "quote",
    "ordered",
    "ready_to_pick",
    "carrier_assigned",
    "picked",
    "complete",
    "cancel",
)


def _load_status_check_in_clause() -> str:
    return ",".join(f"'{s}'" for s in ALLOWED_STATUS)


def _load_create_table_ddl(table_name: str) -> str:
    check = _load_status_check_in_clause()
    return f"""
        CREATE TABLE {table_name} (
          quote_no TEXT PRIMARY KEY,
          status TEXT NOT NULL CHECK (status IN ({check})),
          is_trouble_case INTEGER NOT NULL DEFAULT 0 CHECK (is_trouble_case IN (0,1)),
          customer_name TEXT NOT NULL DEFAULT '',
          note_d_raw TEXT NOT NULL DEFAULT '',
          note_e_raw TEXT NOT NULL DEFAULT '',
          note_f_raw TEXT NOT NULL DEFAULT '',
          pieces_raw TEXT NOT NULL DEFAULT '',
          commodity_desc TEXT NOT NULL DEFAULT '',
          ship_from_raw TEXT NOT NULL DEFAULT '',
          consignee_contact TEXT NOT NULL DEFAULT '',
          shipper_info TEXT NOT NULL DEFAULT '',
          consignee_info TEXT NOT NULL DEFAULT '',
          ship_to_raw TEXT NOT NULL DEFAULT '',
          weight_raw TEXT NOT NULL DEFAULT '',
          dimension_raw TEXT NOT NULL DEFAULT '',
          volume_raw TEXT NOT NULL DEFAULT '',
          cargo_value_raw TEXT NOT NULL DEFAULT '',
          customer_quote_raw TEXT NOT NULL DEFAULT '',
          driver_rate_raw TEXT NOT NULL DEFAULT '',
          distance_miles REAL,
          origin_land_use TEXT NOT NULL DEFAULT '',
          dest_land_use TEXT NOT NULL DEFAULT '',
          validate_ok INTEGER NOT NULL DEFAULT 0 CHECK (validate_ok IN (0,1)),
          validate_error TEXT NOT NULL DEFAULT '',
          validated_at TEXT NOT NULL DEFAULT '',
          used_ai_retry INTEGER NOT NULL DEFAULT 0 CHECK (used_ai_retry IN (0,1)),
          ai_confidence REAL,
          origin_normalized TEXT NOT NULL DEFAULT '',
          dest_normalized TEXT NOT NULL DEFAULT '',
          ai_notes TEXT NOT NULL DEFAULT '',
          source_tabs TEXT NOT NULL DEFAULT '',
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """


def _migrate_load_status_if_needed(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='load'"
    ).fetchone()
    if not row or not row["sql"]:
        return
    sql = str(row["sql"] or "")
    if "carrier_assigned" in sql:
        return
    cols = [
        str(r["name"]) for r in conn.execute("PRAGMA table_info(load)").fetchall()
    ]
    if not cols:
        return
    collist = ",".join(cols)
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(_load_create_table_ddl("load__new"))
        conn.execute(f"INSERT INTO load__new ({collist}) SELECT {collist} FROM load")
        conn.execute("DROP TABLE load")
        conn.execute("ALTER TABLE load__new RENAME TO load")
    except Exception:
        conn.rollback()
        raise


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        f"""
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS load (
          quote_no TEXT PRIMARY KEY,
          status TEXT NOT NULL CHECK (status IN ({_load_status_check_in_clause()})),
          is_trouble_case INTEGER NOT NULL DEFAULT 0 CHECK (is_trouble_case IN (0,1)),
          customer_name TEXT NOT NULL DEFAULT '',
          note_d_raw TEXT NOT NULL DEFAULT '',
          note_e_raw TEXT NOT NULL DEFAULT '',
          note_f_raw TEXT NOT NULL DEFAULT '',
          pieces_raw TEXT NOT NULL DEFAULT '',
          commodity_desc TEXT NOT NULL DEFAULT '',
          ship_from_raw TEXT NOT NULL DEFAULT '',
          consignee_contact TEXT NOT NULL DEFAULT '',
          shipper_info TEXT NOT NULL DEFAULT '',
          consignee_info TEXT NOT NULL DEFAULT '',
          ship_to_raw TEXT NOT NULL DEFAULT '',
          weight_raw TEXT NOT NULL DEFAULT '',
          dimension_raw TEXT NOT NULL DEFAULT '',
          volume_raw TEXT NOT NULL DEFAULT '',
          cargo_value_raw TEXT NOT NULL DEFAULT '',
          customer_quote_raw TEXT NOT NULL DEFAULT '',
          driver_rate_raw TEXT NOT NULL DEFAULT '',
          distance_miles REAL,
          origin_land_use TEXT NOT NULL DEFAULT '',
          dest_land_use TEXT NOT NULL DEFAULT '',
          validate_ok INTEGER NOT NULL DEFAULT 0 CHECK (validate_ok IN (0,1)),
          validate_error TEXT NOT NULL DEFAULT '',
          validated_at TEXT NOT NULL DEFAULT '',
          used_ai_retry INTEGER NOT NULL DEFAULT 0 CHECK (used_ai_retry IN (0,1)),
          ai_confidence REAL,
          origin_normalized TEXT NOT NULL DEFAULT '',
          dest_normalized TEXT NOT NULL DEFAULT '',
          ai_notes TEXT NOT NULL DEFAULT '',
          source_tabs TEXT NOT NULL DEFAULT '',
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS load_sync_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_at TEXT NOT NULL,
          trigger TEXT NOT NULL,
          rows_read INTEGER NOT NULL DEFAULT 0,
          rows_written INTEGER NOT NULL DEFAULT 0,
          rows_skipped INTEGER NOT NULL DEFAULT 0,
          success INTEGER NOT NULL DEFAULT 1 CHECK (success IN (0,1)),
          error_message TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS import_lock (
          lock_key TEXT PRIMARY KEY,
          lock_value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS load_validation_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          quote_no TEXT NOT NULL,
          run_at TEXT NOT NULL,
          success INTEGER NOT NULL DEFAULT 0 CHECK (success IN (0,1)),
          distance_miles REAL,
          origin_land_use TEXT NOT NULL DEFAULT '',
          dest_land_use TEXT NOT NULL DEFAULT '',
          used_ai_retry INTEGER NOT NULL DEFAULT 0 CHECK (used_ai_retry IN (0,1)),
          ai_confidence REAL,
          origin_normalized TEXT NOT NULL DEFAULT '',
          dest_normalized TEXT NOT NULL DEFAULT '',
          ai_notes TEXT NOT NULL DEFAULT '',
          error_message TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS debug_validation_job (
          id TEXT PRIMARY KEY,
          kind TEXT NOT NULL CHECK (kind IN ('all', 'tab')),
          tab_key TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL CHECK (status IN ('queued','running','done','error')),
          total INTEGER NOT NULL DEFAULT 0,
          processed INTEGER NOT NULL DEFAULT 0,
          ok_count INTEGER NOT NULL DEFAULT 0,
          fail_deleted INTEGER NOT NULL DEFAULT 0,
          ai_retry_count INTEGER NOT NULL DEFAULT 0,
          ai_recovered_count INTEGER NOT NULL DEFAULT 0,
          current_quote_no TEXT NOT NULL DEFAULT '',
          error_message TEXT NOT NULL DEFAULT '',
          started_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          finished_at TEXT NOT NULL DEFAULT ''
        );
        """
    )
    _ensure_load_columns(conn)
    _migrate_load_status_if_needed(conn)
    conn.commit()


def _ensure_load_columns(conn: sqlite3.Connection) -> None:
    existing = {
        str(r["name"])
        for r in conn.execute("PRAGMA table_info(load)").fetchall()
    }
    wanted: dict[str, str] = {
        "customer_name": "TEXT NOT NULL DEFAULT ''",
        "note_d_raw": "TEXT NOT NULL DEFAULT ''",
        "note_e_raw": "TEXT NOT NULL DEFAULT ''",
        "note_f_raw": "TEXT NOT NULL DEFAULT ''",
        "pieces_raw": "TEXT NOT NULL DEFAULT ''",
        "commodity_desc": "TEXT NOT NULL DEFAULT ''",
        "ship_from_raw": "TEXT NOT NULL DEFAULT ''",
        "consignee_contact": "TEXT NOT NULL DEFAULT ''",
        "shipper_info": "TEXT NOT NULL DEFAULT ''",
        "consignee_info": "TEXT NOT NULL DEFAULT ''",
        "ship_to_raw": "TEXT NOT NULL DEFAULT ''",
        "weight_raw": "TEXT NOT NULL DEFAULT ''",
        "dimension_raw": "TEXT NOT NULL DEFAULT ''",
        "volume_raw": "TEXT NOT NULL DEFAULT ''",
        "cargo_value_raw": "TEXT NOT NULL DEFAULT ''",
        "customer_quote_raw": "TEXT NOT NULL DEFAULT ''",
        "driver_rate_raw": "TEXT NOT NULL DEFAULT ''",
        "distance_miles": "REAL",
        "origin_land_use": "TEXT NOT NULL DEFAULT ''",
        "dest_land_use": "TEXT NOT NULL DEFAULT ''",
        "validate_ok": "INTEGER NOT NULL DEFAULT 0 CHECK (validate_ok IN (0,1))",
        "validate_error": "TEXT NOT NULL DEFAULT ''",
        "validated_at": "TEXT NOT NULL DEFAULT ''",
        "used_ai_retry": "INTEGER NOT NULL DEFAULT 0 CHECK (used_ai_retry IN (0,1))",
        "ai_confidence": "REAL",
        "origin_normalized": "TEXT NOT NULL DEFAULT ''",
        "dest_normalized": "TEXT NOT NULL DEFAULT ''",
        "ai_notes": "TEXT NOT NULL DEFAULT ''",
    }
    for col, ddl in wanted.items():
        if col in existing:
            continue
        conn.execute(f"ALTER TABLE load ADD COLUMN {col} {ddl}")
    _ensure_validation_log_columns(conn)


def _ensure_validation_log_columns(conn: sqlite3.Connection) -> None:
    existing = {
        str(r["name"])
        for r in conn.execute("PRAGMA table_info(load_validation_log)").fetchall()
    }
    wanted: dict[str, str] = {
        "used_ai_retry": "INTEGER NOT NULL DEFAULT 0 CHECK (used_ai_retry IN (0,1))",
        "ai_confidence": "REAL",
        "origin_normalized": "TEXT NOT NULL DEFAULT ''",
        "dest_normalized": "TEXT NOT NULL DEFAULT ''",
        "ai_notes": "TEXT NOT NULL DEFAULT ''",
    }
    for col, ddl in wanted.items():
        if col in existing:
            continue
        conn.execute(f"ALTER TABLE load_validation_log ADD COLUMN {col} {ddl}")


def is_import_done(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT lock_value FROM import_lock WHERE lock_key = 'initial_load_done'"
    ).fetchone()
    if not row:
        return False
    v = row["lock_value"]
    return str(v).strip() == "1"


def set_import_done(conn: sqlite3.Connection) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO import_lock(lock_key, lock_value, updated_at)
        VALUES ('initial_load_done', '1', ?)
        ON CONFLICT(lock_key) DO UPDATE SET
          lock_value = excluded.lock_value,
          updated_at = excluded.updated_at
        """,
        (ts,),
    )
    conn.commit()


def reset_for_test(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM load")
    conn.execute("DELETE FROM import_lock WHERE lock_key = 'initial_load_done'")
    conn.commit()


def clear_load_only(conn: sqlite3.Connection) -> int:
    cur = conn.execute("DELETE FROM load")
    conn.execute("DELETE FROM import_lock WHERE lock_key = 'initial_load_done'")
    conn.commit()
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.OperationalError:
        pass
    return int(cur.rowcount or 0)


def has_running_validation_job(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT 1 AS x FROM debug_validation_job
        WHERE status IN ('queued', 'running')
        LIMIT 1
        """
    ).fetchone()
    return bool(row)


def create_validation_job(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    kind: str,
    tab_key: str,
    total: int,
) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO debug_validation_job(
          id, kind, tab_key, status,
          total, processed, ok_count, fail_deleted, ai_retry_count, ai_recovered_count,
          current_quote_no, error_message, started_at, updated_at, finished_at
        ) VALUES (?, ?, ?, 'running', ?, 0, 0, 0, 0, 0, '', '', ?, ?, '')
        """,
        (job_id, kind, tab_key, int(total), ts, ts),
    )


def get_validation_job(conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM debug_validation_job WHERE id = ?", (job_id,)
    ).fetchone()


def update_validation_job_progress(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    processed: int,
    ok_count: int,
    fail_deleted: int,
    ai_retry_count: int,
    ai_recovered_count: int,
    current_quote_no: str,
) -> None:
    conn.execute(
        """
        UPDATE debug_validation_job SET
          processed = ?,
          ok_count = ?,
          fail_deleted = ?,
          ai_retry_count = ?,
          ai_recovered_count = ?,
          current_quote_no = ?,
          updated_at = ?
        WHERE id = ?
        """,
        (
            int(processed),
            int(ok_count),
            int(fail_deleted),
            int(ai_retry_count),
            int(ai_recovered_count),
            current_quote_no,
            now_iso(),
            job_id,
        ),
    )
    conn.commit()


def finish_validation_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    status: str,
    error_message: str = "",
) -> None:
    ts = now_iso()
    conn.execute(
        """
        UPDATE debug_validation_job SET
          status = ?,
          error_message = ?,
          updated_at = ?,
          finished_at = ?
        WHERE id = ?
        """,
        (status, error_message, ts, ts, job_id),
    )
    conn.commit()


def delete_load_and_validation_logs(conn: sqlite3.Connection, quote_no: str) -> None:
    last_err: Exception | None = None
    for _ in range(5):
        try:
            conn.execute("DELETE FROM load_validation_log WHERE quote_no = ?", (quote_no,))
            conn.execute("DELETE FROM load WHERE quote_no = ?", (quote_no,))
            return
        except sqlite3.OperationalError as e:
            last_err = e
            if "locked" not in str(e).lower():
                raise
            time.sleep(0.2)
    if last_err:
        raise last_err

