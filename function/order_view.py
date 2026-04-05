"""Card-style HTML for `/f/read/order` — highlights 起运、目的、货物与尺寸。"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from function.api_config import ew_admin_order_sync_label, google_maps_api_key, reload_api_env
from function.auth_roles import normalize_role
from function.dat_theme import LAYOUT_SHELL_CSS, ORDER_PAGE_CSS
from function.order_card import render_order_card_html
from function.order_maps_enrich import maps_debug_first_row_db_lines
from function.order_view_html import esc as _esc
from function.web_nav import render_sidebar_nav

# 订单页技能（原「Google Map」）：邮编规范化、里程、标准地址、地图链接等
ORDER_FORMAT_DATA_SKILL_LABEL = "格式化数据（规范化邮编）"



_PER_PAGE_CHOICES: tuple[int, ...] = (10, 20, 50, 100)


def render_peidan_page(
    *,
    session_user: str | None = None,
    role: str | None = None,
    back_token: str | None = None,
) -> str:
    """配单技能占位页：与下单页相同登录/令牌规则。"""
    reload_api_env()
    q: dict[str, str] = {"fmt": "html"}
    if (back_token or "").strip():
        q["token"] = (back_token or "").strip()
    order_href = "/f/read/order?" + urlencode(q)

    return (
        """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="theme-color" content="#0f172a"/>
  <title>配单 · 技能</title>
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
        + f"""
    <main class="ew-main">
      <div class="oc-wrap">
        <div class="oc-top">
          <div class="oc-top-head">
          <a class="oc-home-link" href="/">首页</a>
          <h1><span class="oc-brand">配单</span><span class="oc-title-sub"> · 技能</span></h1>
          </div>
        </div>
        <p class="oc-peidan-intro">
          此处为「配单」技能入口的占位页：后续可在此编排承运匹配、报价与派车等业务流程。
        </p>
        <p class="oc-peidan-actions">
          <a class="oc-peidan-back" href="{_esc(order_href)}">← 返回在途订单</a>
        </p>
      </div>
    </main>
  </div>
</body>
</html>
"""
    )


