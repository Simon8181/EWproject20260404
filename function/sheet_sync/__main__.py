from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .catalog import get_google_for_sheet, project_root, resolve_rules_for_sheet
from .config import load_mapping
from .sync import (
    _open_sheet_client,
    fetch_worksheet_rows,
    normalize_row_strings,
    probe_sheet,
    row_passes_filters,
    run_sync,
)


def _default_rules_path() -> Path:
    return project_root() / "function" / "sheet_sync" / "rules" / "EW_SHEET_RULES.yaml"


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
        default=None,
        help="Path to rules YAML (default: function/sheet_sync/rules/EW_SHEET_RULES.yaml)",
    )
    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        metavar="ID",
        help="Logical sheet id from EW_CATALOG.yaml (e.g. ew_quote_working), or a route/alias listed there",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Only test Google API: print worksheet title and headers (no DB, no rules file required if --sheet)",
    )
    parser.add_argument(
        "--spreadsheet-id",
        type=str,
        default=None,
        help="With --probe: ID from /d/<ID>/edit (optional if --sheet is set)",
    )
    parser.add_argument(
        "--worksheet-id",
        type=int,
        default=None,
        help="With --probe: gid= from URL (optional if --sheet is set)",
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
        sid = args.spreadsheet_id
        wid = args.worksheet_id
        if args.sheet and (sid is None or wid is None):
            try:
                sid, wid, _ = get_google_for_sheet(args.sheet)
            except Exception as e:
                print(f"Could not resolve --sheet in EW_CATALOG.yaml: {e}", file=sys.stderr)
                sys.exit(1)
        if not sid:
            print(
                "Usage: python -m function.sheet_sync --probe "
                "--spreadsheet-id YOUR_ID --worksheet-id GID\n"
                "Or: python -m function.sheet_sync --probe --sheet ew_quote_working",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            probe_sheet(
                sid,
                worksheet_id=wid,
                worksheet_name=args.worksheet,
            )
        except Exception as e:
            print(f"Probe failed: {e}", file=sys.stderr)
            sys.exit(1)
        return

    mapping_path: Path
    if args.sheet:
        try:
            mapping_path = resolve_rules_for_sheet(args.sheet)
        except Exception as e:
            print(f"{e}", file=sys.stderr)
            sys.exit(1)
    elif args.mapping is not None:
        mapping_path = args.mapping
    else:
        mapping_path = _default_rules_path()

    if not mapping_path.is_file():
        print(
            f"Rules file not found: {mapping_path}\n"
            "Use --sheet ew_quote_working, or -m path/to/rules.yaml, "
            "see EW_CATALOG.yaml and function/sheet_sync/rules/.",
            file=sys.stderr,
        )
        sys.exit(1)

    cfg = load_mapping(mapping_path)
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

    _rows_json(None)


if __name__ == "__main__":
    main()
