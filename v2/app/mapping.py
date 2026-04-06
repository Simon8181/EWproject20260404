from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml


@dataclass(frozen=True)
class TabConfig:
    key: str
    worksheet: str
    data_start_row: int
    key_column_letter: str
    status_mode: str
    status_value: str | None
    status_column_letter: str | None
    status_map: dict[str, str]
    status_default: str
    trouble_column_letter: str | None
    trouble_truthy: tuple[str, ...]
    use_color_status: bool
    color_status_map: dict[str, str]


@dataclass(frozen=True)
class LoadMapping:
    spreadsheet_id: str
    tabs: tuple[TabConfig, ...]


def load_mapping(path: Path) -> LoadMapping:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    spreadsheet_id = _normalize_spreadsheet_id(str(raw.get("spreadsheet_id", "")).strip())
    if not spreadsheet_id:
        raise ValueError("mapping 缺少 spreadsheet_id")

    tabs_cfg: list[TabConfig] = []
    for tab in raw.get("tabs", []):
        status = tab.get("status") or {}
        trouble = tab.get("trouble_case") or {}
        status_map = {
            str(k).strip().lower(): str(v).strip()
            for k, v in (status.get("map") or {}).items()
            if str(k).strip() and str(v).strip()
        }
        tabs_cfg.append(
            TabConfig(
                key=str(tab.get("key", "")).strip(),
                worksheet=str(tab.get("worksheet", "")).strip(),
                data_start_row=int(tab.get("data_start_row", 2) or 2),
                key_column_letter=str(tab.get("key_column_letter", "C")).strip().upper(),
                status_mode=str(status.get("mode", "fixed")).strip().lower(),
                status_value=(str(status.get("value", "")).strip() or None),
                status_column_letter=(
                    str(status.get("column_letter", "")).strip().upper() or None
                ),
                status_map=status_map,
                status_default=str(status.get("default", "pending_quote")).strip()
                or "pending_quote",
                trouble_column_letter=(
                    str(trouble.get("column_letter", "")).strip().upper() or None
                ),
                trouble_truthy=tuple(
                    str(v).strip().lower()
                    for v in (trouble.get("truthy") or ["1", "true", "yes", "y"])
                ),
                use_color_status=bool(tab.get("use_color_status", False)),
                color_status_map={
                    str(k).strip().lower(): str(v).strip()
                    for k, v in (tab.get("color_status_map") or {}).items()
                    if str(k).strip() and str(v).strip()
                },
            )
        )
    if not tabs_cfg:
        raise ValueError("mapping 缺少 tabs 配置")
    return LoadMapping(spreadsheet_id=spreadsheet_id, tabs=tuple(tabs_cfg))


def _normalize_spreadsheet_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    # Accept full Google Sheet URL and extract the ID from /d/{id}
    m = re.search(r"/d/([a-zA-Z0-9-_]+)", s)
    if m:
        return m.group(1)
    return s

