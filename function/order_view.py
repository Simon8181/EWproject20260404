"""Card-style HTML for `/f/read/order` — highlights 起运、目的、货物与尺寸。"""

from __future__ import annotations

import html
import os
import re
from typing import Any

from function.address_display import resolve_origin_for_order
from function.api_config import ew_admin_order_sync_label, google_maps_api_key, reload_api_env
from function.dat_theme import LAYOUT_SHELL_CSS, ORDER_PAGE_CSS
from function.web_nav import render_sidebar_nav
from function.maps_distance import (
    RouteInsightResult,
    fetch_route_insight,
    normalize_land_use_label,
)
from function.route_metrics import google_maps_directions_url, google_maps_search_url


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _first_nonempty_str(r: dict[str, Any], *keys: str) -> str:
    """Prefer first non-empty mapped field (e.g. Sheet 列名变更后可临时加备用键)."""
    for k in keys:
        v = r.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _booking_section_html(
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
        inner = _block_body(val) if val.strip() else '<span class="empty">—</span>'
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


def _pick_line_for_geocode(blob: str) -> str:
    """
    Geocoding 对多行「地址+联系人」整段查询易 ZERO_RESULTS；优先含邮编/门牌的一行。
    驾车距离仍用全文（Distance Matrix 更宽松）。
    """
    raw = (blob or "").strip()
    if not raw:
        return ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return lines[0] if lines else ""
    zip_us = re.compile(r"\b\d{5}(-\d{4})?\b")
    for ln in lines:
        if zip_us.search(ln) and len(ln) >= 8:
            return ln
    for ln in lines:
        if re.match(r"^\d+\s+\S", ln):
            return ln
    for ln in lines:
        if "," in ln and any(ch.isdigit() for ch in ln):
            return ln
    return lines[0]


def _order_google_miles_max() -> int:
    try:
        return max(0, int(os.environ.get("ORDER_GOOGLE_MILES_MAX", "30")))
    except ValueError:
        return 30


def _addr_type_row(
    land_use: str | None,
    *,
    computed: bool,
    omitted_page: bool,
    geocode_status: str | None = None,
) -> str:
    """
    仅展示并高亮 Land use：warehouse | commercial | residential | unknown（由 Maps 映射并写入 ri）。
    computed=False：未请求；omitted_page=True：本页省略在线请求。
    """
    if not computed:
        hint = ""
        if omitted_page:
            hint = ' title="本页订单过多，已省略在线 Land use；可调 ORDER_GOOGLE_MILES_MAX 或减小 limit"'
        return (
            f'<div class="oc-addr-type"{hint}>'
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
    title_attr = f' title="{_esc(title)}"'
    return (
        f'<div class="oc-addr-type">'
        '<span class="oc-at-k">Land use</span>'
        f'<span class="oc-lu oc-lu--{lu}"{title_attr}>{_esc(lu)}</span>'
        "</div>"
    )


def _maps_debug_panel_html(
    *,
    maps_on: bool,
    g_max: int,
    nrows: int,
    ship_maps_raw: str,
    dest_combined: str,
    insight_computed: bool,
    insight_omitted: bool,
    ri: RouteInsightResult | None,
    idx: int,
) -> str:
    """首行 Maps 调用条件与 API 返回（?debug_maps=1）。"""
    if not maps_on:
        why = "原因：进程内仍无有效 GOOGLE_MAPS_API_KEY（检查 .env 无弯引号、已保存；或 config/google_maps_api_key.txt）"
    elif not ship_maps_raw.strip() or not dest_combined.strip():
        why = "原因：首行起运或目的为空"
    elif idx >= g_max:
        why = f"原因：行号 {idx} ≥ ORDER_GOOGLE_MILES_MAX（{g_max}）"
    else:
        why = "条件满足，应已调用 fetch_route_insight"
    lines = [
        "本页渲染前已执行 reload_api_env()（从磁盘重载 .env / api.secrets.env / ew_settings.env）",
        f"GOOGLE_MAPS_API_KEY: {'已配置' if maps_on else '未配置 — 不会请求距离/地址类型'}",
        f"ORDER_GOOGLE_MILES_MAX={g_max}（仅前 {g_max} 行会调 Maps）",
        f"本页行数={nrows}",
        "--- 首行 ---",
        f"ship_maps_raw 非空={bool(ship_maps_raw.strip())} len={len(ship_maps_raw.strip())}",
        f"dest_combined 非空={bool(dest_combined.strip())} len={len(dest_combined.strip())}",
        f"insight_computed={insight_computed} · {why}",
        f"insight_omitted（行号超限）={insight_omitted}",
    ]
    if ri is not None:
        lines.extend(
            [
                f"ri.ok={ri.ok}",
                f"matrix: google_status={ri.google_distance_status} element={ri.element_status!r}",
                f"geocode: origin={ri.origin_geocode_status} destination={ri.destination_geocode_status}",
                f"land_use: origin={ri.origin_land_use!r} destination={ri.destination_land_use!r}",
                f"distance_text={ri.distance_text!r} distance_miles={ri.distance_miles!r}",
                f"error_message={ri.error_message!r}",
            ]
        )
        if ri.google_distance_status == "OK" and ri.element_status == "OK":
            o_st, d_st = ri.origin_geocode_status, ri.destination_geocode_status
            if o_st == "REQUEST_DENIED" and d_st == "REQUEST_DENIED":
                lines.append(
                    "提示：矩阵成功但两端 Geocoding 均为 REQUEST_DENIED → 在 GCP 启用「Geocoding API」"
                    "；若密钥设了 API 限制，请把 Geocoding 加入允许列表（与 Distance Matrix 分开）"
                )
            elif (o_st == "REQUEST_DENIED") != (d_st == "REQUEST_DENIED"):
                side = "起点" if o_st == "REQUEST_DENIED" else "终点"
                lines.append(
                    f"提示：矩阵成功，仅{side} Geocoding 末次为 REQUEST_DENIED（另一为 OK）"
                    "→ API 一般已可用；多为该侧多候选均未解析成功或瞬时配额/重试问题，可核对该侧文案或稍后刷新"
                )
    else:
        lines.append("ri=None（未进入 fetch_route_insight）")
    inner = "\n".join(lines)
    return (
        '<aside class="oc-debug" aria-label="Maps 调试">'
        "<strong>Maps 调试</strong>（加 <code>?debug_maps=1</code> 显示；勿在生产长期开启）"
        f"<pre>{_esc(inner)}</pre>"
        "</aside>"
    )


def render_order_page(
    rows: list[dict[str, Any]],
    *,
    debug_maps: bool = False,
    sync_flash_err: str | None = None,
    sync_flash_ok: str | None = None,
    last_synced: str | None = None,
    show_sync_form: bool = False,
    db_fallback_warning: str | None = None,
    order_sync_prefilled_token: str | None = None,
    order_sync_via_session: bool = False,
    session_user: str | None = None,
    role: str | None = None,
) -> str:
    """渲染前重载 env，避免 uvicorn 长驻进程仍用旧环境（改 .env 后无需重启即可试 Maps）。"""
    reload_api_env()
    admin_sync_label = ew_admin_order_sync_label()
    cards: list[str] = []
    g_max = _order_google_miles_max()
    maps_on = bool(google_maps_api_key())
    maps_debug_html = ""
    nrows = len(rows)
    for idx, r in enumerate(rows):
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
        q_cust = str(r.get("quote_customer", ""))
        q_drv = str(r.get("quote_driver", ""))
        bk = _first_nonempty_str(r, "booking_broker")
        br = _first_nonempty_str(r, "booking_rate")
        cm = _first_nonempty_str(r, "carrier_mc", "carriers_mc")
        booking_sec = _booking_section_html(
            broker=bk,
            rate=br,
            carrier_mc=cm,
            a_cell=a_cell,
        )

        dest_combined = "\n".join(
            x for x in (dest_addr.strip(), dest_contact.strip()) if x
        )

        # 地图链接仍用 resolve 后的原文；卡片上展示完整起运文案（提货回退时为整段提货地址）
        _, ship_maps_raw = resolve_origin_for_order(r)
        origin_full = (ship_maps_raw or "").strip() or ship.strip()

        url_from = google_maps_search_url(ship_maps_raw)
        url_to = google_maps_search_url(dest_combined)
        url_dir = google_maps_directions_url(ship_maps_raw, dest_combined)

        google_mi_html = "—"
        o_geo_st: str | None = None
        d_geo_st: str | None = None
        o_land: str | None = None
        d_land: str | None = None
        insight_computed = False
        insight_omitted = maps_on and idx >= g_max
        ri: RouteInsightResult | None = None

        if maps_on and idx < g_max and ship_maps_raw.strip() and dest_combined.strip():
            geo_o = _pick_line_for_geocode(ship_maps_raw) or ship_maps_raw.strip()
            geo_d = _pick_line_for_geocode(dest_combined) or dest_combined.strip()
            ri = fetch_route_insight(
                ship_maps_raw,
                dest_combined,
                origin_for_geocode=geo_o,
                destination_for_geocode=geo_d,
            )
            insight_computed = True
            o_geo_st, d_geo_st = ri.origin_geocode_status, ri.destination_geocode_status
            o_land, d_land = ri.origin_land_use, ri.destination_land_use
            if ri.ok and ri.distance_text:
                google_mi_html = _esc(ri.distance_text)
            elif ri.ok and ri.distance_miles is not None:
                google_mi_html = _esc(f"{ri.distance_miles:.1f} mi")
        elif maps_on and idx >= g_max:
            google_mi_html = '<span class="empty" title="本页订单过多，已省略在线算距；可改 ORDER_GOOGLE_MILES_MAX 或调小 limit">—</span>'

        if debug_maps and idx == 0:
            maps_debug_html = _maps_debug_panel_html(
                maps_on=maps_on,
                g_max=g_max,
                nrows=nrows,
                ship_maps_raw=ship_maps_raw,
                dest_combined=dest_combined,
                insight_computed=insight_computed,
                insight_omitted=insight_omitted,
                ri=ri,
                idx=idx,
            )

        body_from = _lane_body_link(
            url_from,
            _block_body(origin_full),
            "在 Google 地图打开起点",
            title_hint=origin_full,
        )
        body_to = _lane_body_link(
            url_to,
            _block_body(dest_combined.strip()),
            "在 Google 地图打开终点",
            title_hint="",
        )
        row_from_types = _addr_type_row(
            o_land,
            computed=insight_computed,
            omitted_page=insight_omitted,
            geocode_status=o_geo_st,
        )
        row_to_types = _addr_type_row(
            d_land,
            computed=insight_computed,
            omitted_page=insight_omitted,
            geocode_status=d_geo_st,
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
            # 其它填色/空白/未识别：视为未安排（与 Sheet 文档「其它为空」一致）
            a_cell_html = '<span class="oc-a oc-a--open" title="A 列非红非绿或未填色">未安排</span>'

        cards.append(
            f"""
    <article class="oc-card">
      <header class="oc-head">
        <span class="oc-ew">{ew or "—"}</span>
        <div class="oc-meta">
          {a_cell_html}
          <span class="oc-co">{co}</span>
          {bol_html}
        </div>
      </header>
      <div class="oc-grid oc-grid-3" role="group" aria-label="起运、路线、目的">
        <section class="oc-lane oc-from" aria-label="起运">
          <h3>起运</h3>
          {body_from}
          {row_from_types}
        </section>
        <div class="oc-mid-route">{mid_route}</div>
        <section class="oc-lane oc-to" aria-label="目的">
          <h3>目的</h3>
          {body_to}
          {row_to_types}
        </section>
      </div>
      <section class="oc-route" aria-label="里程">
        <h3>里程</h3>
        <div class="oc-km">
          <span class="oc-km-label">Google 驾车</span>
          <div class="oc-km-val">{google_mi_html}</div>
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
      {booking_sec}
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

    body_cards = (
        "".join(cards)
        if cards
        else '<p class="oc-empty">暂无订单数据。请确认已执行 <code>db/schema_order.sql</code> 建表，并在上方「从 Sheet 刷新」将 Google 表写入数据库（<code>ew_quote_no</code> 存在则更新）。</p>'
    )

    return (
        """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="theme-color" content="#0f172a"/>
  <title>下单 · Order</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700&amp;display=swap" rel="stylesheet"/>
  <style>
"""
        + LAYOUT_SHELL_CSS
        + ORDER_PAGE_CSS
        + """
  </style>
</head>
<body>
  <div class="ew-shell">
"""
        + render_sidebar_nav("order", session_user=session_user, role=role)
        + """
    <main class="ew-main">
      <div class="oc-wrap">
        <div class="oc-top">
          <h1><span class="oc-brand">下单</span><span class="oc-title-sub"> · 在途订单</span></h1>
          <div class="oc-top-actions">
"""
        + (
            (
                '<p class="oc-sync-meta">当前列表来自 <strong>Google Sheet 直连</strong>；数据库恢复后将改为读取 <code>ew_orders</code>。</p>'
                '<p class="oc-sync-meta oc-sync-meta--muted">「从 Sheet 刷新」需数据库可用；并请在 <code>config/api.secrets.env</code> 配置 <code>EW_ADMIN_TOKEN</code> 后重启服务，再使用刷新。</p>'
            )
            if db_fallback_warning
            else (
                f'<p class="oc-sync-meta">列表来自数据库 <code>ew_orders</code>（<code>ew_quote_no</code> 主键）'
                + (f"；最近同步：{_esc(last_synced)}" if last_synced else "；尚未同步或表为空")
                + "</p>"
            )
        )
        + (
            (
                f"""
            <form class="oc-sync-form oc-sync-form--inline" method="post" action="/f/read/order/sync">
              <span class="oc-sync-admin" title="管理员书签：URL 带 ?token= 与 /admin 相同">{_esc(admin_sync_label)}</span>
              <input type="hidden" name="token" value="{_esc(order_sync_prefilled_token)}"/>
              <button type="submit" class="oc-sync-btn">从 Sheet 刷新</button>
            </form>
            """
                if show_sync_form and order_sync_prefilled_token
                else (
                    f"""
            <form class="oc-sync-form oc-sync-form--inline" method="post" action="/f/read/order/sync">
              <span class="oc-sync-admin" title="已登录：与 /login 相同会话">{_esc(admin_sync_label)}</span>
              <button type="submit" class="oc-sync-btn">从 Sheet 刷新</button>
            </form>
            """
                    if show_sync_form and order_sync_via_session
                    else (
                        """
            <form class="oc-sync-form" method="post" action="/f/read/order/sync">
              <label class="oc-sync-token"><span>令牌</span>
                <input type="password" name="token" autocomplete="current-password" placeholder="EW_ADMIN_TOKEN" required/>
              </label>
              <button type="submit" class="oc-sync-btn">从 Sheet 刷新</button>
            </form>
            """
                        if show_sync_form
                        else (
                            ""
                            if db_fallback_warning
                            else '<p class="oc-sync-meta oc-sync-meta--muted">刷新需 <code>EW_ADMIN_TOKEN</code>（写入 <code>config/api.secrets.env</code> 后重启服务），或<a href="/login?next=%2Ff%2Fread%2Forder%3Ffmt%3Dhtml">登录</a>。</p>'
                        )
                    )
                )
            )
        )
        + """
          </div>
        </div>
"""
        + (
            f'<p class="oc-sync-flash oc-sync-flash--ok" role="status">{_esc(sync_flash_ok)}</p>'
            if sync_flash_ok
            else ""
        )
        + (
            f'<p class="oc-sync-flash oc-sync-flash--err" role="alert">{_esc(sync_flash_err)}</p>'
            if sync_flash_err
            else ""
        )
        + (
            f'<p class="oc-db-fallback" role="alert">{_esc(db_fallback_warning)}</p>'
            if db_fallback_warning
            else ""
        )
        + (
            '<p class="oc-maps-hint">未配置 <code>GOOGLE_MAPS_API_KEY</code>：驾车距离与地址类型不会加载。调试请加 URL 参数 <code>?debug_maps=1</code>。</p>'
            if (not maps_on and nrows > 0)
            else ""
        )
        + maps_debug_html
        + body_cards
        + """
      </div>
    </main>
  </div>
</body>
</html>
"""
    )
