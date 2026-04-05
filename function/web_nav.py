"""Shared left navigation HTML for EW web pages (role-aware)."""

from __future__ import annotations

import html
from typing import Literal

from function.auth_roles import (
    can_manage_users,
    can_view_config,
    can_view_integration,
    nav_user_caption,
)

NavActive = Literal["home", "order", "health", "config", "users", "integration"]

_ORDER_HREF = "/f/read/order?fmt=html&amp;limit=50"


def render_sidebar_nav(
    active: NavActive,
    *,
    session_user: str | None = None,
    role: str | None = None,
) -> str:
    # 仅已登录（有会话展示名）时渲染侧栏；未登录页面只显示主内容区
    if not (session_user or "").strip():
        return ""

    def link(href: str, label: str, key: NavActive) -> str:
        cls = "ew-nav-link"
        if active == key:
            cls += " ew-nav-link--active"
        return f'        <a class="{cls}" href="{href}">{label}</a>'

    parts: list[str] = [
        link("/", "首页", "home"),
        link(_ORDER_HREF, "下单", "order"),
    ]
    if role is not None and can_view_config(role):
        parts.append(link("/config", "配置", "config"))
    if role is not None and can_manage_users(role):
        parts.append(link("/users", "用户", "users"))
    if role is not None and can_view_integration(role):
        parts.append(link("/admin", "集成", "integration"))
    parts.append(link("/health", "Health", "health"))

    nav_inner = "\n".join(parts)

    su = (session_user or "").strip()
    # 调用方通常已传入 nav_user_caption；若仅传登录名则在此补全「· 角色」
    auth_label = su if " · " in su else nav_user_caption(su, role)

    auth_html = (
        f'<div class="ew-nav-auth"><span class="ew-nav-user">{html.escape(auth_label)}</span>'
        f'<a class="ew-nav-link ew-nav-link--sub" href="/logout">退出</a></div>'
    )
    return f"""
    <aside class="ew-nav" aria-label="主导航">
      <a class="ew-nav-brand" href="/">
        <span class="ew-nav-brand-mark">EW</span>
        <span class="ew-nav-brand-sub">Sheet</span>
      </a>
      <nav class="ew-nav-list" aria-label="页面">
{nav_inner}
      </nav>
{auth_html}
    </aside>
"""
