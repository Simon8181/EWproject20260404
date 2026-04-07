# v3 Web 壳（导航与干净 URL）

目标：从 v2 Debug 复制 **视觉壳** 与主导航，满足：

- 链接：**Home**、**`load`** 下拉（内含 `quote` / `order` / `complete` / `cancel`）、**`blank`**
- URL **不带查询参数**（主导航与首页列表均为 `/`、`/tab/quote`、`/blank` 等）
- 与 v2 **分离**：默认端口可与 v2 错开（如 `8011`）
- **v2**：继续保留 [`/debug/blank`](../../v2/app/debug_web.py)，**不要**从 v2 删除 `blank`

## 目录与依赖

在 `v3/` 下新增：

```
v3/
  app/
    __init__.py    # 可为空或仅 docstring
    web.py         # 见下文完整代码
  requirements.txt
```

`requirements.txt`：

```
fastapi>=0.100
uvicorn[standard]>=0.22
```

## 启动

```bash
cd v3
pip install -r requirements.txt
uvicorn app.web:app --host 127.0.0.1 --port 8011 --reload
```

浏览器：`http://127.0.0.1:8011/`、`http://127.0.0.1:8011/tab/order` 等。

## `v3/app/__init__.py`

```python
"""EW v3 application package (scaffold)."""
```

## `v3/app/web.py`（参考）

下列代码块可能与仓库略有出入；**以仓库内 [`v3/app/web.py`](../app/web.py) 为准**（含 **load** 下拉菜单的完整 CSS）。

```python
"""
EW v3 web shell: same visual language as v2 Debug (gf-*), clean paths without query params on nav.
Run: cd v3 && uvicorn app.web:app --host 127.0.0.1 --port 8011 --reload
"""

from __future__ import annotations

import html

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

_DEBUG_BRAND = "EW v3 Debug Simon"
TAB_KEYS = ("quote", "order", "complete", "cancel")

_NO_CACHE = {
    "Cache-Control": "no-store, must-revalidate",
    "Pragma": "no-cache",
}


def _render_layout(title: str, body: str) -> HTMLResponse:
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
      font-family: Roboto, system-ui, -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
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
    .gf-link-list {{ margin: 8px 0 0; padding-left: 20px; }}
    .gf-link-list li {{ margin: 8px 0; }}
  </style>
</head>
<body class="gf-page">
  <header class="gf-header">
    <div class="gf-header__inner">
      <span class="gf-header__brand">{html.escape(_DEBUG_BRAND)}</span>
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


app = FastAPI(title=_DEBUG_BRAND, version="0.1.0")


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    links = (
        "<p class=\"muted\">v3 壳页面；主导航与下列链接均为无查询参数的干净 URL。</p>"
        "<p class=\"gf-load-section-title\">load</p>"
        "<ul class=\"gf-link-list gf-link-list--nested\">"
        "<li><a class=\"gf-link\" href=\"/tab/quote\">quote</a></li>"
        "<li><a class=\"gf-link\" href=\"/tab/order\">order</a></li>"
        "<li><a class=\"gf-link\" href=\"/tab/complete\">complete</a></li>"
        "<li><a class=\"gf-link\" href=\"/tab/cancel\">cancel</a></li>"
        "</ul>"
        "<p class=\"gf-load-section-title\">其它</p>"
        "<ul class=\"gf-link-list gf-link-list--nested\">"
        "<li><a class=\"gf-link\" href=\"/blank\">blank</a></li>"
        "</ul>"
    )
    return _render_layout(_DEBUG_BRAND, links)


@app.get("/blank", response_class=HTMLResponse)
def blank_page() -> HTMLResponse:
    return _render_layout("Blank", "")


@app.get("/tab/{tab_key}", response_class=HTMLResponse)
def tab_page(tab_key: str) -> HTMLResponse:
    if tab_key not in TAB_KEYS:
        body = (
            "<p class=\"muted\">无效的 tab。</p>"
            "<p><a class=\"gf-link\" href=\"/\">返回 Home</a></p>"
        )
        return _render_layout("Tab 不存在", body)
    body = (
        f"<p class=\"muted\">tab=<b>{html.escape(tab_key)}</b> · 占位页，待接业务逻辑。</p>"
        "<p><a class=\"gf-link\" href=\"/\">返回 Home</a></p>"
    )
    return _render_layout(f"Tab: {tab_key}", body)
```

## 说明

- **`load` 菜单**：顶栏用 `<details><summary>load</summary>` 收纳四个 tab 链接；首页用标题 **load** 分组列表。
- **`blank`**：`GET /blank` 与 v2 的 `/debug/blank` 同类，仅标题 + 空正文，供扩展 UI；**v2 侧勿删** `debug_blank`。
- 未挂载 v2 的提货提醒脚本、无 `?reminder_interval_ms` 等 **URL 参数依赖**。
- Tab 内容为占位；后续可接 `load` / Sheet 与 v2 逻辑或共享包。
