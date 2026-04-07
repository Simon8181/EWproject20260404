"""Resolve v2 SQLite path and load `v2/config/.env` so v3 shares the same DB config as v2."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _v2_root() -> Path:
    return _repo_root() / "v2"


def _dotenv_fill_missing(path: Path) -> None:
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
    v2 = _v2_root()
    load_dotenv(v2 / "config" / ".env", override=False)
    load_dotenv(v2 / "config" / ".env.local", override=True)
    _dotenv_fill_missing(v2 / "config" / ".env")
    # v3 总闸：每次从磁盘同步，避免旧进程里 os.environ 未更新或首次未写入 .env
    for path in (v2 / "config" / ".env", v2 / "config" / ".env.local"):
        if not path.is_file():
            continue
        raw = dotenv_values(path).get("V3_SHEET_ROW_AI_ENABLED")
        if raw is not None and str(raw).strip():
            os.environ["V3_SHEET_ROW_AI_ENABLED"] = str(raw).strip()


@dataclass(frozen=True)
class Settings:
    db_path: Path


def get_settings() -> Settings:
    load_env()
    v2 = _v2_root()
    db_path = Path(os.environ.get("V2_DB_PATH", str(v2 / "data" / "v2.sqlite3")))
    if not db_path.is_absolute():
        db_path = (v2 / db_path).resolve()
    return Settings(db_path=db_path)
