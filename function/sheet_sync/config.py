from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
def is_column_letters(key: str) -> bool:
    ku = key.strip().upper()
    return bool(ku) and bool(re.match(r"^[A-Z]{1,3}$", ku))


def column_letter_to_index(letters: str) -> int:
    """A->0, B->1, …, Z->25, AA->26 (Excel column to 0-based index)."""
    n = 0
    for c in letters.strip().upper():
        if c < "A" or c > "Z":
            raise ValueError(f"Invalid column letter: {letters!r}")
        n = n * 26 + (ord(c) - ord("A") + 1)
    return n - 1


def infer_column_map_mode(keys: list[str]) -> str:
    """Letter mode if every key is A–ZZ (1–2 letters). 3-letter Excel cols (e.g. AAA) need mapping.column_mode: letter."""
    letterish: list[bool] = []
    for k in keys:
        ku = k.strip().upper()
        letterish.append(bool(re.match(r"^[A-Z]{1,3}$", ku)))
    if all(letterish):
        if any(len(k.strip()) == 3 for k in keys):
            return "header"
        return "letter"
    if not any(letterish):
        return "header"
    raise ValueError(
        "columns keys mix Excel letters and header text; set mapping.column_mode to letter or header"
    )


def resolve_column_mode(keys: list[str], explicit: str | None) -> str:
    if explicit in ("letter", "header"):
        return explicit
    if explicit is not None:
        raise ValueError("mapping.column_mode must be letter, header, or omitted")
    return infer_column_map_mode(keys)


def _validate_ident(name: str, ctx: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"Invalid SQL identifier in {ctx}: {name!r}")
    return name


def _parse_color_columns(raw: Any, ctx: str) -> dict[str, str]:
    """Excel column letter → Postgres column name for fill-color-derived fields."""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{ctx}: color_columns must be a mapping")
    out: dict[str, str] = {}
    for k, v in raw.items():
        ks = str(k).strip().upper()
        if not re.match(r"^[A-Z]{1,3}$", ks):
            raise ValueError(f"{ctx}: color_columns key {k!r} must be a column letter (A–ZZZ)")
        out[ks] = _validate_ident(str(v), f"{ctx}.color_columns")
    return out


@dataclass(frozen=True)
class ReadingRules:
    """Post-fetch row handling (replaces ad-hoc SheetSQL-style queries)."""

    trim_strings: bool = True
    error_tokens_as_empty: tuple[str, ...] = ("#DIV/0!", "#N/A", "#REF!", "#VALUE!")
    # header mode: sheet header text; letter mode: column letters (e.g. C) — empty after trim → skip row
    skip_if_empty: tuple[str, ...] = ()


@dataclass(frozen=True)
class SheetSyncJob:
    """Use `worksheet` (tab title) or `worksheet_id` (URL gid=…); gid takes precedence."""

    label: str
    worksheet_name: str | None
    worksheet_id: int | None
    table: str
    primary_key: tuple[str, ...]
    columns: dict[str, str]  # header text -> pg col, OR Excel letters A/AA -> pg col
    column_map_mode: str = "header"  # "header" | "letter"
    header_row: int = 1  # 1-based, row that contains column titles
    data_start_row: int = 2  # 1-based, first data row
    reading: ReadingRules = field(default_factory=ReadingRules)
    # Excel column letter → DB column; fill color read via Sheets API (not cell text)
    color_columns: dict[str, str] = field(default_factory=dict)

    def insert_column_order(self) -> list[str]:
        """All DB columns for INSERT/UPSERT and row dict export (values + color-derived)."""
        seen: set[str] = set()
        out: list[str] = []
        for _k, pg in self.columns.items():
            if pg not in seen:
                seen.add(pg)
                out.append(pg)
        for _letter, pg in self.color_columns.items():
            if pg not in seen:
                seen.add(pg)
                out.append(pg)
        return out

    def project_normalized_row(self, nr: dict[str, str]) -> dict[str, str]:
        """Map normalized sheet row (header keys or pg keys) to DB column names."""
        m: dict[str, str] = {}
        if self.column_map_mode == "letter":
            for _letter, pg in self.columns.items():
                m[pg] = nr.get(pg, "")
        else:
            for src_key, pg in self.columns.items():
                m[pg] = nr.get(src_key, "")
        for _letter, pg in self.color_columns.items():
            m[pg] = nr.get(pg, "")
        return m


