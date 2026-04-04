"""
起始地（起运）展示与地图解析。

系统约定：
- 卡片展示优先输出 **City, ST 12345**（或中文「城市 + 邮编」）形式。
- `ship_from` 常为货描；若无地址信号，从 **`consignee_contact`** 中带「提货地址 / 发货地址」等标签的段落解析。
- 地图链接使用 **`resolve_origin_for_order`** 返回的原文，保证可搜到真实提货地。

目的地址不在此模块处理。
"""

from __future__ import annotations

import re
from typing import Any

# --- shared US fragments ---
_ZIP = r"\d{5}(?:-\d{4})?"
_ST = r"[A-Z]{2}"

# … , City , ST ZIP
_US_2COMMA = re.compile(
    rf",\s*([^,\n]+?)\s*,\s*({_ST})\s*({_ZIP})\b",
    re.IGNORECASE,
)
# … , City , ST , ZIP (no space before zip)
_US_3COMMA = re.compile(
    rf",\s*([^,\n]+?)\s*,\s*({_ST})\s*,\s*({_ZIP})\b",
    re.IGNORECASE,
)
# TitleCase / ALLCAPS city + , ST ZIP (last match wins over street noise)
_US_TAIL = re.compile(
    rf"\b((?:[A-Z][A-Za-z]*)(?:\s+[A-Z][A-Za-z]*)*)\s*,\s*({_ST})\s*({_ZIP})\b",
)
# city with lowercase words: San Marcos ca 92069
_US_LOWR = re.compile(
    rf"\b([A-Za-z][a-z]+(?:\s+[a-z]+)*)\s+([a-z]{{2}})\s*({_ZIP})\b",
    re.IGNORECASE,
)
# Full state name: … , Hilton head island , South Carolina , 29926
_US_FULLSTATE = re.compile(
    rf",\s*([^,\n]+?)\s*,\s*([A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+)+)\s*,\s*({_ZIP})\b",
)
# Chinese labels
_CN_CITY = re.compile(r"城市\s*[：:]\s*([^\n\r]+?)(?:\s*(?:区域|邮编)|\n|$)")
_CN_ZIP = re.compile(r"邮编\s*[：:]\s*(\d{5}(?:-\d{4})?)")
# Pickup / ship-from lines in mixed notes (not 派送)
_PICKUP_HEAD = re.compile(
    r"(?:^|\n)\s*(?:提货地址|发货地址|提货地|发货地|Pick\s*up\s*addr(?:ess)?|PU\s*addr)\s*[：:\s]\s*",
    re.IGNORECASE | re.MULTILINE,
)
# Token before city name on same line as "… Avenue Edison, NJ"
_STREET_TYPE = frozenset(
    {
        "ave", "avenue", "st", "street", "rd", "road", "dr", "drive", "ln", "lane",
        "blvd", "boulevard", "way", "ct", "court", "pl", "place", "pkwy", "hwy",
        "loop", "cir", "circle", "trl", "trace", "rte", "route", "pike", "tpke",
    }
)


def _normalize_display(city: str, st: str, zipc: str) -> str:
    c = (city or "").strip().strip(",")
    z = (zipc or "").strip()
    s = (st or "").strip().upper()
    if not c:
        return ""
    if s and len(s) == 2 and z:
        return f"{c}, {s} {z}"
    if z:
        return f"{c} {z}"
    return c


