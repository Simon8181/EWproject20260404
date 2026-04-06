from __future__ import annotations

import sqlite3
import unittest

from app.db import clear_load_quote_only, ensure_schema, now_iso


class ClearLoadQuoteTest(unittest.TestCase):
    def test_clears_only_quote_tab_rows(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO load (
              quote_no, status, source_tabs,
              first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, 'pending_quote', 'quote', ?, ?, ?, ?)
            """,
            ("q-quote", ts, ts, ts, ts),
        )
        conn.execute(
            """
            INSERT INTO load (
              quote_no, status, source_tabs,
              first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, 'ordered', 'order', ?, ?, ?, ?)
            """,
            ("q-order", ts, ts, ts, ts),
        )
        conn.commit()
        n = clear_load_quote_only(conn)
        self.assertEqual(n, 1)
        left = conn.execute(
            "SELECT quote_no FROM load ORDER BY quote_no"
        ).fetchall()
        self.assertEqual([r["quote_no"] for r in left], ["q-order"])


if __name__ == "__main__":
    unittest.main()
