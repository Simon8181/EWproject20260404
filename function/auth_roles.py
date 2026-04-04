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


def normalize_role(raw: str | None) -> Role | None:
    if not raw:
        return None
    s = str(raw).strip().lower()
    if s in ROLES:
        return s  # type: ignore[return-value]
    return None


def can_sync_orders(role: str | None) -> bool:
    return normalize_role(role) is not None


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
    r = normalize_role(role) or "broker"
    zh = ROLE_LABEL_ZH.get(r, r)
    return f"{username} · {zh}"
