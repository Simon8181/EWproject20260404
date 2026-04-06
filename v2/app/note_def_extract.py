from __future__ import annotations

import re

# Parse Sheet columns D/E/F (note_d/e/f_raw) into broker, actual_driver_rate_raw, carriers.
# Carriers holds MC#/DOT# or 3PL reference text when applicable.


def _strip(s: str) -> str:
    return ("" if s is None else str(s)).strip()


def _looks_like_rate(s: str) -> bool:
    t = s.strip()
    if not t:
        return False
    if any(c in t for c in ("$", "￥", "¥", "€")):
        return True
    if re.search(r"\bUSD\b", t, re.I):
        return True
    t2 = t.replace(",", "").replace(" ", "")
    if re.fullmatch(r"\d{1,9}(?:\.\d{1,2})?", t2):
        return True
    return False


def _is_mc_or_carrier_ref(s: str) -> bool:
    t = s.strip()
    if not t:
        return False
    if re.search(r"(?:^|\s)(?:MC|DOT)\s*[：:\s#.]*\d+", t, re.I):
        return True
    if re.search(r"(?:3PL|三方)", t, re.I):
        return True
    if re.fullmatch(r"\d{6,10}", t.strip()):
        return True
    if re.fullmatch(r"[A-Z]{2,}\d{4,12}|\d{6,}-[A-Z0-9]+", t, re.I):
        return True
    return False


def _normalize_mc_value(s: str) -> str:
    t = s.strip()
    m = re.search(r"(?:MC|DOT)\s*[：:\s#.]*(\d{3,8})\b", t, re.I)
    if m:
        return m.group(1).strip()
    m = re.fullmatch(r"(\d{4,8})", t)
    if m:
        return m.group(1).strip()
    t2 = re.sub(r"^\s*(?:3PL|三方(?:物流)?)\s*(?:单号)?\s*[:：]?\s*", "", t, flags=re.I)
    if t2 != t:
        return t2.strip()
    return t.strip()


def _label_extract(combined: str) -> tuple[str, str, str]:
    broker, rate, carriers = "", "", ""
    # Broker
    m = re.search(
        r"(?m)^\s*(?:Broker|经纪|BROKER)\s*[:：]\s*(.+?)\s*$",
        combined,
    )
    if m:
        broker = m.group(1).strip()
    # Rate / 给司机
    for pat in (
        r"(?m)^\s*(?:Rate|费率|价格|司机价|给司机)\s*[:：]\s*(.+?)\s*$",
        r"(?m)^\s*实际(?:给)?司机(?:价格)?\s*[:：]\s*(.+?)\s*$",
    ):
        m = re.search(pat, combined)
        if m:
            rate = m.group(1).strip()
            break
    # MC / DOT
    m = re.search(
        r"(?m)^\s*(?:MC|DOT)\s*[：:\s#.]*(\d{3,8})\s*$",
        combined,
        re.I,
    )
    if m:
        carriers = m.group(1).strip()
    # 3PL 单号
    if not carriers:
        m = re.search(
            r"(?m)^\s*(?:3PL|三方(?:物流)?)\s*(?:单号|#)?\s*[:：]?\s*(.+?)\s*$",
            combined,
        )
        if m:
            carriers = _normalize_mc_value(m.group(1))
    return broker, rate, carriers


def _fallback_three_cells(d: str, e: str, f: str) -> tuple[str, str, str]:
    cells = [_strip(d), _strip(e), _strip(f)]
    if not all(cells):
        return "", "", ""
    rate_i = next((i for i, c in enumerate(cells) if _looks_like_rate(c)), None)
    car_i = next((i for i, c in enumerate(cells) if _is_mc_or_carrier_ref(c)), None)
    if rate_i is None and car_i is None:
        return "", "", ""
    used: set[int] = set()
    for i in (rate_i, car_i):
        if i is not None:
            used.add(i)
    broker_i = next((i for i in range(3) if i not in used), None)
    broker = cells[broker_i] if broker_i is not None else ""
    rate = cells[rate_i] if rate_i is not None else ""
    car_raw = cells[car_i] if car_i is not None else ""
    carriers = _normalize_mc_value(car_raw) if car_raw else ""
    return broker.strip(), rate.strip(), carriers.strip()


def parse_def_notes(note_d_raw: str, note_e_raw: str, note_f_raw: str) -> dict[str, str]:
    d, e, f = _strip(note_d_raw), _strip(note_e_raw), _strip(note_f_raw)
    combined = "\n".join(x for x in (d, e, f) if x)
    broker, rate, carriers = "", "", ""
    if combined:
        broker, rate, carriers = _label_extract(combined)
    if d and e and f and (not broker or not rate or not carriers):
        bb, rr, cc = _fallback_three_cells(d, e, f)
        if not broker:
            broker = bb
        if not rate:
            rate = rr
        if not carriers:
            carriers = cc
    return {
        "broker": broker,
        "actual_driver_rate_raw": rate,
        "carriers": carriers,
    }
