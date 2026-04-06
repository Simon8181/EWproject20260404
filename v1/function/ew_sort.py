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


def a_cell_arrangement_priority(row: dict[str, Any]) -> int:
    """下单页排序：未安排（含空）最先 → 待找车 → 已经安排。数值越小越靠前。"""
    a = str(row.get("a_cell_status", "")).strip()
    if a in ("", "未安排"):
        return 0
    if a == "待找车":
        return 1
    if a == "已经安排":
        return 2
    return 0


def sort_order_rows_for_display(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """未安排优先；同状态内 EW 报价号降序（大号在上）。"""
    return sorted(
        rows,
        key=lambda r: (a_cell_arrangement_priority(r),) + (-ew_quote_sort_key(r)[0], ew_quote_sort_key(r)[1]),
    )
