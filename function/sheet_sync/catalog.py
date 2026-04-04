from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# function/sheet_sync/catalog.py → parents[2] = EW project root
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def catalog_path() -> Path:
    return project_root() / "EW_CATALOG.yaml"


def load_catalog() -> dict[str, Any]:
    p = catalog_path()
    if not p.is_file():
        raise FileNotFoundError(f"Catalog not found: {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("EW_CATALOG.yaml root must be a mapping")
    return raw


def _normalize_key(s: str) -> str:
    return " ".join(s.strip().split())


def find_sheet_entry(catalog: dict[str, Any], key: str) -> tuple[str, dict[str, Any]]:
    """Return (sheet_id, entry) for logical id, route, or alias."""
    key_n = _normalize_key(key)
    sheets = catalog.get("sheets")
    if not isinstance(sheets, dict):
        raise ValueError("EW_CATALOG.yaml: sheets must be a mapping")

    if key_n in sheets:
        return key_n, sheets[key_n]

    for sid, entry in sheets.items():
        if not isinstance(entry, dict):
            continue
        for r in entry.get("routes", []) or []:
            if _normalize_key(str(r)) == key_n:
                return sid, entry
        for a in entry.get("aliases_zh", []) or []:
            if _normalize_key(str(a)) == key_n:
                return sid, entry
        for a in entry.get("aliases_en", []) or []:
            if _normalize_key(str(a)).lower() == key_n.lower():
                return sid, entry

    raise KeyError(
        f"No sheet matches {key!r}; see EW_CATALOG.yaml sheets.* and routes/aliases"
    )


def resolve_rules_for_sheet(key: str) -> Path:
    _, entry = find_sheet_entry(load_catalog(), key)
    rel = entry.get("rules_file")
    if not rel:
        raise ValueError(f"Sheet entry missing rules_file: {key!r}")
    path = project_root() / str(rel).lstrip("/")
    if not path.is_file():
        raise FileNotFoundError(f"Rules file from catalog: {path}")
    return path


def get_google_for_sheet(key: str) -> tuple[str, int | None, str | None]:
    """spreadsheet_id, worksheet_id (gid), tab_title_hint."""
    _, entry = find_sheet_entry(load_catalog(), key)
    g = entry.get("google") or {}
    sid = g.get("spreadsheet_id")
    if not sid:
        raise ValueError(f"Catalog entry missing google.spreadsheet_id for {key!r}")
    wid = g.get("worksheet_id")
    if wid is not None:
        wid = int(wid)
    hint = g.get("tab_title_hint") or g.get("worksheet_title_hint")
    return str(sid), wid, str(hint) if hint else None