def _one_comma_address_line(line: str) -> str:
    """
    'Street… City, ST ZIP' 或 'Street…City,ST ZIP'（仅一个逗号在州前）→ 取末尾 City + ST + ZIP。
    避免把整段 'Executive Avenue Edison,NJ' 当成 city。
    """
    line = line.strip()
    if not line or "," not in line:
        return ""
    parts = [p.strip() for p in line.split(",") if p.strip()]
    if len(parts) < 2:
        return ""
    last = parts[-1]
    m = re.match(rf"^({_ST})\s*({_ZIP})\s*$", last, re.IGNORECASE)
    if not m:
        return ""
    st, zp = m.group(1).upper(), m.group(2)
    left = ", ".join(parts[:-1]).strip()
    one_word = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*$", left)
    if one_word:
        return _normalize_display(one_word.group(1), st, zp)
    toks = [x.rstrip(".,;") for x in left.split()]
    while toks and toks[-1].isdigit():
        toks.pop()
    if not toks:
        return _normalize_display(left, st, zp)
    if len(toks) >= 2 and toks[-2].lower() in _STREET_TYPE:
        return _normalize_display(toks[-1], st, zp)
    if (
        len(toks) >= 2
        and re.match(r"^[A-Z][a-z]+$", toks[-2])
        and re.match(r"^[A-Z][a-z]+$", toks[-1])
        and toks[-2].lower() not in _STREET_TYPE
    ):
        return _normalize_display(f"{toks[-2]} {toks[-1]}", st, zp)
    if re.match(r"^[A-Z][a-z]+$", toks[-1]):
        return _normalize_display(toks[-1], st, zp)
    return _normalize_display(left, st, zp)


def _best_us_match(text: str) -> str:
    """Prefer structured matches; return 'City, ST ZIP' or ''."""
    if not text or not text.strip():
        return ""

    t = text.replace("\r", "\n").strip()

    for line in reversed(t.split("\n")):
        oc = _one_comma_address_line(line)
        if oc:
            return oc

    m3 = list(_US_3COMMA.finditer(t))
    if m3:
        g = m3[-1]
        return _normalize_display(g.group(1), g.group(2), g.group(3))

    m2 = list(_US_2COMMA.finditer(t))
    if m2:
        g = m2[-1]
        return _normalize_display(g.group(1), g.group(2), g.group(3))

    mf = list(_US_FULLSTATE.finditer(t))
    if mf:
        g = mf[-1]
        c, st_name, z = g.group(1).strip(), g.group(2).strip(), g.group(3).strip()
        return f"{c}, {st_name} {z}"

    mt = list(_US_TAIL.finditer(t))
    if mt:
        g = mt[-1]
        return _normalize_display(g.group(1), g.group(2), g.group(3))

    ml = list(_US_LOWR.finditer(t))
    if ml:
        g = ml[-1]
        return _normalize_display(g.group(1), g.group(2).upper(), g.group(3))

    return ""


def _cn_city_zip(t: str) -> str:
    t = t.replace("\r", "\n")
    mc = _CN_CITY.search(t)
    mz = _CN_ZIP.search(t)
    mr = re.search(r"区域\s*[：:]\s*([A-Za-z]{2})\b", t)
    city = mc.group(1).strip() if mc else ""
    z = mz.group(1).strip() if mz else ""
    st = mr.group(1).upper() if mr else ""
    if city and z and st and len(st) == 2:
        return f"{city}, {st} {z}"
    if city and z:
        return f"{city}, {z}"
    if city:
        return city
    if z:
        return z
    return ""


def _multiline_city_st_zip(t: str) -> str:
    """e.g. 'TAMPA, FL\\n33624' or 'Florence NJ\\n08554'."""
    lines = [ln.strip() for ln in t.replace("\r", "\n").split("\n") if ln.strip()]
    for i in range(len(lines) - 1):
        a, b = lines[i], lines[i + 1]
        if re.match(rf"^{_ZIP}$", b):
            m = re.match(rf"^(.+?)\s+({_ST})\s*$", a, re.IGNORECASE)
            if m:
                return _normalize_display(m.group(1).strip(), m.group(2), b)
            if re.search(rf"{_ST}\s*$", a, re.IGNORECASE):
                m2 = re.match(rf"^(.+?)\s+({_ST})\s*$", a, re.IGNORECASE)
                if m2:
                    return _normalize_display(m2.group(1).strip(), m2.group(2), b)
        mzip = re.match(rf"^({_ST})\s+({_ZIP})$", b, re.IGNORECASE)
        if mzip and "," in a:
            parts = [p.strip() for p in a.rsplit(",", 1)]
            if len(parts) == 2:
                return _normalize_display(parts[0], parts[1][:2] if len(parts[1]) >= 2 else "", mzip.group(2))
    return ""


