"""User management HTML — developer only."""

from __future__ import annotations

import html

from function.auth_roles import ROLE_LABEL_ZH, ROLES
from function.dat_theme import AUTH_PAGE_BODY_CSS, LAYOUT_SHELL_CSS
from function.web_nav import render_sidebar_nav

_USERS_CSS = """
    .um-wrap { max-width: min(720px, 100%); margin: 0 auto; color: #f3f4f6; }
    .um-top h1 { font-size: clamp(22px, 4vw, 26px); font-weight: 800; margin: 0 0 8px; color: #fff; }
    .um-top .um-brand { color: #38bdf8; }
    .um-lead { font-size: 14px; color: #d4d4d8; line-height: 1.55; margin: 0 0 18px; max-width: 56ch; }
    .um-lead code { font-size: 0.92em; color: #fde68a; }
    .um-table-wrap { overflow-x: auto; border: 1px solid #3f3f46; border-radius: 10px; background: #18181b; }
    table.um-table { border-collapse: collapse; width: 100%; font-size: 14px; }
    .um-table th, .um-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #27272a; }
    .um-table th { background: #27272a; color: #fafafa; font-weight: 800; font-size: 12px; }
    .um-table tr:last-child td { border-bottom: none; }
    .um-badge { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 12px; font-weight: 700; }
    .um-badge--dev { background: rgba(34, 197, 94, 0.25); color: #bbf7d0; }
    .um-badge--boss { background: rgba(59, 130, 246, 0.25); color: #bfdbfe; }
    .um-badge--broker { background: rgba(245, 158, 11, 0.25); color: #fde68a; }
    .um-box {
      margin-top: 22px; padding: 18px; border: 1px solid #52525b; border-radius: 12px; background: #18181b;
    }
    .um-box h2 { margin: 0 0 12px; font-size: 15px; font-weight: 800; color: #fff; }
    .um-field { margin-bottom: 12px; }
    .um-field label { display: block; font-size: 12px; font-weight: 700; color: #e4e4e7; margin-bottom: 4px; }
    .um-field input, .um-field select {
      width: 100%; max-width: 320px; padding: 9px 10px; font-size: 14px; border-radius: 8px;
      border: 1px solid #52525b; background: #09090b; color: #fafafa;
    }
    .um-btn {
      display: inline-flex; align-items: center; justify-content: center;
      min-height: 40px; padding: 0 16px; font-size: 14px; font-weight: 800;
      border-radius: 8px; border: none; cursor: pointer;
      background: linear-gradient(165deg, rgba(125, 211, 252, 0.98), #0ea5e9); color: #020617;
      border: 1px solid rgba(56, 189, 248, 0.4);
      font-weight: 600;
    }
    .um-btn--danger { background: linear-gradient(135deg, #f87171, #b91c1c); color: #fff; }
    .um-btn--sm { min-height: 32px; padding: 0 10px; font-size: 12px; }
    .um-flash { padding: 10px 12px; border-radius: 8px; margin-bottom: 12px; font-weight: 600; }
    .um-flash--ok { background: rgba(22, 101, 52, 0.45); border: 1px solid #4ade80; color: #ecfccb; }
    .um-flash--err { background: rgba(127, 29, 29, 0.5); border: 1px solid #f87171; color: #fecaca; }
    .um-inline { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
"""


def _badge_class(role: str) -> str:
    return {"developer": "um-badge--dev", "boss": "um-badge--boss", "broker": "um-badge--broker"}.get(
        role, "um-badge--broker"
    )


def render_users_page(
    rows: list[dict[str, str]],
    *,
    session_caption: str,
    role: str,
    flash_ok: str | None = None,
    flash_err: str | None = None,
) -> str:
    body_rows: list[str] = []
    for row in rows:
        un = html.escape(row["username"])
        role = row["role"]
        zh = html.escape(ROLE_LABEL_ZH.get(role, role))
        bc = _badge_class(role)
        body_rows.append(
            f"<tr><td><code>{un}</code></td>"
            f'<td><span class="um-badge {bc}">{zh}</span></td>'
            "<td>"
            f'<form class="um-inline" method="post" action="/users/role" style="display:inline">'
            f'<input type="hidden" name="username" value="{un}"/>'
            '<select name="role" aria-label="角色">'
            + "".join(
                f'<option value="{html.escape(r)}"{" selected" if r == role else ""}>{html.escape(ROLE_LABEL_ZH.get(r, r))}</option>'
                for r in ROLES
            )
            + "</select>"
            '<button type="submit" class="um-btn um-btn--sm">更新角色</button>'
            "</form>"
            f'<form method="post" action="/users/delete" style="display:inline" onsubmit="return confirm(\'删除用户 {un}？\');">'
            f'<input type="hidden" name="username" value="{un}"/>'
            '<button type="submit" class="um-btn um-btn--sm um-btn--danger">删除</button>'
            "</form>"
            "</td></tr>"
        )
    table_html = (
        '<table class="um-table"><thead><tr><th>用户名</th><th>角色</th><th>操作</th></tr></thead><tbody>'
        + "".join(body_rows)
        + "</tbody></table>"
        if body_rows
        else '<p class="um-lead">暂无用户。请在下方添加，或使用 <code>python -m function.create_user</code>。</p>'
    )

    flash = ""
    if flash_ok:
        flash += f'<div class="um-flash um-flash--ok" role="status">{html.escape(flash_ok)}</div>'
    if flash_err:
        flash += f'<div class="um-flash um-flash--err" role="alert">{html.escape(flash_err)}</div>'

    role_opts = "".join(
        f'<option value="{html.escape(r)}">{html.escape(ROLE_LABEL_ZH.get(r, r))}</option>' for r in ROLES
    )

    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="theme-color" content="#0f172a"/>
  <title>EW · 用户管理</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700&amp;display=swap" rel="stylesheet"/>
  <style>
{LAYOUT_SHELL_CSS}
{AUTH_PAGE_BODY_CSS}
{_USERS_CSS}
  </style>
</head>
<body>
  <div class="ew-shell">
{render_sidebar_nav("users", session_user=session_caption, role=role)}
    <main class="ew-main">
      <div class="um-wrap">
        <header class="um-top">
          <h1><span class="um-brand">EW</span> 用户管理</h1>
          <p class="um-lead">仅 <strong>开发者</strong> 可访问。账号保存在 <code>config/ew_users.yaml</code>（勿提交 Git）。角色：开发者（全站与集成）、Boss（看单与集成、配置只读）、Broker（下单与同步）。</p>
        </header>
{flash}
        <div class="um-table-wrap">{table_html}</div>
        <div class="um-box">
          <h2>添加用户</h2>
          <form method="post" action="/users/add" autocomplete="off">
            <div class="um-field">
              <label for="nu">用户名</label>
              <input id="nu" name="username" type="text" required maxlength="64" placeholder="登录名"/>
            </div>
            <div class="um-field">
              <label for="np">初始密码（至少 6 位）</label>
              <input id="np" name="password" type="password" autocomplete="new-password" required minlength="6"/>
            </div>
            <div class="um-field">
              <label for="nr">角色</label>
              <select id="nr" name="role" aria-label="角色">{role_opts}</select>
            </div>
            <button type="submit" class="um-btn">添加</button>
          </form>
        </div>
      </div>
    </main>
  </div>
</body>
</html>
"""