def render_order_pagination_nav(
    *,
    page: int,
    per_page: int,
    total: int,
    preserved_query: dict[str, str],
) -> str:
    """底部分页：保留 fmt、token、debug_maps 等查询参数；可点选每页条数。"""
    if total <= 0:
        return ""
    total_pages = max(1, (total + per_page - 1) // per_page)
    qbase = {k: v for k, v in preserved_query.items() if k not in ("page", "per_page")}
    qbase.setdefault("fmt", "html")

    def href(p: int) -> str:
        qq = {**qbase, "page": str(p), "per_page": str(per_page)}
        return "/f/read/order?" + urlencode(qq)

    def href_per_page(n: int) -> str:
        """切换每页条数时回到第 1 页，避免页码越界。"""
        qq = {**qbase, "page": "1", "per_page": str(n)}
        return "/f/read/order?" + urlencode(qq)

    size_links: list[str] = []
    for n in _PER_PAGE_CHOICES:
        if n == per_page:
            size_links.append(f'<span class="oc-pg-sz oc-pg-sz--on">{n}</span>')
        else:
            size_links.append(
                f'<a class="oc-pg-sz" href="{_esc(href_per_page(n))}">{n}</a>'
            )
    if per_page not in _PER_PAGE_CHOICES:
        size_links.append(
            f'<span class="oc-pg-sz oc-pg-sz--custom" title="当前 URL 指定的每页条数">{per_page}</span>'
        )

    sizes_html = (
        '<div class="oc-pg-sizes" role="group" aria-label="每页条数">'
        '<span class="oc-pg-sz-label">每页</span>'
        + "".join(size_links)
        + "</div>"
    )

    h_first = _esc(href(1))
    h_prev = _esc(href(max(1, page - 1)))
    h_next = _esc(href(min(total_pages, page + 1)))
    h_last = _esc(href(total_pages))

    prev_off = page <= 1
    next_off = page >= total_pages
    nav_prev = (
        f'<span class="oc-pg-link oc-pg-link--off" aria-disabled="true">上一页</span>'
        if prev_off
        else f'<a class="oc-pg-link" href="{h_prev}" rel="prev">上一页</a>'
    )
    nav_next = (
        f'<span class="oc-pg-link oc-pg-link--off" aria-disabled="true">下一页</span>'
        if next_off
        else f'<a class="oc-pg-link" href="{h_next}" rel="next">下一页</a>'
    )
    nav_first = (
        '<span class="oc-pg-link oc-pg-link--off" aria-disabled="true">«</span>'
        if prev_off
        else f'<a class="oc-pg-link" href="{h_first}" aria-label="第一页">«</a>'
    )
    nav_last = (
        '<span class="oc-pg-link oc-pg-link--off" aria-disabled="true">»</span>'
        if next_off
        else f'<a class="oc-pg-link" href="{h_last}" aria-label="末页">»</a>'
    )
    return (
        f'<nav class="oc-pagination" aria-label="分页">'
        f'<div class="oc-pg-top">'
        f'<span class="oc-pg-meta">共 <strong>{total}</strong> 条 · '
        f"第 <strong>{page}</strong> / {total_pages} 页</span>"
        f"{sizes_html}"
        f"</div>"
        f'<div class="oc-pg-btns">'
        f"{nav_first}"
        f"{nav_prev}"
        f"{nav_next}"
        f"{nav_last}"
        f"</div>"
        f"</nav>"
    )


def _maps_debug_panel_html(
    *,
    maps_on: bool,
    nrows: int,
    first_row: dict[str, Any] | None,
) -> str:
    """?debug_maps=1：首行数据库中的 Maps 缓存（页面不发起在线请求）。"""
    lines = [
        "本页渲染前已执行 reload_api_env()",
        f"GOOGLE_MAPS_API_KEY: {'已配置' if maps_on else '未配置（「格式化数据」不可用）'}",
        f"本页行数={nrows}",
        "--- 首行 DB ---",
        maps_debug_first_row_db_lines(first_row),
    ]
    inner = "\n".join(lines)
    return (
        '<aside class="oc-debug" aria-label="Maps 调试">'
        "<strong>Maps 调试</strong>（加 <code>?debug_maps=1</code>；无在线请求）"
        f"<pre>{_esc(inner)}</pre>"
        "</aside>"
    )


def render_order_page(
    rows: list[dict[str, Any]],
    *,
    debug_maps: bool = False,
    sync_flash_err: str | None = None,
    sync_flash_ok: str | None = None,
    maps_flash_err: str | None = None,
    maps_flash_ok: str | None = None,
    last_synced: str | None = None,
    show_sync_form: bool = False,
    show_maps_enrich_form: bool = False,
    db_fallback_warning: str | None = None,
    order_sync_prefilled_token: str | None = None,
    order_sync_via_session: bool = False,
    session_user: str | None = None,
    role: str | None = None,
    pagination_html: str = "",
) -> str:
    """渲染前重载 env，避免 uvicorn 长驻进程仍用旧环境（改 .env 后无需重启即可试 Maps）。"""
    reload_api_env()
    admin_sync_label = ew_admin_order_sync_label()
    is_developer = normalize_role(role) == "developer"

    def maps_btn_block() -> str:
        if not show_maps_enrich_form:
            return ""
        if order_sync_prefilled_token:
            return (
                f'<form class="oc-sync-form oc-sync-form--inline" method="post" action="/f/read/order/google-maps">'
                f'<input type="hidden" name="token" value="{_esc(order_sync_prefilled_token)}"/>'
                f'<button type="submit" class="oc-sync-btn oc-sync-btn--maps" title="Google Maps：邮编规范化、距离、标准地址与地图链接">{ORDER_FORMAT_DATA_SKILL_LABEL}</button></form>'
            )
        if order_sync_via_session:
            return (
                '<form class="oc-sync-form oc-sync-form--inline" method="post" action="/f/read/order/google-maps">'
                f'<button type="submit" class="oc-sync-btn oc-sync-btn--maps" title="Google Maps：邮编规范化、距离、标准地址与地图链接">{ORDER_FORMAT_DATA_SKILL_LABEL}</button></form>'
            )
        return (
            f"""
            <form class="oc-sync-form oc-sync-form--tokencol" method="post" action="/f/read/order/google-maps">
              <label class="oc-sync-token"><span>令牌</span>
                <input type="password" name="token" autocomplete="current-password" placeholder="EW_ADMIN_TOKEN" required/>
              </label>
              <button type="submit" class="oc-sync-btn oc-sync-btn--maps" title="Google Maps：邮编规范化、距离、标准地址与地图链接">{ORDER_FORMAT_DATA_SKILL_LABEL}</button>
            </form>
            """
        )

    def peidan_href() -> str:
        q: dict[str, str] = {"fmt": "html"}
        if order_sync_prefilled_token:
            q["token"] = order_sync_prefilled_token
        return "/f/read/order/peidan?" + urlencode(q)

    def peidan_btn_block() -> str:
        if not show_sync_form:
            return ""
        return (
            f'<a class="oc-sync-btn oc-sync-btn--peidan" href="{_esc(peidan_href())}">配单</a>'
        )

    def skills_headline_html() -> str:
        return (
            '<div class="oc-skills-headline" role="group" aria-label="技能">'
            f'<span class="oc-skills-user" title="管理员显示名（EW_ADMIN_DISPLAY_NAME）">{_esc(admin_sync_label)}</span>'
            '<span class="oc-skills-title">技能</span>'
            "</div>"
        )

    def sync_maps_btn_row(inner: str) -> str:
        return (
            '<div class="oc-skills">'
            + skills_headline_html()
            + '<div class="oc-sync-btn-row">'
            + inner
            + peidan_btn_block()
            + "</div></div>"
        )

    def sync_token_btn_grid(sync_form: str, maps_form: str) -> str:
        return (
            '<div class="oc-skills">'
            + skills_headline_html()
            + f'<div class="oc-sync-token-grid">{sync_form}{maps_form}</div>'
            + '<div class="oc-skills-peidan-row">'
            + peidan_btn_block()
            + "</div></div>"
        )

    cards: list[str] = []
    maps_on = bool(google_maps_api_key())
    nrows = len(rows)
    first_row = rows[0] if rows else None
    maps_debug_html = ""
    if debug_maps and rows:
        maps_debug_html = _maps_debug_panel_html(
            maps_on=maps_on,
            nrows=nrows,
            first_row=first_row,
        )
    for r in rows:
        cards.append(
            render_order_card_html(r, maps_skill_label=ORDER_FORMAT_DATA_SKILL_LABEL)
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
          <div class="oc-top-head">
          <a class="oc-home-link" href="/">首页</a>
          <h1><span class="oc-brand">下单</span><span class="oc-title-sub"> · 在途订单</span></h1>
          </div>
"""
        + (
            f"""          <div class="oc-top-actions">
"""
            + (
                (
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
                        sync_maps_btn_row(
                            f"""
            <form class="oc-sync-form oc-sync-form--inline" method="post" action="/f/read/order/sync">
              <input type="hidden" name="token" value="{_esc(order_sync_prefilled_token)}"/>
              <button type="submit" class="oc-sync-btn oc-sync-btn--sheet">从 Sheet 刷新</button>
            </form>
            """
                            + maps_btn_block()
                        )
                        if show_sync_form and order_sync_prefilled_token
                        else (
                            sync_maps_btn_row(
                                f"""
            <form class="oc-sync-form oc-sync-form--inline" method="post" action="/f/read/order/sync">
              <button type="submit" class="oc-sync-btn oc-sync-btn--sheet">从 Sheet 刷新</button>
            </form>
            """
                                + maps_btn_block()
                            )
                            if show_sync_form and order_sync_via_session
                            else (
                                (
                                    sync_token_btn_grid(
                                        """
            <form class="oc-sync-form oc-sync-form--tokencol" method="post" action="/f/read/order/sync">
              <label class="oc-sync-token"><span>令牌</span>
                <input type="password" name="token" autocomplete="current-password" placeholder="EW_ADMIN_TOKEN" required/>
              </label>
              <button type="submit" class="oc-sync-btn oc-sync-btn--sheet">从 Sheet 刷新</button>
            </form>
            """,
                                        maps_btn_block(),
                                    )
                                    if show_maps_enrich_form
                                    else sync_maps_btn_row(
                                        """
            <form class="oc-sync-form" method="post" action="/f/read/order/sync">
              <label class="oc-sync-token"><span>令牌</span>
                <input type="password" name="token" autocomplete="current-password" placeholder="EW_ADMIN_TOKEN" required/>
              </label>
              <button type="submit" class="oc-sync-btn oc-sync-btn--sheet">从 Sheet 刷新</button>
            </form>
            """
                                    )
                                )
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
                + """          </div>
"""
            )
            if is_developer
            else ""
        )
        + """
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
            f'<p class="oc-sync-flash oc-sync-flash--ok" role="status">{_esc(maps_flash_ok)}</p>'
            if maps_flash_ok
            else ""
        )
        + (
            f'<p class="oc-sync-flash oc-sync-flash--err" role="alert">{_esc(maps_flash_err)}</p>'
            if maps_flash_err
            else ""
        )
        + (
            f'<p class="oc-db-fallback" role="alert">{_esc(db_fallback_warning)}</p>'
            if db_fallback_warning
            else ""
        )
        + (
            f'<p class="oc-maps-hint">未配置 <code>GOOGLE_MAPS_API_KEY</code>：无法使用「{ORDER_FORMAT_DATA_SKILL_LABEL}」。调试请加 <code>?debug_maps=1</code> 查看首行数据库缓存。</p>'
            if (not maps_on and nrows > 0)
            else ""
        )
        + maps_debug_html
        + body_cards
        + pagination_html
        + """
      </div>
    </main>
  </div>
</body>
</html>
"""
    )
