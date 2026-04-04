"""Card-style HTML for `/f/read/order` — highlights 起运、目的、货物与尺寸。"""

from __future__ import annotations

import html
from typing import Any

from function.address_display import resolve_origin_for_order
from function.dat_theme import ORDER_PAGE_CSS
from function.route_metrics import (
    format_route_miles_display,
    google_maps_directions_url,
    google_maps_search_url,
)


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _block_body(text: str) -> str:
    raw = text or ""
    if not raw.strip():
        return '<span class="empty">—</span>'
    parts = _esc(raw).split("\n")
    return "<br/>".join(parts) if len(parts) > 1 else (parts[0] if parts else '<span class="empty">—</span>')


def _lane_body_link(url: str, inner_html: str, aria: str, title_hint: str = "") -> str:
    """Wrap address block in map link, or plain div if no URL."""
    title_attr = (
        f' title="{_esc(title_hint)}"' if title_hint.strip() else ""
    )
    if not url:
        return f'<div class="oc-body"{title_attr}>{inner_html}</div>'
    return (
        '<a class="oc-body oc-lane-link" href="'
        + html.escape(url, quote=True)
        + '" target="_blank" rel="noopener noreferrer" aria-label="'
        + _esc(aria)
        + '"'
        + title_attr
        + ">"
        + inner_html
        + "</a>"
    )


def render_order_page(rows: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for r in rows:
        ew = _esc(str(r.get("ew_quote_no", "")))
        co = _esc(str(r.get("quote_company", "")).strip() or "—")
        bol_raw = str(r.get("quote_bol_ref", "")).strip()
        bol_html = f'<span class="oc-bol">{_esc(bol_raw)}</span>' if bol_raw else ""
        ship = str(r.get("ship_from", ""))
        dest_addr = str(r.get("consignee_address", ""))
        dest_contact = str(r.get("consignee_contact", ""))
        goods = str(r.get("goods_description", ""))
        dims = str(r.get("dimensions_class", ""))
        cargo_val = str(r.get("cargo_value_note", ""))
        vol = str(r.get("volume_m3", ""))
        wlb = str(r.get("weight_lbs", ""))
        status = str(r.get("status_text", ""))
        dat = str(r.get("dat_post_status", ""))
        a_cell = str(r.get("a_cell_status", "")).strip()
        route_note = str(r.get("route_miles_note", ""))
        q_cust = str(r.get("quote_customer", ""))
        q_drv = str(r.get("quote_driver", ""))

        dest_combined = "\n".join(
            x for x in (dest_addr.strip(), dest_contact.strip()) if x
        )

        # 起始地：解析 City+ZIP（ship_from 无地址时回退提货段）；地图用解析出的原文
        ship_show, ship_maps_raw = resolve_origin_for_order(r)

        miles_line = format_route_miles_display(route_note)
        url_from = google_maps_search_url(ship_maps_raw)
        url_to = google_maps_search_url(dest_combined)
        url_dir = google_maps_directions_url(ship_maps_raw, dest_combined)

        body_from = _lane_body_link(
            url_from,
            _block_body(ship_show),
            "在 Google 地图打开起点",
            title_hint=ship_maps_raw.strip() or ship.strip(),
        )
        body_to = _lane_body_link(
            url_to,
            _block_body(dest_combined.strip()),
            "在 Google 地图打开终点",
            title_hint="",
        )
        if url_dir:
            mid_route = (
                '<a class="oc-route-mid" href="'
                + html.escape(url_dir, quote=True)
                + '" target="_blank" rel="noopener noreferrer" aria-label="Google 地图：起点到终点路线">路线</a>'
            )
        else:
            mid_route = '<span class="oc-route-mid oc-route-mid--off" title="需填写起运与目的地址">—</span>'

        if a_cell == "待找车":
            a_cell_html = '<span class="oc-a oc-a--wait" title="A 列填充色为红">待找车</span>'
        elif a_cell == "已经安排":
            a_cell_html = '<span class="oc-a oc-a--ok" title="A 列填充色为绿">已经安排</span>'
        else:
            a_cell_html = ""

        cards.append(
            f"""
    <article class="oc-card">
      <header class="oc-head">
        <span class="oc-ew">{ew or "—"}</span>
        <div class="oc-meta">
          <span class="oc-co">{co}</span>
          {bol_html}
          {a_cell_html}
        </div>
      </header>
      <div class="oc-grid oc-grid-3" role="group" aria-label="起运、路线、目的">
        <section class="oc-lane oc-from" aria-label="起运">
          <h3>起运</h3>
          {body_from}
        </section>
        <div class="oc-mid-route">{mid_route}</div>
        <section class="oc-lane oc-to" aria-label="目的">
          <h3>目的</h3>
          {body_to}
        </section>
      </div>
      <section class="oc-route" aria-label="里程">
        <h3>里程</h3>
        <div class="oc-km">
          <span class="oc-km-label">Mi</span>
          <div class="oc-km-val">{_esc(miles_line) if miles_line else "—"}</div>
        </div>
      </section>
      <section class="oc-pnl" aria-label="报价与费用">
        <h3>报价</h3>
        <div class="oc-sub">
          <div class="oc-chip"><span class="k">客户 P</span><span class="v">{_block_body(q_cust) if q_cust.strip() else "—"}</span></div>
          <div class="oc-chip"><span class="k">司机 U</span><span class="v">{_block_body(q_drv) if q_drv.strip() else "—"}</span></div>
          <div class="oc-chip oc-chip-muted"><span class="k">其他费用</span><span class="v">网页追加录入（见 order_fee_addons）</span></div>
        </div>
      </section>
      <section class="oc-load" aria-label="货物与尺寸">
        <h3>货物 / 尺寸</h3>
        <div class="oc-dims">{_block_body(dims) if dims.strip() else '<span class="empty">尺寸（L×W×H 等）—</span>'}</div>
        <div class="oc-sub">
          <div class="oc-chip"><span class="k">品名</span><span class="v">{_block_body(goods) if goods.strip() else "—"}</span></div>
          <div class="oc-chip"><span class="k">货值</span><span class="v">{_block_body(cargo_val) if cargo_val.strip() else "—"}</span></div>
          <div class="oc-chip"><span class="k">体积 m³</span><span class="v">{_esc(vol) if vol.strip() else "—"}</span></div>
          <div class="oc-chip"><span class="k">重量 lbs</span><span class="v">{_block_body(wlb) if wlb.strip() else "—"}</span></div>
        </div>
      </section>
      <footer class="oc-foot">
        <span class="oc-st">{_esc(status)}</span>
        {f'<span class="oc-dat">{_esc(dat)}</span>' if dat.strip() else ""}
      </footer>
    </article>
            """
        )

    body_cards = "".join(cards) if cards else '<p class="oc-empty">暂无数据。</p>'

    return (
        """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="theme-color" content="#ff6600"/>
  <title>下单 · Order</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700&amp;display=swap" rel="stylesheet"/>
  <style>
"""
        + ORDER_PAGE_CSS
        + """
  </style>
</head>
<body>
  <div class="oc-wrap">
    <div class="oc-top">
      <h1><span class="oc-brand">下单</span><span class="oc-title-sub"> · 在途订单</span></h1>
      <a href="/">← 返回主页</a>
    </div>
"""
        + body_cards
        + """
  </div>
</body>
</html>
"""
    )
