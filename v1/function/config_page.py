"""配置页：高对比度文字；可保存 ORDER_GOOGLE_MILES_MAX（需 EW_ADMIN_TOKEN）。"""

from __future__ import annotations

import html

from function.api_config import configuration_snapshot, integration_snapshot
from function.dat_theme import LAYOUT_SHELL_CSS
from function.web_nav import render_sidebar_nav

_CFG_CSS = """
    .cfg-wrap {
      max-width: min(920px, 100%);
      margin: 0 auto;
      color: #f3f4f6;
      font-size: 15px;
      line-height: 1.55;
    }
    .cfg-wrap code { font-size: 0.92em; color: #fde68a; background: rgba(0,0,0,.35); padding: 2px 6px; border-radius: 4px; }
    .cfg-top { margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #3f3f46; }
    .cfg-top h1 { font-size: clamp(22px, 4.5vw, 28px); font-weight: 800; margin: 0 0 10px; color: #ffffff; letter-spacing: -0.02em; }
    .cfg-top .cfg-brand { color: #38bdf8; }
    .cfg-lead { font-size: 14px; color: #d4d4d8; line-height: 1.6; margin: 0; max-width: 58ch; }
    .cfg-flash {
      padding: 12px 14px; border-radius: 10px; margin-bottom: 16px; font-size: 14px; font-weight: 600;
      border: 1px solid;
    }
    .cfg-flash--ok { background: rgba(22, 101, 52, 0.45); border-color: #4ade80; color: #ecfccb; }
    .cfg-flash--err { background: rgba(127, 29, 29, 0.5); border-color: #f87171; color: #fecaca; }
    .cfg-section { margin-bottom: 22px; }
    .cfg-section h2 {
      font-size: 12px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase;
      color: #fafafa; margin: 0 0 10px;
    }
    .cfg-kv {
      background: #18181b; border: 1px solid #3f3f46; border-radius: 10px; padding: 12px 14px;
      font-size: 14px; line-height: 1.55;
    }
    .cfg-kv-row { display: grid; grid-template-columns: minmax(160px, 34%) 1fr; gap: 10px 14px; padding: 8px 0; border-bottom: 1px solid #27272a; }
    .cfg-kv-row:last-child { border-bottom: none; padding-bottom: 0; }
    .cfg-kv-row:first-child { padding-top: 0; }
    .cfg-k { color: #e4e4e7; font-weight: 700; }
    .cfg-v { color: #fafafa; word-break: break-word; }
    .cfg-v code { color: #fde047; }
    .cfg-yes { color: #4ade80; font-weight: 800; }
    .cfg-no { color: #fb7185; font-weight: 800; }
    table.cfg-table { border-collapse: collapse; width: 100%; font-size: 14px; }
    table.cfg-table th, table.cfg-table td { border: 1px solid #3f3f46; padding: 10px 12px; text-align: left; }
    table.cfg-table th { background: #27272a; color: #fafafa; font-weight: 800; font-size: 12px; }
    table.cfg-table td { color: #f4f4f5; background: #18181b; }
    .cfg-note { font-size: 14px; color: #d4d4d8; line-height: 1.6; margin: 0; max-width: 58ch; }
    .cfg-note ul { margin: 10px 0 0; padding-left: 1.25em; color: #e4e4e7; }
    .cfg-note li { margin-bottom: 6px; }
    .cfg-foot { margin-top: 24px; padding-top: 16px; border-top: 1px solid #3f3f46; font-size: 13px; color: #a1a1aa; }
    .cfg-foot a { color: #fdba74; text-decoration: none; font-weight: 700; }
    .cfg-foot a:hover { text-decoration: underline; color: #fed7aa; }
    .cfg-form-box {
      background: #18181b; border: 1px solid #52525b; border-radius: 10px; padding: 16px 18px;
    }
    .cfg-form-box h3 { margin: 0 0 12px; font-size: 15px; font-weight: 800; color: #ffffff; }
    .cfg-field { margin-bottom: 14px; }
    .cfg-field label { display: block; font-size: 13px; font-weight: 700; color: #e4e4e7; margin-bottom: 6px; }
    .cfg-field input[type="number"], .cfg-field input[type="password"], .cfg-field input[type="text"] {
      width: 100%; max-width: 320px; padding: 10px 12px; font-size: 15px; border-radius: 8px;
      border: 1px solid #52525b; background: #09090b; color: #fafafa;
    }
    .cfg-field input:focus { outline: 2px solid rgba(56, 189, 248, 0.5); outline-offset: 1px; border-color: rgba(56, 189, 248, 0.4); }
    .cfg-field .hint { font-size: 12px; color: #a1a1aa; margin-top: 6px; line-height: 1.45; }
    .cfg-form-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; }
    .cfg-btn {
      display: inline-flex; align-items: center; justify-content: center;
      min-height: 44px; padding: 0 20px; font-size: 15px;
      border-radius: 10px; cursor: pointer;
      background: linear-gradient(165deg, rgba(125, 211, 252, 0.98), #0ea5e9); color: #020617;
      border: 1px solid rgba(56, 189, 248, 0.45);
      font-weight: 600;
      box-shadow: 0 1px 0 rgba(255, 255, 255, 0.12) inset;
    }
    .cfg-btn:hover { filter: brightness(1.06); }
    .cfg-btn:disabled { opacity: 0.45; cursor: not-allowed; filter: none; }
    .cfg-muted { font-size: 13px; color: #a1a1aa; }
"""


