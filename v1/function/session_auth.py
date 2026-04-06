"""Signed cookie session (v2: username + role). Key: EW_SESSION_SECRET or EW_ADMIN_TOKEN."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from starlette.requests import Request

from function.auth_roles import normalize_role

ADMIN_SESSION_COOKIE = "ew_admin_session"
SESSION_MAX_AGE_SEC = 30 * 24 * 3600
SESSION_VERSION = 2


def _session_signing_key() -> bytes | None:
    secret = (os.environ.get("EW_SESSION_SECRET") or "").strip()
    if secret:
        return hashlib.sha256(secret.encode("utf-8")).digest()
    tok = (os.environ.get("EW_ADMIN_TOKEN") or "").strip()
    if tok:
        return hashlib.sha256((tok + "\x00ew_session_v2").encode("utf-8")).digest()
    return None


def _b64decode_padded(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue_session_value(username: str, role: str) -> str:
    key = _session_signing_key()
    if not key:
        return ""
    r = normalize_role(role)
    if not r:
        return ""
    exp = int(time.time()) + SESSION_MAX_AGE_SEC
    payload = json.dumps(
        {"exp": exp, "v": SESSION_VERSION, "u": username.strip(), "r": r},
        separators=(",", ":"),
    ).encode("utf-8")
    sig = hmac.new(key, payload, hashlib.sha256).digest()
    pb = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    sb = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{pb}.{sb}"


def read_session(request: Request) -> dict[str, str] | None:
    """Return {'username','role'} if valid v2 cookie, else None."""
    raw = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not raw:
        return None
    key = _session_signing_key()
    if not key:
        return None
    try:
        parts = raw.split(".", 1)
        if len(parts) != 2:
            return None
        payload = _b64decode_padded(parts[0])
        sig = _b64decode_padded(parts[1])
        expected = hmac.new(key, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        obj = json.loads(payload.decode("utf-8"))
        if int(obj.get("exp", 0)) < time.time():
            return None
        if int(obj.get("v", 0)) != SESSION_VERSION:
            return None
        u = str(obj.get("u", "")).strip()
        r = normalize_role(str(obj.get("r", "")))
        if not u or not r:
            return None
        return {"username": u, "role": r}
    except Exception:
        return None


def is_logged_in(request: Request) -> bool:
    return read_session(request) is not None


def is_admin_logged_in(request: Request) -> bool:
    """Backward-compatible name: any valid session."""
    return is_logged_in(request)


def session_can_use_app(request: Request) -> bool:
    """True if logged in with v2 session."""
    return read_session(request) is not None


def safe_next_path(raw: str | None, *, default: str = "/f/read/order?fmt=html") -> str:
    if not raw:
        return default
    s = str(raw).strip()
    if not s.startswith("/") or s.startswith("//"):
        return default
    return s


def signing_key_configured() -> bool:
    return _session_signing_key() is not None
