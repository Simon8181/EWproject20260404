from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

import json

from .config import load_mapping
from .sync import (
    _open_sheet_client,
    fetch_worksheet_rows,
    normalize_row_strings,
    probe_sheet,
    row_passes_filters,
    run_sync,
)


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Read Google Sheets using rules YAML (JSON out). Use --sync only when writing to Postgres.",
    )
    parser.add_argument(
        "-m",
        "--mapping",
        type=Path,
        default=Path("EW_SHEET_RULES.yaml"),
        help="Rules file: EW_SHEET_RULES.yaml or mapping.yaml",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Only test Google API: print worksheet title and headers (no DB, no mapping file)",
    )
    parser.add_argument(
        "--spreadsheet-id",
        type=str,
        default=None,
        help="With --probe: ID from /d/<ID>/edit in the Sheet URL",
    )
    parser.add_argument(
        "--worksheet-id",
        type=int,
        default=None,
        help="With --probe: gid= value from URL (tab id)",
    )
    parser.add_argument(
        "--worksheet",
        type=str,
        default=None,
        help="With --probe: tab name (if not using --worksheet-id)",
    )
    parser.add_argument(
        "--preview",
        type=int,
        metavar="N",
        default=None,
        help="Print first N matching rows as JSON only (no DB)",
    )
    parser.add_argument(
        "--read",
        action="store_true",
        help="Print all matching rows as JSON (default; no DB)",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Write to PostgreSQL (requires DATABASE_URL; optional for later)",
    )
    args = parser.parse_args()

    if args.probe:
        if not args.spreadsheet_id:
            print(
                "Usage: python -m sheet_sync --probe "
                "--spreadsheet-id YOUR_ID --worksheet-id GID\n"
                "Example gid is in the URL: ...?gid=589486198",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            probe_sheet(
                args.spreadsheet_id,
                worksheet_id=args.worksheet_id,
                worksheet_name=args.worksheet,
            )
        except Exception as e:
            print(f"Probe failed: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.mapping.is_file():
        print(
            f"Rules file not found: {args.mapping}\n"
            "Use EW_SHEET_RULES.yaml or copy mapping.example.yaml to mapping.yaml.",
            file=sys.stderr,
        )
        sys.exit(1)

    cfg = load_mapping(args.mapping)
    os.environ.setdefault("MAPPING_FILE", str(cfg.mapping_path))

    def _rows_json(limit: int | None) -> None:
        gc = _open_sheet_client()
        for job in cfg.jobs:
            _, rows = fetch_worksheet_rows(gc, cfg.spreadsheet_id, job)
            filtered: list[dict[str, str]] = []
            for r in rows:
                nr = normalize_row_strings(r, job.reading)
                if not row_passes_filters(nr, job.reading, job):
                    continue
                if job.column_map_mode == "letter":
                    filtered.append(
                        {pg: nr.get(pg, "") for pg in job.columns.values()}
                    )
                else:
                    filtered.append(
                        {
                            pg: nr.get(src_key, "")
                            for src_key, pg in job.columns.items()
                        }
                    )
                if limit is not None and len(filtered) >= limit:
                    break
            print(json.dumps(filtered, ensure_ascii=False, indent=2))

    if args.preview is not None:
        _rows_json(args.preview)
        return

    if args.sync:
        counts = run_sync(cfg)
        for k, v in counts.items():
            print(f"{k}: {v} rows affected")
        return

    # Default: read-only, full export (same as --read)
    _rows_json(None)


if __name__ == "__main__":
    main()
