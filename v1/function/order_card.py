"""单张在途订单卡片 HTML（折叠摘要 + 展开详情）。"""

from __future__ import annotations

import html
from typing import Any

from function.address_display import extract_location_display_line, resolve_origin_for_order
from function.order_cargo_ft import format_cargo_density_fold, per_pallet_classes_suffix_text
from function.order_maps_enrich import maps_row_needs_attention
from function.order_zip import first_us_zip, strip_us_zip_plus4_from_text
from function.order_view_html import (
    addr_type_row,
    block_body,
    booking_section_html,
    esc,
    lane_body_link,
)
from function.order_view_summary import (
    a_cell_badge_html,
    first_nonempty_str,
    miles_float_for_summary_km,
    summary_fold_margin_block,
    summary_fold_quote_snippet,
    summary_prefer_db_city_state_zip,
    summary_fold_distance_mi_display,
)
from function.route_metrics import google_maps_directions_url, google_maps_search_url

_DIMS_CLASS_TITLE = "NMFC 密度法估算；正式以 NMFTA/承运人为准"


def _dims_section_html(dims: str, row: dict[str, Any]) -> str:
    """货物/尺寸：尺寸正文 + 每板 Class（若有）。"""
    body = (
        block_body(dims) if dims.strip() else '<span class="empty">尺寸（L×W×H 等）—</span>'
    )
    cls_note = per_pallet_classes_suffix_text(row)
    tail = (
        f'<div class="oc-dims-classes" title="{esc(_DIMS_CLASS_TITLE)}">{esc(cls_note)}</div>'
        if cls_note
        else ""
    )
    return f'<div class="oc-dims-wrap"><div class="oc-dims">{body}</div>{tail}</div>'


