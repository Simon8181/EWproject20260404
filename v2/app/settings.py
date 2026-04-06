from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _dotenv_fill_missing(path: Path) -> None:
    """If a key is unset or blank in os.environ, set it from the file.

    ``load_dotenv(..., override=False)`` skips keys that already exist, including
    when the shell set ``VAR=`` (empty). That makes ``GEMINI_API_KEY`` in ``.env``
    appear \"ignored\" even though the file has a value.
    """
    if not path.is_file():
        return
    for k, v in dotenv_values(path).items():
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        cur = os.environ.get(k)
        if cur is None or not str(cur).strip():
            os.environ[k] = s


def load_env() -> None:
    root = _project_root()
    load_dotenv(root / "config" / ".env", override=False)
    load_dotenv(root / "config" / ".env.local", override=True)
    _dotenv_fill_missing(root / "config" / ".env")


@dataclass(frozen=True)
class Settings:
    app_env: str
    db_path: Path
    mapping_path: Path
    google_credentials_path: Path


def get_settings() -> Settings:
    load_env()
    root = _project_root()
    db_path = Path(os.environ.get("V2_DB_PATH", str(root / "data" / "v2.sqlite3")))
    if not db_path.is_absolute():
        db_path = (root / db_path).resolve()
    mapping_path = Path(
        os.environ.get("V2_LOAD_MAPPING_PATH", str(root / "config" / "load_mapping.yaml"))
    )
    if not mapping_path.is_absolute():
        mapping_path = (root / mapping_path).resolve()
    creds_path = _resolve_credentials_path(root)
    return Settings(
        app_env=(os.environ.get("APP_ENV", "dev") or "dev").strip().lower(),
        db_path=db_path,
        mapping_path=mapping_path,
        google_credentials_path=creds_path,
    )


def _resolve_credentials_path(v2_root: Path) -> Path:
    raw = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        str(v2_root / "config" / "service_account.json"),
    )
    p = Path(raw)
    if not p.is_absolute():
        p = (v2_root / p).resolve()
    if p.exists():
        return p
    local_default = v2_root / "config" / "service_account.json"
    if local_default.exists():
        return local_default
    return p