@dataclass(frozen=True)
class AppConfig:
    spreadsheet_id: str
    jobs: tuple[SheetSyncJob, ...]
    mapping_path: Path


def parse_columns_dict(
    cols: dict[Any, Any],
    ctx: str,
    column_mode: str | None = None,
) -> tuple[dict[str, str], str]:
    """Returns (column_map, mode) where mode is header | letter."""
    if not isinstance(cols, dict) or not cols:
        raise ValueError(f"{ctx}: columns must be a non-empty mapping")
    keys = [str(k) for k in cols.keys()]
    mode = resolve_column_mode(keys, column_mode)
    col_map: dict[str, str] = {}
    for k, pg in cols.items():
        ks = str(k).strip().upper() if mode == "letter" else str(k)
        if mode == "letter":
            if not re.match(r"^[A-Z]{1,3}$", ks):
                raise ValueError(f"{ctx}: columns key {k!r} is not a valid column letter")
        col_map[ks] = _validate_ident(str(pg), f"{ctx}.columns")
    return col_map, mode


def _parse_reading(raw: dict[str, Any] | None) -> ReadingRules:
    if not raw:
        return ReadingRules()
    toks = raw.get("error_tokens_as_empty") or []
    skip = raw.get("skip_if_empty") or []
    return ReadingRules(
        trim_strings=bool(raw.get("trim_strings", True)),
        error_tokens_as_empty=tuple(str(x) for x in toks),
        skip_if_empty=tuple(str(x) for x in skip),
    )


def load_mapping(path: Path) -> AppConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("mapping root must be a mapping")

    if raw.get("ew_sheet_rules_version") or raw.get("ew_order_rules_version"):
        return _load_ew_sheet_rules_v1(raw, path)

    sid = raw.get("spreadsheet_id")
    if not sid or not isinstance(sid, str):
        raise ValueError("spreadsheet_id is required")

    sync_list = raw.get("sync")
    if not isinstance(sync_list, list) or not sync_list:
        raise ValueError("sync must be a non-empty list")

    jobs: list[SheetSyncJob] = []
    for i, item in enumerate(sync_list):
        if not isinstance(item, dict):
            raise ValueError(f"sync[{i}] must be a mapping")
        ws = item.get("worksheet")
        ws_id = item.get("worksheet_id")
        if ws_id is not None:
            ws_id = int(ws_id)
        table = item.get("table")
        pk = item.get("primary_key")
        cols = item.get("columns")
        if not table:
            raise ValueError(f"sync[{i}]: table is required")
        if ws_id is None and not ws:
            raise ValueError(
                f"sync[{i}]: set worksheet (tab name) or worksheet_id (gid from URL)"
            )
        if not isinstance(pk, list) or not pk:
            raise ValueError(f"sync[{i}]: primary_key must be a non-empty list")
        if not isinstance(cols, dict) or not cols:
            raise ValueError(f"sync[{i}]: columns must be a non-empty mapping")

        layout = item.get("layout") or {}
        reading = _parse_reading(item.get("reading"))

        _validate_ident(str(table), f"sync[{i}].table")
        pk_t = tuple(_validate_ident(str(p), f"sync[{i}].primary_key") for p in pk)
        map_opts = item.get("mapping") or {}
        col_map, cm_mode = parse_columns_dict(
            cols, f"sync[{i}]", map_opts.get("column_mode")
        )

        for k in pk_t:
            if k not in col_map.values():
                raise ValueError(
                    f"sync[{i}]: primary_key {k!r} must appear as a values in columns"
                )

        if ws_id is not None:
            label = f"gid:{ws_id}"
        else:
            label = str(ws)

        hr = int(layout.get("header_row", item.get("header_row", 1)))
        dr = int(layout.get("data_start_row", item.get("data_start_row", hr + 1)))
        color_cols = _parse_color_columns(item.get("color_columns"), f"sync[{i}]")

        jobs.append(
            SheetSyncJob(
                label=label,
                worksheet_name=str(ws) if ws else None,
                worksheet_id=ws_id,
                table=str(table),
                primary_key=pk_t,
                columns=col_map,
                column_map_mode=cm_mode,
                header_row=hr,
                data_start_row=dr,
                reading=reading,
                color_columns=color_cols,
            )
        )

    return AppConfig(
        spreadsheet_id=sid.strip(),
        jobs=tuple(jobs),
        mapping_path=path.resolve(),
    )


