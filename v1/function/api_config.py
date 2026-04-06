"""
Central API configuration: load env files and expose getters for keys / future endpoints.

Load order (later overrides earlier for duplicate variable names):
  1. Repository root `.env`
  2. `config/api.secrets.env` (optional; use for API keys only)
  3. `config/ew_settings.env` (optional; 可由 /config 页面保存的非敏感项，如 ORDER_GOOGLE_MILES_MAX)

After that, if root `.env` defines `DATABASE_URL` or `EW_SELF_REGISTER`, those values are
applied again so local `.env` wins over `api.secrets.env` / `ew_settings.env` for these keys
(same reason as DB URL: avoid accidental empty override in another file).

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


def _database_url_from_root_dotenv() -> str | None:
    """Read only DATABASE_URL from repo root `.env` (BOM-safe), without applying other keys."""
    p = _ROOT / ".env"
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() != "DATABASE_URL":
            continue
        v = val.strip().strip('"').strip("'")
        return v if v else None
    return None


def _ew_self_register_from_root_dotenv() -> str | None:
    """If repo root `.env` defines EW_SELF_REGISTER, return its value (may be empty); else None."""
    p = _ROOT / ".env"
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() != "EW_SELF_REGISTER":
            continue
        return val.strip().strip('"').strip("'")
    return None


def _load_api_env() -> None:
    # utf-8-sig: strip BOM so keys are not read as "\ufeffGOOGLE_..."
    _enc = "utf-8-sig"
    load_dotenv(_ROOT / ".env", override=False, encoding=_enc)
    secrets = _CONFIG_DIR / "api.secrets.env"
    if secrets.is_file():
        load_dotenv(secrets, override=True, encoding=_enc)
    runtime = _CONFIG_DIR / "ew_settings.env"
    if runtime.is_file():
        load_dotenv(runtime, override=True, encoding=_enc)
    # 根目录 .env 里的 DATABASE_URL 优先生效，避免 api.secrets.env 误写覆盖后连到无 ew_orders 的库
    du = _database_url_from_root_dotenv()
    if du:
        os.environ["DATABASE_URL"] = du
    # 同上：EW_SELF_REGISTER 若在根 .env 中定义，最后覆盖（避免 secrets 里空 EW_SELF_REGISTER= 关掉自助注册）
    ew_sr = _ew_self_register_from_root_dotenv()
    if ew_sr is not None:
        os.environ["EW_SELF_REGISTER"] = ew_sr


_load_api_env()

# 由 /config 保存页写入，仅允许白名单键
EW_SETTINGS_FILE = _CONFIG_DIR / "ew_settings.env"


def _mask_secret(value: str, *, keep_start: int = 4, keep_end: int = 4) -> str:
    v = value.strip()
    if len(v) <= keep_start + keep_end:
        return "****" if v else "—"
    return v[:keep_start] + "…" + v[-keep_end:]


def _normalize_maps_key(raw: str) -> str:
    """Strip spaces, ASCII quotes, and common Unicode ‘smart’ quotes from pasted .env values."""
    s = raw.strip().strip("'\"")
    for ch in ("\u201c", "\u201d", "\u2018", "\u2019"):  # “ ” ‘ ’
        s = s.replace(ch, "")
    return s.strip()


def _maps_key_from_optional_file() -> str | None:
    """Single-line fallback if env vars are empty (config/google_maps_api_key.txt)."""
    p = _CONFIG_DIR / "google_maps_api_key.txt"
    if not p.is_file():
        return None
    try:
        line = p.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    for raw in line.splitlines():
        t = raw.strip()
        if t and not t.startswith("#"):
            return _normalize_maps_key(t)
    return None


def google_maps_api_key() -> str | None:
    """Maps Platform: Distance Matrix, Geocoding, etc."""
    k = (
        os.environ.get("GOOGLE_MAPS_API_KEY")
        or os.environ.get("MAPS_API_KEY")
        or _maps_key_from_optional_file()
        or ""
    )
    k = _normalize_maps_key(k)
    return k or None


# Backwards-compatible name used by maps_distance
def maps_api_key() -> str | None:
    return google_maps_api_key()


def reload_api_env() -> None:
    """Tests or long-running workers after file change (optional)."""
    _load_api_env()


def ew_smtp_settings() -> dict[str, Any] | None:
    """
    发信（使用守则邮件等）。需设置 EW_SMTP_HOST；EW_SMTP_FROM 缺省时用 EW_SMTP_USER。
    EW_SMTP_SSL=1 时用 SMTP_SSL（常见 465）；否则 EW_SMTP_TLS（默认 1）对 587 等走 STARTTLS。
    """
    host = (os.environ.get("EW_SMTP_HOST") or "").strip()
    if not host:
        return None
    port_s = (os.environ.get("EW_SMTP_PORT") or "587").strip()
    try:
        port = int(port_s or "587")
    except ValueError:
        port = 587
    user = (os.environ.get("EW_SMTP_USER") or "").strip()
    password = (os.environ.get("EW_SMTP_PASSWORD") or "").strip()
    from_addr = (os.environ.get("EW_SMTP_FROM") or user or "").strip()
    if not from_addr:
        return None
    use_ssl = (os.environ.get("EW_SMTP_SSL") or "").strip().lower() in ("1", "true", "yes", "on")
    use_starttls = (os.environ.get("EW_SMTP_TLS", "1") or "").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    if use_ssl:
        use_starttls = False
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_addr": from_addr,
        "use_ssl": use_ssl,
        "use_starttls": use_starttls,
    }


def ew_smtp_configured() -> bool:
    return ew_smtp_settings() is not None


def ew_admin_order_sync_label() -> str:
    """Shown next to the order page one-click sync button (bookmark with ?token=)."""
    v = (os.environ.get("EW_ADMIN_DISPLAY_NAME") or "").strip()
    return v if v else "Simon"


def save_order_google_miles_max_ui(value: int) -> None:
    """
    将 ORDER_GOOGLE_MILES_MAX 写入 config/ew_settings.env 并 reload 环境。
    仅用于配置页；数值范围由调用方校验。
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    text = (
        "# Auto-written by EW /config — overrides .env for this key only.\n"
        f"ORDER_GOOGLE_MILES_MAX={int(value)}\n"
    )
    EW_SETTINGS_FILE.write_text(text, encoding="utf-8")
    reload_api_env()


