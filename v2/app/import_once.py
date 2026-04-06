from __future__ import annotations

import argparse
import sys

from .db import ensure_schema, open_db, reset_for_test
from .mapping import load_mapping
from .settings import get_settings
from .sheet_import import run_one_time_import


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EW v2: 从 Sheet 一次性导入 load 数据")
    parser.add_argument(
        "--force-reimport",
        action="store_true",
        help="忽略导入锁再次导入（prod 禁止）",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="测试模式先清空 load 与导入锁，再导入",
    )
    parser.add_argument(
        "--trigger",
        default="manual",
        help="写入日志的触发来源标签（默认 manual）",
    )
    args = parser.parse_args(argv)
    st = get_settings()

    conn = open_db(st.db_path)
    ensure_schema(conn)
    if args.reset:
        if st.app_env == "prod":
            raise RuntimeError("生产环境禁止 --reset")
        reset_for_test(conn)

    mapping = load_mapping(st.mapping_path)
    stats = run_one_time_import(
        conn,
        mapping,
        credentials_file=str(st.google_credentials_path),
        app_env=st.app_env,
        force_reimport=args.force_reimport,
        trigger=args.trigger,
    )
    print(
        f"import_done rows_read={stats.rows_read} rows_written={stats.rows_written} rows_skipped={stats.rows_skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

