"""Extract US ZIP from free-text：仅保留前 5 位（忽略 ZIP+4 后缀）。"""

from __future__ import annotations

import re

_US_ZIP = re.compile(r"\b(\d{5})(?:-(\d{4}))?\b")


def first_us_zip(text: str) -> str:
    """First US ZIP in text, **5 digits only**（`12345-6789` / 连续 9 位均只取前 5 位）；无则空串。"""
    if not text or not str(text).strip():
        return ""
    s = str(text)
    m = _US_ZIP.search(s)
    if m:
        return m.group(1)
    m9 = re.search(r"\b(\d{5})(\d{4})\b", s)
    if m9:
        return m9.group(1)
    return ""


def is_valid_us_zip5(z: str) -> bool:
    """美国本土常用 5 位数字邮编（格式化数据写库前校验）。"""
    return bool(re.fullmatch(r"\d{5}", (z or "").strip()))


def strip_us_zip_plus4_from_text(s: str) -> str:
    """
    将整段地址里的美国 ZIP+4 写成 5 位（`12345-6789` / 连续 `123456789` → `12345`）。
    用于 Geocoding formatted 行、避免在「起运/目的」长文案里仍出现后四位。
    """
    if not s or not str(s).strip():
        return str(s or "")
    out = re.sub(r"\b(\d{5})-(\d{4})\b", r"\1", str(s))
    return re.sub(r"\b(\d{5})(\d{4})\b", r"\1", out)