def _yes_no(v: bool) -> str:
    return f'<span class="{"cfg-yes" if v else "cfg-no"}">{"是" if v else "否"}</span>'


def render_config_page(
    *,
    saved: bool = False,
    error: str | None = None,
    can_save: bool = True,
    session_user: str | None = None,
    role: str | None = None,
    read_only: bool = False,
) -> str:
    cfg = configuration_snapshot()
    rows = integration_snapshot()
    miles_val = html.escape(str(cfg["order_google_miles_max"]))
    places_lu = html.escape(str(cfg.get("order_places_land_use") or "0"))

    flash_html = ""
    if saved:
        flash_html = '<div class="cfg-flash cfg-flash--ok" role="status">已保存：ORDER_GOOGLE_MILES_MAX 已写入 <code>config/ew_settings.env</code> 并已生效（无需重启）。</div>'
    if error:
        flash_html += (
            '<div class="cfg-flash cfg-flash--err" role="alert">'
            f"{html.escape(error)}"
            "</div>"
        )

    kv_html = f"""
      <div class="cfg-kv-row"><span class="cfg-k">仓库根目录</span><span class="cfg-v"><code>{html.escape(cfg["repo_root"])}</code></span></div>
      <div class="cfg-kv-row"><span class="cfg-k">根目录 .env</span><span class="cfg-v">{_yes_no(bool(cfg["dot_env_exists"]))}</span></div>
      <div class="cfg-kv-row"><span class="cfg-k">config/api.secrets.env</span><span class="cfg-v">{_yes_no(bool(cfg["api_secrets_env_exists"]))}</span></div>
      <div class="cfg-kv-row"><span class="cfg-k">config/ew_settings.env</span><span class="cfg-v">{_yes_no(bool(cfg["ew_settings_env_exists"]))}（网页保存项）</span></div>
      <div class="cfg-kv-row"><span class="cfg-k">ORDER_GOOGLE_MILES_MAX</span><span class="cfg-v"><code>{miles_val}</code>（当前生效；下单页每行前 N 条调 Maps）</span></div>
      <div class="cfg-kv-row"><span class="cfg-k">ORDER_PLACES_LAND_USE</span><span class="cfg-v"><code>{places_lu}</code>（1=每端多调 Place Details 以细化 warehouse 等；需 GCP 启用 Places API）</span></div>
      <div class="cfg-kv-row"><span class="cfg-k">EW_SELF_REGISTER</span><span class="cfg-v">{_yes_no(bool(cfg.get("ew_self_register_on")))}（进程内当前值：<code>{html.escape(cfg.get("ew_self_register_raw") or "—")}</code>；已有用户时须为 1/true 才开放自助注册。若已写 .env 仍不生效，检查 <code>config/api.secrets.env</code> 是否含空行 <code>EW_SELF_REGISTER=</code> 覆盖了前者）</span></div>
      <div class="cfg-kv-row"><span class="cfg-k">EW_ADMIN_TOKEN</span><span class="cfg-v">{_yes_no(bool(cfg["admin_token_configured"]))}（保存表单必填）</span></div>
      <div class="cfg-kv-row"><span class="cfg-k">EW_SMTP（发守则邮件等）</span><span class="cfg-v">{_yes_no(bool(cfg.get("ew_smtp_configured")))}（EW_SMTP_HOST + EW_SMTP_FROM 或 EW_SMTP_USER；可选 EW_SMTP_PORT、EW_SMTP_TLS、EW_SMTP_SSL）</span></div>
      <div class="cfg-kv-row"><span class="cfg-k">GOOGLE_APPLICATION_CREDENTIALS</span><span class="cfg-v">{_yes_no(bool(cfg["google_application_credentials_set"]))}，文件存在：{_yes_no(bool(cfg["google_application_credentials_file_ok"]))}{f' <code>{html.escape(cfg["google_application_credentials_basename"] or "")}</code>' if cfg.get("google_application_credentials_basename") else ""}</span></div>
    """

    table_rows: list[str] = []
    for row in rows:
        st = row["configured"]
        cls = "cfg-yes" if st else "cfg-no"
        label = "已配置" if st else "未配置"
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(row['name'])}</td>"
            f"<td><span class='{cls}'>{label}</span></td>"
            f"<td><code>{html.escape(row['env_hint'])}</code></td>"
            f"<td>{html.escape(row.get('masked_preview') or '—')}</td>"
            "</tr>"
        )

    form_disabled = "" if can_save else " disabled"
    save_hint = (
        ""
        if can_save
        else '<p class="cfg-muted" style="margin:0 0 12px;">未配置 <code>EW_ADMIN_TOKEN</code> 时无法从网页保存。请在 <code>config/api.secrets.env</code> 中设置后重启服务。</p>'
    )
    token_block = (
        ""
        if (session_user and can_save)
        else f"""
              <div class="cfg-field">
                <label for="ew_admin_token">EW_ADMIN_TOKEN（与 /admin 相同）</label>
                <input id="ew_admin_token" name="token" type="password" autocomplete="current-password" placeholder="输入令牌以保存"{form_disabled}/>
              </div>
"""
    )
    session_note = (
        f'<p class="cfg-muted" style="margin:0 0 12px;">已登录为 <strong>{html.escape(session_user)}</strong>，保存无需再输入令牌。</p>'
        if (session_user and can_save)
        else ""
    )

    if read_only:
        form_html = """
        <section class="cfg-section" aria-label="可保存设置">
          <h2>可保存设置</h2>
          <p class="cfg-note" style="margin:0;">当前为 <strong>Boss</strong> 只读视图。修改 Maps 行数等需使用 <strong>开发者</strong> 账号登录。</p>
        </section>
        """
    else:
        form_html = f"""
        <section class="cfg-section" aria-label="可保存设置">
          <h2>可保存设置</h2>
          <div class="cfg-form-box">
            <h3>下单页 Maps 行数上限</h3>
            {save_hint}
            {session_note}
            <form method="post" action="/config/save" id="cfg-save-form">
              <div class="cfg-field">
                <label for="order_google_miles_max">ORDER_GOOGLE_MILES_MAX</label>
                <input id="order_google_miles_max" name="order_google_miles_max" type="number" min="1" max="9999" step="1" value="{miles_val}" required{form_disabled}/>
                <p class="hint">仅处理每个 HTML 请求中前 N 条订单的驾车距离与地址类型；密钥与 Sheet 仍由环境变量配置。</p>
              </div>
              {token_block}
              <div class="cfg-form-actions">
                <button type="submit" class="cfg-btn"{form_disabled}>保存</button>
                <span class="cfg-muted">写入 <code>config/ew_settings.env</code> 并立即 reload 环境变量</span>
              </div>
            </form>
          </div>
        </section>
        """

    note = """
    <ul>
      <li><strong>密钥</strong>（Maps、服务账号等）请勿在此页填写；请编辑 <code>.env</code> 或 <code>config/api.secrets.env</code> 后<strong>重启</strong>。</li>
      <li>Google Maps：请在 GCP 启用 <strong>Distance Matrix</strong> 与 <strong>Geocoding</strong> API；若设置 <code>ORDER_PLACES_LAND_USE=1</code>，另启用 <strong>Places API</strong>（下单页会显示 Land use: warehouse / commercial / residential 等）。</li>
      <li>下单页调试可加 <code>?debug_maps=1</code>。</li>
    </ul>
    """

    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
  <meta name="theme-color" content="#0f172a"/>
  <title>EW · 配置</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700&amp;display=swap" rel="stylesheet"/>
  <style>
{LAYOUT_SHELL_CSS}
{_CFG_CSS}
  </style>
