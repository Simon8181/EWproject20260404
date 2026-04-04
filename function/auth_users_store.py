"""User accounts in config/ew_users.yaml (gitignored). Passwords: PBKDF2-HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Any

import yaml

from function.auth_roles import normalize_role

_REPO = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _REPO / "config"
_USERS_FILE = _CONFIG_DIR / "ew_users.yaml"
_ITERATIONS = 260_000


def users_file_path() -> Path:
    return _USERS_FILE


def _pbkdf2_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=32)


def _load_raw() -> dict[str, Any]:
    if not _USERS_FILE.is_file():
        return {"version": 1, "users": {}}
    try:
        data = yaml.safe_load(_USERS_FILE.read_text(encoding="utf-8"))
    except OSError:
        return {"version": 1, "users": {}}
    if not isinstance(data, dict):
        return {"version": 1, "users": {}}
    users = data.get("users")
    if not isinstance(users, dict):
        data["users"] = {}
    return data


def _save_raw(data: dict[str, Any]) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    _USERS_FILE.write_text(text, encoding="utf-8")


def user_count() -> int:
    return len(_load_raw().get("users") or {})


def user_exists(username: str) -> bool:
    users = _load_raw().get("users") or {}
    return username.strip() in users


def register_new_user(username: str, password: str) -> str:
    """Create account; first user → developer, else broker. Returns role."""
    un = username.strip()
    if not un or len(un) > 64:
        raise ValueError("无效用户名")
    if user_exists(un):
        raise ValueError("用户名已被占用")
    n = user_count()
    role = "developer" if n == 0 else "broker"
    set_password(un, password, role)
    return role


def list_users() -> list[dict[str, str]]:
    raw = _load_raw()
    users = raw.get("users") or {}
    out: list[dict[str, str]] = []
    for uname, row in sorted(users.items(), key=lambda x: x[0].lower()):
        if not isinstance(row, dict):
            continue
        role = normalize_role(str(row.get("role", "")))
        if not role:
            continue
        out.append({"username": str(uname), "role": role})
    return out


def verify_password(username: str, password: str) -> str | None:
    """Return role if ok, else None."""
    raw = _load_raw()
    users = raw.get("users") or {}
    row = users.get(username.strip())
    if not isinstance(row, dict):
        return None
    role = normalize_role(str(row.get("role", "")))
    if not role:
        return None
    salt_hex = str(row.get("salt", "")).strip()
    hash_hex = str(row.get("hash", "")).strip()
    if not salt_hex or not hash_hex:
        return None
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return None
    got = _pbkdf2_hash(password, salt)
    if not hmac.compare_digest(got, expected):
        return None
    return role


def set_password(username: str, password: str, role: str) -> None:
    r = normalize_role(role)
    if not r:
        raise ValueError(f"invalid role: {role!r}")
    un = username.strip()
    if not un or len(un) > 64:
        raise ValueError("invalid username")
    if len(password) < 6:
        raise ValueError("password too short (min 6)")
    raw = _load_raw()
    users = dict(raw.get("users") or {})
    salt = secrets.token_bytes(16)
    h = _pbkdf2_hash(password, salt)
    users[un] = {
        "role": r,
        "salt": salt.hex(),
        "hash": h.hex(),
    }
    raw["users"] = users
    raw["version"] = 1
    _save_raw(raw)


def delete_user(username: str) -> bool:
    un = username.strip()
    raw = _load_raw()
    users = dict(raw.get("users") or {})
    if un not in users:
        return False
    del users[un]
    raw["users"] = users
    _save_raw(raw)
    return True


def set_role(username: str, role: str) -> None:
    r = normalize_role(role)
    if not r:
        raise ValueError(f"invalid role: {role!r}")
    un = username.strip()
    raw = _load_raw()
    users = dict(raw.get("users") or {})
    row = users.get(un)
    if not isinstance(row, dict):
        raise KeyError("user not found")
    row = dict(row)
    row["role"] = r
    users[un] = row
    raw["users"] = users
    _save_raw(raw)
