"""订单卡片折叠行：起终点摘要、公里、A 列状态、报价摘要。"""

from __future__ import annotations

import re
from typing import Any

from function.address_display import extract_location_display_line
from function.order_zip import first_us_zip, is_valid_us_zip5, strip_us_zip_plus4_from_text
from function.order_view_html import esc


def first_nonempty_str(r: dict[str, Any], *keys: str) -> str:
    """Prefer first non-empty mapped field (e.g. Sheet 列名变更后可临时加备用键)."""
    for k in keys:
        v = r.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def summary_city_st_zip(
    *,
    formatted_google: str,
    fallback_address_blob: str,
    zip_only: str,
) -> str:
    """
    折叠行展示用：优先「City, ST 邮编」；有 Google formatted 则解析；
    否则从起运/目的正文解析；最后退回仅 5 位邮编。
    """
    z = (zip_only or "").strip()
    fg = strip_us_zip_plus4_from_text((formatted_google or "").strip())
    if fg:
        line = extract_location_display_line(fg)
        if line:
            line = strip_us_zip_plus4_from_text(line).strip()
        if line and line != "—":
            return line
    fb = strip_us_zip_plus4_from_text((fallback_address_blob or "").strip())
    if fb:
        line = extract_location_display_line(fb)
        if line:
            line = strip_us_zip_plus4_from_text(line).strip()
        if line and line != "—":
            return line
    return z if z else "—"


def summary_prefer_db_city_state_zip(
    r: dict[str, Any],
    *,
    city_key: str,
    state_key: str,
    formatted_google: str,
    fallback_address_blob: str,
    zip_only: str,
) -> str:
    """折叠行：若库中已有 Geocoding 写入的 city/state + 合法 5 位邮编，优先展示。"""
    c = str(r.get(city_key) or "").strip()
    st = str(r.get(state_key) or "").strip()
    z = (zip_only or "").strip()
    if c and st and is_valid_us_zip5(z):
        return f"{c}, {st} {z}"
    return summary_city_st_zip(
        formatted_google=formatted_google,
        fallback_address_blob=fallback_address_blob,
        zip_only=zip_only,
    )


def a_cell_badge_html(a_cell: str) -> str:
    """A 列填色：待找车 | 已经安排 | 其它视为未安排。"""
    ac = (a_cell or "").strip()
    if ac == "待找车":
        return '<span class="oc-a oc-a--wait" title="A 列填充色为红">待找车</span>'
    if ac == "已经安排":
        return '<span class="oc-a oc-a--ok" title="A 列填充色为绿">已经安排</span>'
    return '<span class="oc-a oc-a--open" title="A 列非红非绿或未填色">未安排</span>'


def summary_fold_quote_snippet(raw: str, *, max_len: int = 48) -> str:
    """折叠行单行展示：折叠空白，过长省略。"""
    t = " ".join((raw or "").split())
    if not t:
        return "—"
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return esc(t)


def summary_total_km_from_miles(miles_val: Any) -> str:
    """由 `google_distance_miles`（英里）换算公里；无则 —。"""
    if miles_val is None:
        return "—"
    s = str(miles_val).strip()
    if not s:
        return "—"
    try:
        mi = float(s)
    except (TypeError, ValueError):
        return "—"
    if mi < 0 or mi > 1e7:
        return "—"
    km = mi * 1.609344
    if km >= 100:
        return f"{km:,.0f} 公里"
    if km >= 10:
        v = f"{km:.1f}".rstrip("0").rstrip(".")
        return f"{v} 公里"
    v = f"{km:.2f}".rstrip("0").rstrip(".")
    return f"{v} 公里"


def miles_float_for_summary_km(r: dict[str, Any]) -> float | None:
    """优先数值英里列，否则从 `google_distance_text` 解析 `… mi`。"""
    v = r.get("google_distance_miles")
    if v is not None and str(v).strip() != "":
        try:
            mi = float(v)
            if 0 <= mi <= 1e7:
                return mi
        except (TypeError, ValueError):
            pass
    t = str(r.get("google_distance_text") or "").strip()
    if not t:
        return None
    m = re.search(r"([\d,.]+)\s*mi\b", t, re.IGNORECASE)
    if not m:
        return None
    try:
        mi = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    if 0 <= mi <= 1e7:
        return mi
    return None