</head>
<body>
  <div class="ew-shell">
{render_sidebar_nav("config", session_user=session_user, role=role)}
    <main class="ew-main">
      <div class="cfg-wrap">
        <header class="cfg-top">
          <h1><span class="cfg-brand">EW</span> 配置</h1>
          <p class="cfg-lead">{"Boss 只读：查看运行环境与集成状态。" if read_only else "运行环境概览（高对比度）；可在下方保存 <strong>非敏感</strong> 项。集成密钥仅脱敏显示。"}</p>
        </header>
{flash_html}
{form_html}
        <section class="cfg-section" aria-label="运行环境">
          <h2>运行环境</h2>
          <div class="cfg-kv">{kv_html}</div>
        </section>

        <section class="cfg-section" aria-label="集成状态">
          <h2>集成状态</h2>
          <div class="cfg-kv" style="padding: 0; overflow: hidden;">
            <table class="cfg-table">
              <thead><tr><th>集成</th><th>状态</th><th>环境变量</th><th>预览</th></tr></thead>
              <tbody>{"".join(table_rows)}</tbody>
            </table>
          </div>
        </section>

        <section class="cfg-section" aria-label="说明">
          <h2>说明</h2>
          <div class="cfg-note">{note}</div>
        </section>

        <footer class="cfg-foot">
          <a href="/">首页</a>
          <span> · </span>
          <a href="/health">/health</a>
          <span> · </span>
          <a href="/f/read/order?fmt=html&amp;limit=20">下单</a>
        </footer>
      </div>
    </main>
  </div>
</body>
</html>"""
