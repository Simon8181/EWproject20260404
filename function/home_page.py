"""Modern landing HTML for the EW HTTP service."""

from __future__ import annotations

import html
from typing import Any

from function.dat_theme import HOME_PAGE_CSS, LAYOUT_SHELL_CSS
from function.web_nav import render_sidebar_nav


def _hero_subtitle(role: str | None) -> str:
    if role == "broker":
        return "Broker：专注在途订单与 Sheet 同步。"
    if role == "boss":
        return "Boss：查看订单、集成状态与配置（只读）。"
    if role == "developer":
        return "开发者：全站配置、用户管理与集成。"
    return "把表格数据接到业务视图：目录路由、网页表格与 JSON，内部一眼可用。"


def render_home_page(
    items: list[dict[str, Any]],
    *,
    session_user: str | None = None,
    role: str | None = None,
) -> str:
    cards: list[str] = []
    for it in items:
        name = html.escape(str(it.get("name", "")))
        sid = html.escape(str(it.get("sheet_id", "")))
        note = html.escape(str(it.get("note", "")))
        tab = html.escape(str(it.get("tab_hint", "")))
        path = html.escape(str(it.get("path", "")))
        cards.append(
            f"""
            <article class="card">
              <div class="card-top">
                <span class="pill">{name}</span>
                <code class="sid">{sid}</code>
              </div>
              <p class="note">{note}</p>
              <p class="tab">{tab}</p>
              <div class="actions">
                <a class="btn primary" href="{path}?fmt=html&amp;limit=50">表格 HTML</a>
                <a class="btn ghost" href="{path}?fmt=json&amp;limit=20" target="_blank" rel="noopener">JSON</a>
              </div>
            </article>
            """
        )
    cards_html = "".join(cards) if cards else '<p class="empty">EW_CATALOG.yaml 中暂无 /f/read/ 路由。</p>'

    return (
        """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="theme-color" content="#0f172a"/>
  <title>EW · Sheet 数据工作台</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&amp;display=swap" rel="stylesheet"/>
  <style>
"""
        + LAYOUT_SHELL_CSS
        + HOME_PAGE_CSS
        + """
  </style>
</head>
<body>
  <div class="ew-shell">
"""
        + render_sidebar_nav("home", session_user=session_user, role=role)
        + """
    <main class="ew-main">
  <div class="wrap">
    <header class="hero">
      <div class="badge">EWproject · Sheet API</div>
      <h1><span class="dat">EW</span> 数据工作台</h1>
      <p class="hero-sub">"""
        + html.escape(_hero_subtitle(role))
        + """</p>
      <p class="lead">从 <code>EW_CATALOG.yaml</code> 声明的路径读取 Google Sheet；大表请加 <code>limit</code>。</p>
      <div class="hero-cta">
        <a class="btn primary" href="/f/read/order?fmt=html&amp;limit=50">下单视图</a>
        <a class="btn ghost" href="/docs/ew-usage-guide-v1.pdf" download>使用守则（PDF）</a>
"""
        + (
            '<a class="btn ghost" href="/config">配置</a>'
            if role is not None and role in ("developer", "boss")
            else ""
        )
        + (
            '<a class="btn ghost" href="/login?next=%2F">登录</a>'
            '<a class="btn ghost" href="/register?next=%2F">注册</a>'
            if not session_user
            else ""
        )
        + """
        <a class="btn ghost" href="/health">Health</a>
      </div>
      <ul class="hero-strip" aria-label="能力要点">
        <li>目录驱动路由</li>
        <li>HTML / JSON 双输出</li>
        <li>可限制行数</li>
      </ul>
      <div class="meta">
        <span>路径与目录一致</span>
        <span>·</span>
        <a href="/health">/health</a>
      </div>
    </header>
    <section aria-labelledby="routes-heading">
      <div class="section-head">
        <h2 id="routes-heading">可读路由</h2>
        <p class="section-desc">下方卡片对应各 Sheet 逻辑名；「表格 HTML」适合浏览，「JSON」便于对接。</p>
      </div>
      <div class="grid">
"""
        + cards_html
        + """
      </div>
    </section>
    <footer>
      EW Sheet Service · 本地 <code>uvicorn function.ew_service:app</code>
      <br/>
      布局层次参考专业物流门户（标题区 → 主操作 → 分区说明 → 功能卡片），例如
      <a class="ref" href="https://welogx.com/" target="_blank" rel="noopener noreferrer">Welogx</a>
      的信息架构。
    </footer>
  </div>
    </main>
  </div>
</body>
</html>
"""
    )