def render_order_card_html(r: dict[str, Any], *, maps_skill_label: str) -> str:
    """渲染一条 `ew_orders` 行对应的 `<article class="oc-card">`。"""
    ew = esc(str(r.get("ew_quote_no", "")))
    co = esc(str(r.get("quote_company", "")).strip() or "—")
    bol_raw = str(r.get("quote_bol_ref", "")).strip()
    bol_html = f'<span class="oc-bol">{esc(bol_raw)}</span>' if bol_raw else ""
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
    bk = first_nonempty_str(r, "booking_broker")
    br = first_nonempty_str(r, "booking_rate")
    cm = first_nonempty_str(r, "carrier_mc", "carriers_mc")
    booking_sec = booking_section_html(
        broker=bk,
        rate=br,
        carrier_mc=cm,
        a_cell=a_cell,
    )

    dest_combined = "\n".join(
        x for x in (dest_addr.strip(), dest_contact.strip()) if x
    )
    zf_db = first_nonempty_str(r, "ship_from_zip")
    zt_db = first_nonempty_str(r, "consignee_zip")
    raw_o_fmt = str(r.get("origin_formatted_address") or "").strip()
    raw_d_fmt = str(r.get("destination_formatted_address") or "").strip()

    origin_one_line, ship_maps_raw = resolve_origin_for_order(r)
    origin_full = (ship_maps_raw or "").strip() or ship.strip()
    origin_show = strip_us_zip_plus4_from_text(origin_full)
    dest_show = strip_us_zip_plus4_from_text(dest_combined.strip())
    o_condensed = (origin_one_line or "").strip()
    if o_condensed == "—":
        o_condensed = ""
    d_condensed = (extract_location_display_line(dest_combined.strip()) or "").strip()
    o_sum_fb = o_condensed or origin_show
    d_sum_fb = d_condensed or dest_show

    zip_o = first_us_zip(zf_db) or first_us_zip(ship) or ""
    zip_d = first_us_zip(zt_db) or first_us_zip(dest_combined) or ""
    o_sum_e = esc(
        summary_prefer_db_city_state_zip(
            r,
            city_key="ship_from_city",
            state_key="ship_from_state",
            formatted_google=raw_o_fmt,
            fallback_address_blob=o_sum_fb,
            zip_only=zip_o,
        )
    )
    d_sum_e = esc(
        summary_prefer_db_city_state_zip(
            r,
            city_key="consignee_city",
            state_key="consignee_state",
            formatted_google=raw_d_fmt,
            fallback_address_blob=d_sum_fb,
            zip_only=zip_d,
        )
    )

    href_o = str(r.get("maps_origin_href") or "").strip()
    href_d = str(r.get("maps_dest_href") or "").strip()
    href_dir = str(r.get("maps_directions_href") or "").strip()
    url_from = href_o or google_maps_search_url(ship_maps_raw)
    url_to = href_d or google_maps_search_url(dest_combined)
    url_dir = href_dir or google_maps_directions_url(ship_maps_raw, dest_combined)

    google_mi_html = "—"
    db_dist_text = str(r.get("google_distance_text") or "").strip()
    db_dist_miles = r.get("google_distance_miles")
    if db_dist_text:
        google_mi_html = esc(db_dist_text)
    elif db_dist_miles is not None and str(db_dist_miles).strip() != "":
        try:
            google_mi_html = esc(f"{float(db_dist_miles):.1f} mi")
        except (TypeError, ValueError):
            google_mi_html = "—"

    mi_fold = miles_float_for_summary_km(r)
    sum_dist_raw = summary_fold_distance_mi_display(mi_fold)
    sum_km_html = (
        f'<strong class="oc-sum-km-val">{esc(sum_dist_raw)}</strong>'
        if sum_dist_raw != "—"
        else '<span class="oc-sum-km-empty">—</span>'
    )
    sum_q_cust = summary_fold_quote_snippet(q_cust)
    sum_q_drv = summary_fold_quote_snippet(q_drv)
    margin_fold_html = summary_fold_margin_block(
        a_cell=a_cell,
        quote_customer=q_cust,
        quote_driver=q_drv,
        booking_rate=str(r.get("booking_rate") or ""),
    )
    ft_fold = format_cargo_density_fold(r.get("cargo_density_pcf"))
    sum_ft_html = (
        f'<strong class="oc-sum-ft-val">{esc(ft_fold)}</strong>'
        if ft_fold != "—"
        else '<span class="oc-sum-ft-empty">—</span>'
    )
    a_cell_html = a_cell_badge_html(a_cell)

    insight_computed = bool(str(r.get("maps_enriched_at") or "").strip())
    o_land = str(r.get("origin_land_use") or "").strip() or None
    d_land = str(r.get("destination_land_use") or "").strip() or None
    o_geo_st = str(r.get("maps_origin_geocode_status") or "").strip() or None
    d_geo_st = str(r.get("maps_dest_geocode_status") or "").strip() or None

    maps_attn = maps_row_needs_attention(r)

    fmt_o = strip_us_zip_plus4_from_text(raw_o_fmt)
    fmt_d = strip_us_zip_plus4_from_text(raw_d_fmt)
    fmt_o_block = (
        f'<div class="oc-maps-fmt" title="Geocoding 标准地址"><span class="oc-maps-fmt-k">Google</span> {esc(fmt_o)}</div>'
        if fmt_o
        else ""
    )
    fmt_d_block = (
        f'<div class="oc-maps-fmt" title="Geocoding 标准地址"><span class="oc-maps-fmt-k">Google</span> {esc(fmt_d)}</div>'
        if fmt_d
        else ""
    )

    body_from = (
        lane_body_link(
            url_from,
            block_body(origin_show),
            "在 Google 地图打开起点",
            title_hint=origin_show,
        )
        + fmt_o_block
    )
    body_to = lane_body_link(
        url_to,
        block_body(dest_show),
        "在 Google 地图打开终点",
        title_hint="",
    ) + fmt_d_block
    row_from_types = addr_type_row(
        o_land,
        computed=insight_computed,
        omitted_page=False,
        geocode_status=o_geo_st,
    )
    row_to_types = addr_type_row(
        d_land,
        computed=insight_computed,
        omitted_page=False,
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

    attn_cls = " oc-card--maps-attention" if maps_attn else ""
    need_banner = ""
    if maps_attn:
        err_hint = str(r.get("maps_enrich_error") or "").strip()
        extra = f"（{esc(err_hint)}）" if err_hint else ""
        need_banner = (
            f'<div class="oc-maps-need" role="status">'
            f"<strong>待解决</strong>：距离 / 地址类型 / 地图链接未齐，请点击上方「{maps_skill_label}」或核对地址。{extra}"
            f"</div>"
        )

    return f"""
    <article class="oc-card{attn_cls}">
      <details class="oc-card__details">
        <summary class="oc-card__sum">
          <div class="oc-sum-top">
            <span class="oc-sum-no">{ew or "—"}</span>
            <span class="oc-sum-zips">{o_sum_e} <span class="oc-zsep">→</span> {d_sum_e}</span>
            <span class="oc-sum-client" title="客户公司（Sheet B 列）">{co}</span>
          </div>
          <div class="oc-sum-extra" aria-label="是否安排、总里程、Ft、客户报价、司机价、差价（同一行，窄屏可换行）">
            <span class="oc-sum-arr">{a_cell_html}</span>
            <span class="oc-sum-km" title="Google 驾车距离（mi），与下方「里程」一致">{sum_km_html}</span>
            <span class="oc-sum-ft" title="货物密度 lb/ft³（L÷体积 ft³；N 列 m³ 或 M 列长×宽×高）"><span class="oc-sum-ql">Ft</span>{sum_ft_html}</span>
            <span class="oc-sum-p"><span class="oc-sum-ql">客户报价</span>{sum_q_cust}</span>
            <span class="oc-sum-u"><span class="oc-sum-ql">司机价</span>{sum_q_drv}</span>
            {margin_fold_html}
          </div>
        </summary>
        <div class="oc-card__inner">
      {need_banner}
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
          <div class="oc-chip"><span class="k">客户 P</span><span class="v">{block_body(q_cust) if q_cust.strip() else "—"}</span></div>
          <div class="oc-chip"><span class="k">司机 U</span><span class="v">{block_body(q_drv) if q_drv.strip() else "—"}</span></div>
          <div class="oc-chip oc-chip-muted"><span class="k">其他费用</span><span class="v">网页追加录入（见 order_fee_addons）</span></div>
        </div>
      </section>
      {booking_sec}
      <section class="oc-load" aria-label="货物与尺寸">
        <h3>货物 / 尺寸</h3>
        {_dims_section_html(dims, r)}
        <div class="oc-sub">
          <div class="oc-chip"><span class="k">品名</span><span class="v">{block_body(goods) if goods.strip() else "—"}</span></div>
          <div class="oc-chip"><span class="k">货值</span><span class="v">{block_body(cargo_val) if cargo_val.strip() else "—"}</span></div>
          <div class="oc-chip"><span class="k">体积 m³</span><span class="v">{esc(vol) if vol.strip() else "—"}</span></div>
          <div class="oc-chip"><span class="k">重量 lbs</span><span class="v">{block_body(wlb) if wlb.strip() else "—"}</span></div>
        </div>
      </section>
      <footer class="oc-foot">
        <span class="oc-st">{esc(status)}</span>
        {f'<span class="oc-dat">{esc(dat)}</span>' if dat.strip() else ""}
      </footer>
        </div>
      </details>
    </article>
            """
