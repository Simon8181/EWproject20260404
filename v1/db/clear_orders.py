#!/usr/bin/env python3
"""清空 ew_orders 与 order_fee_addons（与 delete_all_order_data.sql 等价）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    import psycopg
except ImportError as e:
    print("需要 psycopg：pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(1) from e

_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(_ROOT / ".env")
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        print("未设置 DATABASE_URL（请在仓库根目录 .env 中配置）。", file=sys.stderr)
        raise SystemExit(1)
    with psycopg.connect(url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE order_fee_addons")
            cur.execute("TRUNCATE TABLE ew_orders")
        conn.commit()
    print("已清空 order_fee_addons 与 ew_orders。")


if __name__ == "__main__":
    main()
