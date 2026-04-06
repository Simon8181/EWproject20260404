"""里程（只显示英里 mi）与 Google Maps 链接。"""

from __future__ import annotations

import re
from urllib.parse import quote

_KM_HINT = re.compile(r"\bkm\b|公里", re.IGNORECASE)
_NUM = re.compile(r"([\d,]+(?:\.\d+)?)")


def format_route_miles_display(route_note: str) -> str:
    """从 Q 列解析数字，只显示 **mi**。表内一般为英里；若单元格标为 km/公里则换算为 mi 再显示。"""
    t = (route_note or "").strip()
    if not t:
        return ""
    m = _NUM.search(t.replace(",", ""))
    if not m:
        return ""
    try:
        val = float(m.group(1).replace(",", ""))
    except ValueError:
        return ""
    if _KM_HINT.search(t):
        mi = val * 0.6213711922373348
    else:
        mi = val
    if mi >= 100:
        return f"{mi:,.0f} mi"
    return f"{mi:.1f} mi"


def google_maps_search_url(address: str) -> str:
    """单点搜索/定位。"""
    a = (address or "").strip()
    if len(a) < 2:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote(a, safe='')}"


def google_maps_directions_url(origin: str, destination: str) -> str:
    """起点 → 终点 驾车路线（地址为原文，由 Google 解析）。"""
    o = (origin or "").strip()
    d = (destination or "").strip()
    if len(o) < 2 or len(d) < 2:
        return ""
    return (
        "https://www.google.com/maps/dir/?api=1&origin="
        + quote(o, safe="")
        + "&destination="
        + quote(d, safe="")
    )
