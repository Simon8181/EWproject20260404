"""Shared HTML shell (gf-*), v3 nav paths, extended styles for load tables."""

from __future__ import annotations

import html

from fastapi.responses import HTMLResponse

DEBUG_BRAND = "EW v3 Debug Simon"

_NO_CACHE = {
    "Cache-Control": "no-store, must-revalidate",
    "Pragma": "no-cache",
}


def render_layout(title: str, body: str) -> HTMLResponse:
    nav = (
        '<nav class="gf-nav" aria-label="主导航">'
        '<a href="/">Home</a>'
        '<details class="gf-nav-load">'
        '<summary>load</summary>'
        '<div class="gf-nav-load-panel" role="group" aria-label="load">'
        '<a href="/tab/quote">quote</a>'
        '<a href="/tab/order">order</a>'
        '<a href="/tab/complete">complete</a>'
        '<a href="/tab/cancel">cancel</a>'
        "</div>"
        "</details>"
        '<a href="/blank">blank</a>'
        "</nav>"
    )
    page = f"""<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet"/>
  <style>
    :root {{
      --gf-primary: #673ab7;
      --gf-primary-hover: #5e35b1;
      --gf-surface: #ffffff;
      --gf-page: #f8f7fc;
      --gf-text: #202124;
      --gf-muted: #5f6368;
      --gf-border: #dadce0;
      --gf-success: #34a853;
      --gf-error: #d93025;
      --gf-radius: 8px;
      --gf-shadow: 0 1px 2px rgba(60,64,67,.3), 0 1px 3px 1px rgba(60,64,67,.15);
    }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    body.gf-page {{
      margin: 0;
      min-height: 100vh;
      font-family: Roboto, system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial,
        "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: var(--gf-text);
      background: var(--gf-page);
    }}
    .gf-header {{
      background: var(--gf-primary);
      color: #fff;
      box-shadow: var(--gf-shadow);
    }}
    .gf-header__inner {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 12px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px 20px;
    }}
    .gf-header__brand {{
      font-weight: 500;
      font-size: 1.125rem;
      letter-spacing: 0.02em;
    }}
    .gf-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 16px;
      align-items: center;
    }}
    .gf-nav a {{
      color: rgba(255,255,255,.95);
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      padding: 4px 0;
      border-radius: 4px;
    }}
    .gf-nav a:hover {{ text-decoration: underline; color: #fff; }}
    .gf-nav a:focus-visible {{
      outline: 2px solid #fff;
      outline-offset: 2px;
    }}
    .gf-nav-load {{ position: relative; }}
    .gf-nav-load > summary {{
      list-style: none;
      cursor: pointer;
      color: rgba(255,255,255,.95);
      font-size: 13px;
      font-weight: 500;
      padding: 4px 0;
      user-select: none;
    }}
    .gf-nav-load > summary::-webkit-details-marker {{ display: none; }}
    .gf-nav-load > summary::after {{
      content: " ▾";
      font-size: 10px;
      opacity: 0.85;
    }}
    .gf-nav-load[open] > summary::after {{ content: " ▴"; }}
    .gf-nav-load > summary:focus-visible {{
      outline: 2px solid #fff;
      outline-offset: 2px;
      border-radius: 4px;
    }}
    .gf-nav-load-panel {{
      position: absolute;
      top: 100%;
      left: 0;
      margin-top: 6px;
      min-width: 11rem;
      padding: 6px 0;
      background: var(--gf-surface);
      border-radius: var(--gf-radius);
      box-shadow: var(--gf-shadow);
      display: flex;
      flex-direction: column;
      z-index: 20;
    }}
    .gf-nav-load-panel a {{
      color: var(--gf-text);
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 500;
    }}
    .gf-nav-load-panel a:hover {{
      background: #f1f3f4;
      text-decoration: none;
      color: var(--gf-primary);
    }}
    .gf-nav-load-panel a:focus-visible {{
      outline: 2px solid var(--gf-primary);
      outline-offset: -2px;
    }}
    .gf-load-section-title {{
      font-size: 12px;
      font-weight: 500;
      color: var(--gf-muted);
      text-transform: lowercase;
      margin: 16px 0 6px;
      letter-spacing: 0.04em;
    }}
    .gf-load-section-title:first-of-type {{ margin-top: 0; }}
    .gf-link-list--nested {{ margin-top: 4px; }}
    .gf-main {{ padding: 24px 16px 48px; }}
    .gf-card {{
      max-width: 1200px;
      margin: 0 auto;
      background: var(--gf-surface);
      border-radius: var(--gf-radius);
      box-shadow: var(--gf-shadow);
      padding: 28px 32px 36px;
    }}
    .gf-title {{
      margin: 0 0 8px;
      font-size: 1.5rem;
      font-weight: 500;
      color: var(--gf-text);
      letter-spacing: -0.01em;
    }}
    .muted {{ color: var(--gf-muted); font-size: 13px; }}
    .gf-link {{
      color: var(--gf-primary);
      text-decoration: none;
      font-weight: 500;
    }}
    .gf-link:hover {{ text-decoration: underline; }}
    .gf-link:focus-visible {{
      outline: 2px solid var(--gf-primary);
      outline-offset: 2px;
      border-radius: 2px;
    }}
    .gf-link-list {{ margin: 8px 0 0; padding-left: 20px; }}
    .gf-link-list li {{ margin: 8px 0; }}
    .gf-table-wrap {{
      overflow: auto;
      margin: 12px 0 24px;
      border: 1px solid var(--gf-border);
      border-radius: var(--gf-radius);
    }}
    .gf-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .gf-table th, .gf-table td {{
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid var(--gf-border);
    }}
    .gf-table th {{
      background: #f8f9fa;
      color: var(--gf-muted);
      font-weight: 500;
      position: sticky;
      top: 0;
      z-index: 1;
      border-bottom: 2px solid var(--gf-border);
      box-shadow: 0 1px 0 var(--gf-border);
    }}
    .gf-table tbody tr:hover {{ background: #f8f9fa; }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 16px 0 24px;
      align-items: center;
    }}
    .gf-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 0 24px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 500;
      border-radius: 4px;
      cursor: pointer;
      border: none;
      text-decoration: none;
      transition: background .15s, box-shadow .15s, border-color .15s;
    }}
    .gf-btn:focus-visible {{
      outline: 2px solid var(--gf-primary);
      outline-offset: 2px;
    }}
    .gf-btn-primary {{
      background: var(--gf-primary);
      color: #fff;
      box-shadow: 0 1px 2px rgba(60,64,67,.3);
    }}
    .gf-btn-primary:hover {{ background: var(--gf-primary-hover); }}
    .gf-btn-ghost {{
      background: #ffffff;
      color: var(--gf-primary);
      border: 1px solid var(--gf-border);
      box-shadow: none;
    }}
    .gf-btn-ghost:hover {{ background: #f3e5f5; border-color: #ce93d8; }}
    .gf-order-filter {{
      border: 1px solid var(--gf-border);
      border-radius: var(--gf-radius);
      padding: 14px 16px;
      background: #f8f9fa;
      margin: 0 0 16px;
    }}
    .gf-order-filter__title {{
      font-weight: 500;
      margin: 0 0 10px;
      color: var(--gf-text);
      font-size: 14px;
    }}
    .gf-code {{
      background: #f1f3f4;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.9em;
      font-family: ui-monospace, monospace;
    }}
    tr.gf-row-overdue > td {{ background: #fff3e0; }}
    table.gf-load-table tbody tr.gf-load-summary {{ cursor: pointer; }}
    table.gf-load-table tbody tr.gf-load-summary:focus-visible {{
      outline: 2px solid var(--gf-primary);
      outline-offset: -2px;
    }}
    table.gf-load-table tbody tr.gf-load-summary:hover td {{ background: #f5f5f5; }}
    table.gf-load-table tbody tr.gf-load-summary.gf-row-overdue:hover td {{
      background: #ffe8cc;
    }}
    table.gf-load-table .gf-chev {{
      width: 2rem;
      text-align: center;
      font-size: 12px;
      color: var(--gf-muted);
      user-select: none;
    }}
    table.gf-load-table tr.gf-load-detail td {{
      padding: 14px 16px 18px;
      background: #fafafa;
      border-bottom: 1px solid var(--gf-border);
    }}
    .gf-detail-dl {{
      display: grid;
      grid-template-columns: 9.5rem 1fr;
      gap: 6px 16px;
      margin: 0;
      font-size: 13px;
    }}
    .gf-detail-dl dt {{
      margin: 0;
      color: var(--gf-muted);
      font-weight: 500;
    }}
    .gf-detail-dl dd {{
      margin: 0;
      word-break: break-word;
    }}
    .gf-sum-main {{ vertical-align: middle; line-height: 1.45; }}
    .gf-sum-qno {{ font-weight: 500; }}
    .gf-sum-route {{ font-size: 13px; }}
    .gf-sum-sep {{ margin: 0 0.35em; }}
  </style>
</head>
<body class="gf-page">
  <header class="gf-header">
    <div class="gf-header__inner">
      <span class="gf-header__brand">{html.escape(DEBUG_BRAND)}</span>
      {nav}
    </div>
  </header>
  <main class="gf-main">
    <article class="gf-card">
      <h1 class="gf-title">{html.escape(title)}</h1>
      {body}
    </article>
  </main>
</body>
</html>
"""
    return HTMLResponse(page, headers=dict(_NO_CACHE))
