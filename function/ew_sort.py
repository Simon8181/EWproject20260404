"""Sort rows by ew_quote_no descending (numeric part, largest first)."""

from __future__ import annotations

import re
from typing import Any

_DIGITS = re.compile(r"\d+")


def ew_quote_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    """Higher EW number sorts first; non-numeric fall back to string."""
    s = str(row.get("ew_quote_no", "")).strip()
    parts = _DIGITS.findall(s)
    if parts:
        try:
            n = int("".join(parts))
        except ValueError:
            n = -1
    else:
        n = -1
    return (n, s)


def sort_rows_by_ew_quote_no_desc(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=ew_quote_sort_key, reverse=True)
