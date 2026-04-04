"""Shared left navigation HTML for EW web pages (role-aware)."""

from __future__ import annotations

import html
from typing import Literal
from urllib.parse import quote

from function.auth_roles import can_manage_users, can_view_config, can_view_integration

NavActive = Literal["home", "order", "health", "config", "users", "integration"]

_ORDER_HREF = "/f/read/order?fmt=html&amp;limit=50"


def render_sidebar_nav(
    active: NavActive,
    *,
    session_user: str | None = None,
    role: str | None = None,
) -> str:
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

    login_href = "/login?next=" + quote("/f/read/order?fmt=html", safe="")
    register_href = "/register?next=" + quote("/f/read/order?fmt=html", safe="")
    auth_html = (
        f'<div class="ew-nav-auth"><span class="ew-nav-user">{html.escape(session_user)}</span>'
        f'<a class="ew-nav-link ew-nav-link--sub" href="/logout">退出</a></div>'
        if session_user
        else (
            f'<div class="ew-nav-auth ew-nav-auth--row">'
            f'<a class="ew-nav-link ew-nav-link--sub" href="{login_href}">登录</a>'
            f'<a class="ew-nav-link ew-nav-link--sub" href="{register_href}">注册</a>'
            f"</div>"
        )
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
