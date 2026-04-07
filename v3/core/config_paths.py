"""Path to v3 ai_sheet_rules.yaml. Runtime does not read core/rules.yaml."""

from __future__ import annotations

import os
from pathlib import Path


def core_dir() -> Path:
    return Path(__file__).resolve().parent


def ai_sheet_rules_yaml() -> Path:
    """Single file: sheet + table_load + ai. Override via V3_AI_SHEET_RULES_PATH or legacy env names."""
    raw = (
        os.environ.get("V3_AI_SHEET_RULES_PATH")
        or os.environ.get("V3_AI_RULES_PATH")
        or os.environ.get("V3_SHEET_MAPPING_PATH")
        or os.environ.get("V3_LISTENER_MAPPING_PATH")
        or os.environ.get("V3_AI_INTERFACE_RULES_PATH")
        or ""
    ).strip()
    if raw:
        p = Path(raw).expanduser()
        return p if p.is_absolute() else (core_dir().parent / p).resolve()
    return (core_dir() / "ai_sheet_rules.yaml").resolve()


def ai_rules_yaml() -> Path:
    """Alias for :func:`ai_sheet_rules_yaml`."""
    return ai_sheet_rules_yaml()


def sheet_mapping_yaml() -> Path:
    """Deprecated alias (same path; file no longer uses column mapping)."""
    return ai_sheet_rules_yaml()


def listener_mapping_yaml() -> Path:
    """Deprecated alias for :func:`ai_sheet_rules_yaml`."""
    return ai_sheet_rules_yaml()


def ai_interface_rules_yaml() -> Path:
    """Deprecated alias for :func:`ai_sheet_rules_yaml`."""
    return ai_sheet_rules_yaml()
