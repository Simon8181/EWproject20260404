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
    usage_email_ok: bool = False,
    usage_email_err: str | None = None,
    smtp_configured: bool = False,
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

    flash_usage = ""
    if usage_email_ok:
        flash_usage = (
            '<div class="flash flash--ok" role="status">'
            '<span class="flash-icon" aria-hidden="true">'
            '<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
            '<polyline points="22 4 12 14.01 9 11.01"/>'
            "</svg>"
            "</span>"
            '<div class="flash-text">'
            "<strong>已发出</strong>"
            "<span>说明已发到你的邮箱；若未看到，请到垃圾箱里找一下。附件为 PDF。</span>"
            "</div>"
            "</div>"
        )
    elif usage_email_err:
        flash_usage = (
            '<div class="flash flash--err" role="alert">'
            '<span class="flash-icon flash-icon--err" aria-hidden="true">'
            '<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
            '<circle cx="12" cy="12" r="10"/>'
            '<line x1="12" y1="8" x2="12" y2="12"/>'
            '<line x1="12" y1="16" x2="12.01" y2="16"/>'
            "</svg>"
            "</span>"
            '<div class="flash-text">'
            "<strong>未能发送</strong>"
            f"<span>{html.escape(usage_email_err)}</span>"
            "</div>"
            "</div>"
        )

    smtp_hint = (
        (
            '<div class="usage-mail-callout usage-mail-callout--warn" role="note">'
            "<strong>暂时不可用</strong>"
            "<p>管理员还未配置发信（环境变量 <code>EW_SMTP_HOST</code> 等）。配好后此处即可使用。</p>"
            "</div>"
        )
        if not smtp_configured
        else (
            '<div class="usage-mail-callout usage-mail-callout--info" role="note">'
            "<strong>你可以这样理解</strong>"
            "<p>点一次按钮，系统就向下方邮箱投递<strong>一封</strong>带 PDF 附件的邮件；内容随当前服务版本生成。</p>"
            "</div>"
        )
    )
    submit_disabled = "" if smtp_configured else " disabled"
    submit_aria = (
        ""
        if smtp_configured
        else ' aria-disabled="true" title="发信未配置"'
    )
    usage_mail_submit_btn = (
        '        <button type="submit" class="btn primary usage-mail-submit"'
        + submit_aria
        + submit_disabled
        + ">发到我邮箱</button>\n"
    )

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
    <section id="ew-doc-email" class="usage-mail doc-email" aria-labelledby="ew-doc-heading">
"""
        + flash_usage
        + """
      <div class="usage-mail-inner">
        <h2 id="ew-doc-heading">邮件领取工作台说明</h2>
        <p class="usage-mail-lead">这是<strong>给自己发存档</strong>：把当前平台怎么用（角色、订单、报价规则等）打成一份 PDF，发到你的邮箱，便于留存或转给同事。不用于广告或订阅。</p>
        <p class="doc-email-capsule">每次提交只发一封邮件，带 PDF 附件；须先登录。</p>
"""
        + smtp_hint
        + """
        <form method="post" action="/docs/ew-usage-guide-v1/email" class="usage-mail-form" aria-describedby="ew-doc-heading">
          <div class="usage-mail-field">
            <label class="usage-mail-label" for="usage-email-to">发到哪个邮箱</label>
            <input
              id="usage-email-to"
              class="usage-mail-input"
              type="email"
              name="to"
              required
              autocomplete="email"
              inputmode="email"
              placeholder="你的邮箱地址"
            />
          </div>
          <div class="usage-mail-actions">
"""
        + usage_mail_submit_btn
        + """
          </div>
          <p class="usage-mail-footnote">仅投递本工作台说明文件，不作营销推广。</p>
        </form>
      </div>
    </section>
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
  <script>
(function () {
  try {
    var u = new URL(window.location.href);
    if (u.searchParams.has("usage_email") || u.searchParams.has("usage_email_err")) {
      var el = document.getElementById("ew-doc-email");
      if (el) {
        requestAnimationFrame(function () {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      }
      var path = window.location.pathname + (window.location.hash || "");
      if (u.search) {
        history.replaceState(null, "", path);
      }
    }
  } catch (e) {}
})();
  </script>
</body>
</html>
"""
    )
