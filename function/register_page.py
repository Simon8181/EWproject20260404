"""GET /register — self-service signup (policy in register_policy)."""

from __future__ import annotations

import html
from urllib.parse import quote as urlquote

from function.dat_theme import AUTH_PAGE_BODY_CSS, LAYOUT_SHELL_CSS
from function.web_nav import render_sidebar_nav

_REG_CSS = """
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
    .lg-muted { font-size: 13px; color: #a1a1aa; margin-top: 0; line-height: 1.55; }
    .lg-warn {
      padding: 12px 14px; border-radius: 8px; margin-bottom: 14px; font-size: 13px; font-weight: 600;
      line-height: 1.5; background: rgba(120, 53, 15, 0.55); border: 1px solid #fbbf24; color: #fef3c7;
    }
    .lg-auth-switch { margin-top: 14px; font-size: 13px; color: #a1a1aa; }
    .lg-auth-switch a { color: #fdba74; font-weight: 700; text-decoration: none; }
    .lg-auth-switch a:hover { text-decoration: underline; }
"""


def render_register_page(
    *,
    next_path: str,
    error: str | None = None,
    allowed: bool = True,
    signing_ok: bool = True,
    show_code_field: bool = False,
    closed_message: str | None = None,
) -> str:
    next_esc = html.escape(next_path, quote=True)
    next_login = urlquote(next_path, safe="")
    err_html = f'<div class="lg-err" role="alert">{html.escape(error)}</div>' if error else ""

    code_row = ""
    if show_code_field:
        code_row = """
            <div class="lg-field">
              <label for="reg-code">注册码</label>
              <input id="reg-code" name="registration_code" type="password" autocomplete="off" placeholder="与服务器 EW_REGISTRATION_CODE 一致"/>
            </div>
"""

    form_block = f"""
          <form method="post" action="/register" autocomplete="off">
            <input type="hidden" name="next" value="{next_esc}"/>
            <div class="lg-field">
              <label for="reg-user">用户名</label>
              <input id="reg-user" name="username" type="text" autocomplete="username" required maxlength="64" placeholder="登录名"/>
            </div>
            <div class="lg-field">
              <label for="reg-pass">密码（至少 6 位）</label>
              <input id="reg-pass" name="password" type="password" autocomplete="new-password" required minlength="6"/>
            </div>
            <div class="lg-field">
              <label for="reg-pass2">确认密码</label>
              <input id="reg-pass2" name="password2" type="password" autocomplete="new-password" required minlength="6"/>
            </div>
            {code_row}
            <button type="submit" class="lg-btn">注册</button>
          </form>
          <p class="lg-auth-switch">已有账号？<a href="/login?next={next_login}">登录</a></p>
"""

    if not signing_ok:
        box_inner = f'<p class="lg-auth-switch"><a href="/login?next={next_login}">返回登录</a></p>'
    elif not allowed:
        warn = (
            f'<div class="lg-warn" role="status">{html.escape(closed_message)}</div>'
            if closed_message
            else ""
        )
        box_inner = warn + f'<p class="lg-auth-switch"><a href="/login?next={next_login}">返回登录</a></p>'
    else:
        box_inner = form_block

    # 避免「政策说明」与「请先配置密钥」同时出现，读起来像互相矛盾
    if not signing_ok:
        lead_html = (
            "<p class=\"lg-lead\">当前<strong>无法注册</strong>：服务器尚未配置用于<strong>签发登录会话</strong>的密钥。"
            "请在 <code>config/api.secrets.env</code> 中设置 <code>EW_SESSION_SECRET</code>（推荐）或 "
            "<code>EW_ADMIN_TOKEN</code>，保存后<strong>重启 uvicorn</strong>，再刷新本页。配置好之前，"
            "下面的「首个账号为开发者」等规则不会生效。</p>"
        )
    elif not allowed:
        lead_html = (
            "<p class=\"lg-lead\">当前<strong>不允许自助注册</strong>（例如已有用户且未开启开放注册）。"
            "规则见下方；也可由开发者用 <code>python -m function.create_user</code> 创建账号。</p>"
        )
    else:
        lead_html = (
            "<p class=\"lg-lead\">首个账号为 <strong>开发者</strong>；开放注册后新用户为 <strong>Broker</strong>。"
            "管理员可在 <code>config/api.secrets.env</code> 设置 <code>EW_SELF_REGISTER=1</code> 与可选 "
            "<code>EW_REGISTRATION_CODE</code>。</p>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="theme-color" content="#0f172a"/>
  <title>EW · 注册</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700&amp;display=swap" rel="stylesheet"/>
  <style>
{LAYOUT_SHELL_CSS}
{AUTH_PAGE_BODY_CSS}
{_REG_CSS}
  </style>
</head>
<body>
  <div class="ew-shell">
{render_sidebar_nav("home", session_user=None, role=None)}
    <main class="ew-main">
      <div class="lg-wrap">
        <header class="lg-top">
          <h1><span class="lg-brand">EW</span> 注册</h1>
{lead_html}
        </header>
{err_html}
        <div class="lg-box">
{box_inner}
        </div>
      </div>
    </main>
  </div>
</body>
</html>
"""
