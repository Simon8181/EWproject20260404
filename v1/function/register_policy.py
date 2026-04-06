"""Who may self-register and optional EW_REGISTRATION_CODE check."""

from __future__ import annotations

import hmac
import os

from function.auth_users_store import user_count


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def registration_allowed() -> bool:
    """True if first user (bootstrap) or EW_SELF_REGISTER=1."""
    if user_count() == 0:
        return True
    return _env_truthy("EW_SELF_REGISTER")


def registration_code_configured() -> bool:
    return bool((os.environ.get("EW_REGISTRATION_CODE") or "").strip())


def verify_registration_code(submitted: str | None) -> bool:
    expected = (os.environ.get("EW_REGISTRATION_CODE") or "").strip()
    if not expected:
        return True
    s = (submitted or "").strip()
    try:
        return hmac.compare_digest(
            s.encode("utf-8"),
            expected.encode("utf-8"),
        )
    except Exception:
        return False
