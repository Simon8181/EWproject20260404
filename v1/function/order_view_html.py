"""订单页通用 HTML 片段：转义、正文块、地图链接、Land use、接单区。"""

from __future__ import annotations

import html
from typing import Any

from function.maps_distance import normalize_land_use_label


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def block_body(text: str) -> str:
    raw = text or ""
    if not raw.strip():
        return '<span class="empty">—</span>'
    parts = esc(raw).split("\n")
    return "<br/>".join(parts) if len(parts) > 1 else (parts[0] if parts else '<span class="empty">—</span>')


def lane_body_link(url: str, inner_html: str, aria: str, title_hint: str = "") -> str:
    """Wrap address block in map link, or plain div if no URL."""
    title_attr = f' title="{esc(title_hint)}"' if title_hint.strip() else ""
    if not url:
        return f'<div class="oc-body"{title_attr}>{inner_html}</div>'
    return (
        '<a class="oc-body oc-lane-link" href="'
        + html.escape(url, quote=True)
        + '" target="_blank" rel="noopener noreferrer" aria-label="'
        + esc(aria)
        + '"'
        + title_attr
        + ">"
        + inner_html
        + "</a>"
    )


def addr_type_row(
    land_use: str | None,
    *,
    computed: bool,
    omitted_page: bool,
    geocode_status: str | None = None,
) -> str:
    """
    Land use：warehouse | commercial | residential | unknown（「格式化数据」技能写库）。
    computed=False：尚未补全。
    """
    if not computed:
        return (
            '<div class="oc-addr-type">'
            '<span class="oc-at-k">Land use</span>'
            '<span class="oc-at-v">—</span>'
            "</div>"
        )
    lu = normalize_land_use_label(land_use)
    extra = ""
    gs = (geocode_status or "").strip()
    if gs and gs != "OK":
        extra = f" · Geocoding: {gs}"
    title = f"Land use: {lu}{extra}" if extra else f"Land use: {lu}"
    title_attr = f' title="{esc(title)}"'
    return (
        f'<div class="oc-addr-type">'
        '<span class="oc-at-k">Land use</span>'
        f'<span class="oc-lu oc-lu--{lu}"{title_attr}>{esc(lu)}</span>'
        "</div>"
    )


def booking_section_html(
    *,
    broker: str,
    rate: str,
    carrier_mc: str,
    a_cell: str,
) -> str:
    """
    接单侧：Broker、Rate、Carriers（MC#）。A 列为「已经安排」时三者必填，缺则横幅 + 芯片高亮。
    「待找车」时尚未接单，不展示 V/W/X 映射值（避免与旧数据混淆）。
    """
    if a_cell == "待找车":
        broker = rate = carrier_mc = ""
    need = a_cell == "已经安排"
    mb = not broker.strip()
    mr = not rate.strip()
    mm = not carrier_mc.strip()
    warn = need and (mb or mr or mm)

    banner = ""
    if warn:
        banner = (
            '<div class="oc-bk-warn" role="alert">'
            "已安排：接单须填写 Broker、Rate、Carriers（MC#）。"
            "列映射见 <code>EW_ORDER_RULES.yaml</code>（默认 V/W/X，可按表调整）。"
            "</div>"
        )

    def chip(label: str, val: str, missing: bool) -> str:
        cls = "oc-chip oc-chip--miss" if missing else "oc-chip"
        inner = block_body(val) if val.strip() else '<span class="empty">—</span>'
        return f'<div class="{cls}"><span class="k">{label}</span><span class="v">{inner}</span></div>'

    bs, rs, cs = broker.strip(), rate.strip(), carrier_mc.strip()
    return (
        '<section class="oc-booking" aria-label="接单 Broker Rate Carriers">'
        "<h3>接单 · Broker / Rate / Carriers</h3>"
        + banner
        + '<div class="oc-sub">'
        + chip("Broker", bs, need and mb)
        + chip("Rate", rs, need and mr)
        + chip("Carriers（MC#）", cs, need and mm)
        + "</div></section>"
    )
