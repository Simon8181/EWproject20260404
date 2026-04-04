"""GET /login — 用户名 + 密码，写入 HttpOnly Cookie（角色会话）。"""

from __future__ import annotations

import html
from urllib.parse import quote as urlquote

from function.dat_theme import AUTH_PAGE_BODY_CSS, LAYOUT_SHELL_CSS
from function.web_nav import render_sidebar_nav

_LOGIN_CSS = """
    .lg-wrap { max-width: min(440px, 100%); margin: 0 auto; color: #f3f4f6; }
    .lg-top h1 { font-size: clamp(22px, 4vw, 26px); font-weight: 800; margin: 0 0 8px; color: #fff; }
    .lg-top .lg-brand { color: #38bdf8; }
    .lg-lead { font-size: 14px; color: #d4d4d8; line-height: 1.55; margin: 0 0 20px; max-width: 52ch; }
    .lg-lead code { font-size: 0.92em; color: #fde68a; }
    .lg-box {
      background: #18181b; border: 1px solid #3f3f46; border-radius: 12px; padding: 20px 18px;
    }
    .lg-field { margin-bottom: 14px; }
    .lg-field label { display: block; font-size: 13px; font-weight: 700; color: #e4e4e7; margin-bottom: 6px; }
    .lg-field input[type="password"], .lg-field input[type="text"] {
      width: 100%; padding: 11px 12px; font-size: 15px; border-radius: 8px;
      border: 1px solid #52525b; background: #09090b; color: #fafafa;
    }
    .lg-field input:focus { outline: 2px solid rgba(56, 189, 248, 0.55); outline-offset: 1px; border-color: rgba(56, 189, 248, 0.45); }
    .lg-btn {
      display: inline-flex; align-items: center; justify-content: center;
      min-height: 44px; padding: 0 22px; font-size: 15px;
      border-radius: 10px; cursor: pointer;
      background: linear-gradient(165deg, rgba(125, 211, 252, 0.98), #0ea5e9); color: #020617;
      border: 1px solid rgba(56, 189, 248, 0.45);
      font-weight: 600;
      letter-spacing: 0.03em;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.12) inset;
    }
    .lg-btn:hover { filter: brightness(1.06); }
    .lg-err {
      padding: 10px 12px; border-radius: 8px; margin-bottom: 14px; font-size: 14px; font-weight: 600;
      background: rgba(127, 29, 29, 0.5); border: 1px solid #f87171; color: #fecaca;
    }
    .lg-muted { font-size: 13px; color: #a1a1aa; margin-top: 14px; line-height: 1.5; }
    .lg-warn {
      padding: 12px 14px; border-radius: 8px; margin-bottom: 14px; font-size: 13px; font-weight: 600;
      line-height: 1.5; background: rgba(120, 53, 15, 0.55); border: 1px solid #fbbf24; color: #fef3c7;
    }
    .lg-warn code { font-size: 0.95em; color: #fde68a; }
    .lg-auth-switch { margin-top: 14px; font-size: 13px; color: #a1a1aa; }
    .lg-auth-switch a { color: #fdba74; font-weight: 700; text-decoration: none; }
    .lg-auth-switch a:hover { text-decoration: underline; }
"""


def render_login_page(
    *,
    next_path: str,
    error: str | None = None,
    can_login: bool = True,
    session_user: str | None = None,
    setup_hint: str | None = None,
) -> str:
    next_esc = html.escape(next_path, quote=True)
    next_reg = urlquote(next_path, safe="")
    err_html = f'<div class="lg-err" role="alert">{html.escape(error)}</div>' if error else ""
    hint = (
        f'<div class="lg-warn" role="status">{setup_hint}</div>'
        if setup_hint
        else ""
    )
    muted = (
        ""
        if can_login
        else '<p class="lg-muted">首次使用：在仓库根目录执行 <code>python -m function.create_user 你的登录名 developer</code> 创建账号；'
        "<code>config/api.secrets.env</code> 中需设置 <code>EW_SESSION_SECRET</code>（或 <code>EW_ADMIN_TOKEN</code>）用于会话签名，然后重启 uvicorn。</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="theme-color" content="#0f172a"/>
  <title>EW · 登录</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700&amp;display=swap" rel="stylesheet"/>
  <style>
{LAYOUT_SHELL_CSS}
{AUTH_PAGE_BODY_CSS}
{_LOGIN_CSS}
  </style>
</head>
<body>
  <div class="ew-shell">
{render_sidebar_nav("home", session_user=session_user, role=None)}
    <main class="ew-main">
      <div class="lg-wrap">
        <header class="lg-top">
          <h1><span class="lg-brand">EW</span> 登录</h1>
          <p class="lg-lead">使用 <code>config/ew_users.yaml</code> 中的账号与密码。角色：开发者（全站）、Boss（看单与集成）、Broker（下单与同步）。</p>
        </header>
{err_html}
{hint}
        <div class="lg-box">
          <form method="post" action="/login" autocomplete="off">
            <input type="hidden" name="next" value="{next_esc}"/>
            <div class="lg-field">
              <label for="lg-user">用户名</label>
              <input id="lg-user" name="username" type="text" autocomplete="username" required maxlength="64" placeholder="登录名"/>
            </div>
            <div class="lg-field">
              <label for="lg-pass">密码</label>
              <input id="lg-pass" name="password" type="password" autocomplete="current-password" required minlength="1"/>
            </div>
            <button type="submit" class="lg-btn">登录</button>
          </form>
          <p class="lg-auth-switch">没有账号？<a href="/register?next={next_reg}">注册</a></p>
{muted}
        </div>
      </div>
    </main>
  </div>
</body>
</html>
"""
