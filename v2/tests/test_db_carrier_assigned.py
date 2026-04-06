from __future__ import annotations

import sqlite3
import unittest

from app.db import (
    _load_create_table_ddl,
    _load_status_check_in_clause,
    ensure_schema,
    now_iso,
)


class DbCarrierAssignedTest(unittest.TestCase):
    def test_fresh_schema_accepts_carrier_assigned(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO load (
              quote_no, status, first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, 'carrier_assigned', ?, ?, ?, ?)
            """,
            ("q1", ts, ts, ts, ts),
        )
        conn.commit()
        row = conn.execute(
            "SELECT status FROM load WHERE quote_no = ?", ("q1",)
        ).fetchone()
        self.assertEqual(row["status"], "carrier_assigned")

    def test_migration_from_legacy_check(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        check_old = ",".join(
            f"'{s}'"
            for s in (
                "quote",
                "ordered",
                "ready_to_pick",
                "picked",
                "complete",
                "cancel",
            )
        )
        check_new = _load_status_check_in_clause()
        legacy_ddl = _load_create_table_ddl("load").replace(
            f"CHECK (status IN ({check_new}))",
            f"CHECK (status IN ({check_old}))",
        )
        conn.executescript(legacy_ddl)
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO load (
              quote_no, status, first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, 'ordered', ?, ?, ?, ?)
            """,
            ("q1", ts, ts, ts, ts),
        )
        conn.commit()
        ensure_schema(conn)
        conn.execute(
            "UPDATE load SET status = 'carrier_assigned' WHERE quote_no = 'q1'"
        )
        conn.commit()
        row = conn.execute(
            "SELECT status FROM load WHERE quote_no = ?", ("q1",)
        ).fetchone()
        self.assertEqual(row["status"], "carrier_assigned")


if __name__ == "__main__":
    unittest.main()