def _extract_pickup_blob(contact: str) -> str:
    """First labeled 提货/发货 block (avoid 派送)."""
    if not contact.strip():
        return ""
    m = _PICKUP_HEAD.search(contact)
    if not m:
        return ""
    rest = contact[m.end() :]
    stop = re.search(
        r"(?i)\n\s*(?:派送|收件|目的地|公司名|联系人|联系[:：]|收件人)",
        rest,
    )
    chunk = rest[: stop.start()] if stop else rest
    return chunk.strip()


def _has_address_signal(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    if re.search(rf"\b{_ZIP}\b", s):
        return True
    if re.search(rf",\s*{_ST}\s*,?\s*{_ZIP}\b", s, re.IGNORECASE):
        return True
    if re.search(r"(?:提货地址|发货地址|发货地|城市|邮编|Address:)", s, re.IGNORECASE):
        return True
    return False


def extract_location_display_line(text: str) -> str:
    """
    From one blob of text, best-effort **City, ST ZIP** (or 中文城市+邮编).
    """
    if not text or not str(text).strip():
        return ""

    t = str(text).replace("\r", "\n").strip()

    cn = _cn_city_zip(t)
    if cn:
        return cn

    mm = _multiline_city_st_zip(t)
    if mm:
        return mm

    us = _best_us_match(t)
    if us:
        return us

    # loose zip append: last ST ZIP in string with preceding fragment
    lz = None
    for m in re.finditer(rf"\b({_ST})\s*({_ZIP})\b", t, re.IGNORECASE):
        lz = m
    if lz:
        before = t[: lz.start()].rstrip()
        if "," in before:
            tail = before.split(",")[-1].strip()
            if 1 < len(tail) < 80:
                return _normalize_display(tail, lz.group(1), lz.group(2))

    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    return lines[-1] if lines else t


def format_ship_from_for_display(raw: str) -> str:
    """
    仅对 **单字段** `ship_from` 做展示规范化（系统级起始地字段）。
    若货描无地址，请用 `resolve_origin_for_order`。
    """
    t = (raw or "").strip()
    if not t:
        return ""
    d = extract_location_display_line(t)
    return d if d.strip() else t


def resolve_origin_for_order(row: dict[str, Any]) -> tuple[str, str]:
    """
    订单行 → (卡片展示用一行, 地图搜索/路线用原文)。

    优先 `ship_from` 中已含邮编/地址时用它；否则用 `consignee_contact` 里「提货/发货」段（常为真实提货地）。
    """
    ship = str(row.get("ship_from") or "").strip()
    contact = str(row.get("consignee_contact") or "").strip()
    pickup = _extract_pickup_blob(contact)

    def _zip_in(s: str) -> bool:
        return bool(re.search(rf"\b{_ZIP}\b", s))

    if ship:
        ds = extract_location_display_line(ship)
        if _zip_in(ds) or (_zip_in(ship) and _has_address_signal(ship)):
            return ds, ship

    if pickup:
        dp = extract_location_display_line(pickup)
        if _zip_in(dp) or re.search(rf",\s*{_ST}\s+\d", dp):
            return dp, pickup

    if ship:
        ds = extract_location_display_line(ship)
        return (ds if ds.strip() else ship), ship

    if pickup:
        dp = extract_location_display_line(pickup)
        return (dp if dp.strip() else pickup[:120]), pickup

    if contact:
        dc = extract_location_display_line(contact)
        return (dc if dc.strip() else contact[:120]), contact

    return "—", ""
