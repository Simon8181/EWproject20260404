"""Role names and permission checks for EW web UI."""

from __future__ import annotations

from typing import Literal

Role = Literal["developer", "boss", "broker"]

ROLES: tuple[str, ...] = ("developer", "boss", "broker")

ROLE_LABEL_ZH: dict[str, str] = {
    "developer": "开发者",
    "boss": "Boss",
    "broker": "Broker",
}

# 侧栏、技能区等：角色展示为英文
ROLE_LABEL_EN: dict[str, str] = {
    "developer": "Developer",
    "boss": "Boss",
    "broker": "Broker",
}


def normalize_role(raw: str | None) -> Role | None:
    if not raw:
        return None
    s = str(raw).strip().lower()
    if s in ROLES:
        return s  # type: ignore[return-value]
    return None


def can_sync_orders(role: str | None) -> bool:
    """Sheet→Postgres 同步（下单页「从 Sheet 刷新」）：仅开发者；Boss/Broker 只读列表。"""
    return normalize_role(role) == "developer"


def can_view_config(role: str | None) -> bool:
    r = normalize_role(role)
    return r in ("developer", "boss")


def can_edit_config(role: str | None) -> bool:
    return normalize_role(role) == "developer"


def can_manage_users(role: str | None) -> bool:
    return normalize_role(role) == "developer"


def can_view_integration(role: str | None) -> bool:
    r = normalize_role(role)
    return r in ("developer", "boss")


def nav_user_caption(username: str, role: str | None) -> str:
    """侧栏等：登录名 + 英文角色；无有效角色时仅登录名（不臆造 Broker）。"""
    u = (username or "").strip()
    if not u:
        return ""
    r = normalize_role(role)
    if not r:
        return u
    label = ROLE_LABEL_EN.get(r, r.title())
    return f"{u} · {label}"
