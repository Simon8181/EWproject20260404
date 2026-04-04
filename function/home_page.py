"""Modern landing HTML for the EW HTTP service."""

from __future__ import annotations

import html
from typing import Any

from function.dat_theme import HOME_PAGE_CSS


def render_home_page(items: list[dict[str, Any]]) -> str:
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
  <meta name="theme-color" content="#ff6600"/>
  <title>EW · Sheet 服务</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&amp;display=swap" rel="stylesheet"/>
  <style>
"""
        + HOME_PAGE_CSS
        + """
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div class="badge">EWproject · Sheet API</div>
      <h1><span class="dat">EW</span> 数据视图</h1>
      <p class="lead">从目录中的路由读取 Google Sheet，支持 HTML 表格或 JSON。大表请使用 <code>limit</code> 限制行数。</p>
      <div class="meta">
        <a href="/health">/health</a>
        <span>·</span>
        <span>文档路径与 <code>EW_CATALOG.yaml</code> 一致</span>
      </div>
    </header>
    <section class="grid" aria-label="可读路由">
"""
        + cards_html
        + """
    </section>
    <footer>
      EW Sheet Service · 本地服务请使用 <code>uvicorn function.ew_service:app</code>
    </footer>
  </div>
</body>
</html>
"""
    )