def _load_ew_sheet_rules_v1(raw: dict[str, Any], path: Path) -> AppConfig:
    """Single-table rules file (EW_ORDER_RULES.yaml / EW_QUOTE_RULES.yaml style)."""
    src = raw.get("source") or {}
    sid = raw.get("spreadsheet_id") or src.get("spreadsheet_id")
    if not sid or not isinstance(sid, str):
        raise ValueError("spreadsheet_id is required (top-level or under source)")

    ws_id = src.get("worksheet_id")
    if ws_id is not None:
        ws_id = int(ws_id)
    ws_name = src.get("worksheet")
    if ws_id is None and not ws_name:
        raise ValueError("source.worksheet_id or source.worksheet is required")

    layout = raw.get("layout") or {}
    hr = int(layout.get("header_row", 1))
    dr = int(layout.get("data_start_row", hr + 1))

    pg = raw.get("postgres") or {}
    table = pg.get("table")
    pk = pg.get("primary_key")
    cols = raw.get("columns")
    if not table or not isinstance(pk, list) or not pk:
        raise ValueError("postgres.table and postgres.primary_key are required")
    if not isinstance(cols, dict) or not cols:
        raise ValueError("columns must be a non-empty mapping")

    reading = _parse_reading(raw.get("reading"))

    _validate_ident(str(table), "postgres.table")
    pk_t = tuple(_validate_ident(str(p), "postgres.primary_key") for p in pk)
    map_opts = raw.get("mapping") or {}
    col_map, cm_mode = parse_columns_dict(
        cols, "EW rules", map_opts.get("column_mode")
    )

    for k in pk_t:
        if k not in col_map.values():
            raise ValueError(
                f"primary_key {k!r} must appear as values in columns"
            )

    if ws_id is not None:
        label = f"gid:{ws_id}"
    else:
        label = str(ws_name)

    color_cols = _parse_color_columns(raw.get("color_columns"), "EW rules")

    job = SheetSyncJob(
        label=label,
        worksheet_name=str(ws_name) if ws_name else None,
        worksheet_id=ws_id,
        table=str(table),
        primary_key=pk_t,
        columns=col_map,
        column_map_mode=cm_mode,
        header_row=hr,
        data_start_row=dr,
        reading=reading,
        color_columns=color_cols,
    )

    return AppConfig(
        spreadsheet_id=sid.strip(),
        jobs=(job,),
        mapping_path=path.resolve(),
    )


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    host = os.environ.get("PGHOST", "127.0.0.1")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", os.environ.get("USER", "postgres"))
    password = os.environ.get("PGPASSWORD", "")
    db = os.environ.get("PGDATABASE", "postgres")
    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return f"postgresql://{user}@{host}:{port}/{db}"


def credentials_path() -> Path:
    p = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not p:
        raise RuntimeError(
            "Set GOOGLE_APPLICATION_CREDENTIALS to the path of your service account JSON file."
        )
    path = Path(p).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Credentials file not found: {path}")
    return path
