#!/usr/bin/env python3
"""One-shot: verify GOOGLE_MAPS_API_KEY is visible to api_config (no secret printed)."""

from __future__ import annotations

import sys
from pathlib import Path

# Repo root = parent of scripts/
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from function.api_config import (  # noqa: E402
    _CONFIG_DIR,
    _ROOT as API_ROOT,
    google_maps_api_key,
)


def main() -> None:
    k = google_maps_api_key()
    print("api_config repo_root:", API_ROOT)
    print(".env exists:", (API_ROOT / ".env").is_file())
    print("config/api.secrets.env exists:", (_CONFIG_DIR / "api.secrets.env").is_file())
    print("config/ew_settings.env exists:", (_CONFIG_DIR / "ew_settings.env").is_file())
    print("config/google_maps_api_key.txt exists:", (_CONFIG_DIR / "google_maps_api_key.txt").is_file())
    if k:
        print("GOOGLE_MAPS_API_KEY: loaded OK (length", len(k), ")")
        sys.exit(0)
    print("GOOGLE_MAPS_API_KEY: NOT loaded — set in .env or config/api.secrets.env or config/google_maps_api_key.txt, then restart uvicorn.")
    sys.exit(1)


if __name__ == "__main__":
    main()
