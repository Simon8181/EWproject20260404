"""
Central API configuration: load env files and expose getters for keys / future endpoints.

Load order (later overrides earlier for duplicate variable names):
  1. Repository root `.env`
  2. `config/api.secrets.env` (optional; use for API keys only)

Add new providers by extending `config/api.secrets.env` + a small getter below.

Best practice (summary)
----------------------
- Never commit secrets; use env injection or a secret manager in production.
- Restrict each cloud API key to the minimum APIs and apps (IP / referrer).
- Rotate keys periodically; admin UI here shows only status + masked preview.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _ROOT / "config"


def _load_api_env() -> None:
    load_dotenv(_ROOT / ".env")
    secrets = _CONFIG_DIR / "api.secrets.env"
    if secrets.is_file():
        load_dotenv(secrets, override=True)


_load_api_env()


def _mask_secret(value: str, *, keep_start: int = 4, keep_end: int = 4) -> str:
    v = value.strip()
    if len(v) <= keep_start + keep_end:
        return "****" if v else "—"
    return v[:keep_start] + "…" + v[-keep_end:]


def google_maps_api_key() -> str | None:
    """Maps Platform: Distance Matrix, Geocoding, etc."""
    k = (
        os.environ.get("GOOGLE_MAPS_API_KEY")
        or os.environ.get("MAPS_API_KEY")
        or ""
    ).strip()
    return k or None


# Backwards-compatible name used by maps_distance
def maps_api_key() -> str | None:
    return google_maps_api_key()


def reload_api_env() -> None:
    """Tests or long-running workers after file change (optional)."""
    _load_api_env()


def integration_snapshot() -> list[dict[str, Any]]:
    """
    Rows for the admin status table. Extend when adding APIs (Stripe, OpenAI, …).
    """
    gmk = google_maps_api_key()
    sa_path = (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    sa_ok = bool(sa_path) and Path(sa_path).expanduser().is_file()
    db_ok = bool(
        (os.environ.get("DATABASE_URL") or "").strip()
        or (os.environ.get("PGDATABASE") or "").strip()
    )

    rows: list[dict[str, Any]] = [
        {
            "id": "google_maps",
            "name": "Google Maps (Distance Matrix / Geocoding)",
            "configured": gmk is not None,
            "env_hint": "GOOGLE_MAPS_API_KEY",
            "masked_preview": _mask_secret(gmk) if gmk else None,
        },
        {
            "id": "google_sheets",
            "name": "Google Sheets (service account JSON)",
            "configured": sa_ok,
            "env_hint": "GOOGLE_APPLICATION_CREDENTIALS",
            "masked_preview": str(Path(sa_path).name) if sa_ok else None,
        },
        {
            "id": "postgres",
            "name": "PostgreSQL",
            "configured": db_ok,
            "env_hint": "DATABASE_URL or PG*",
            "masked_preview": "set" if db_ok else None,
        },
    ]
    return rows