def configuration_snapshot() -> dict[str, Any]:
    """
    非敏感运行时信息（路径、文件是否存在、常用 env 开关），供 /config 页面展示。
    """
    sa = (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    sa_path = Path(sa).expanduser() if sa else None
    return {
        "repo_root": str(_ROOT),
        "dot_env_exists": (_ROOT / ".env").is_file(),
        "api_secrets_env_exists": (_CONFIG_DIR / "api.secrets.env").is_file(),
        "ew_settings_env_exists": EW_SETTINGS_FILE.is_file(),
        "order_google_miles_max": (os.environ.get("ORDER_GOOGLE_MILES_MAX") or "30").strip() or "30",
        "order_places_land_use": (os.environ.get("ORDER_PLACES_LAND_USE") or "0").strip() or "0",
        "admin_token_configured": bool(os.environ.get("EW_ADMIN_TOKEN", "").strip()),
        "ew_smtp_configured": ew_smtp_configured(),
        "ew_self_register_raw": (os.environ.get("EW_SELF_REGISTER") or "").strip(),
        "ew_self_register_on": (os.environ.get("EW_SELF_REGISTER") or "").strip().lower()
        in ("1", "true", "yes", "on"),
        "google_application_credentials_set": bool(sa),
        "google_application_credentials_file_ok": bool(sa_path and sa_path.is_file()),
        "google_application_credentials_basename": sa_path.name if sa_path else None,
    }


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
