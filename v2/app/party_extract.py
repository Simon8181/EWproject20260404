from __future__ import annotations

import re

# 电话：北美 +1 / (xxx) / 中国 11 位手机
_PHONE_RES = (
    re.compile(r"\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}"),
    re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?:\s*ext\.?\s*\d+)?", re.I),
    re.compile(r"\b1[3-9]\d{9}\b"),
)

# 发货/提货侧常见标签（中文）
_LABEL_RES = (
    re.compile(r"发货人[：:\s]*([^\n\r]+)", re.I),
    re.compile(r"发件人[：:\s]*([^\n\r]+)", re.I),
    re.compile(r"联系人[：:\s]*([^\n\r]+)", re.I),
    re.compile(r"收件人[：:\s]*([^\n\r]+)", re.I),
    re.compile(r"提货人[：:\s]*([^\n\r]+)", re.I),
    re.compile(r"公司名称[：:\s]*([^\n\r]+)", re.I),
    re.compile(r"[Ff]rom\s*[：:\s]+([^\n\r]+)", re.I),
    re.compile(r"[Cc]ontact\s*[：:\s]+([^\n\r]+)", re.I),
)


def _uniq_join(parts: list[str], *, max_items: int = 12) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        t = (p or "").strip()
        if not t or len(t) > 500:
            continue
        key = t.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= max_items:
            break
    return " | ".join(out)


def _phones(text: str) -> list[str]:
    found: list[str] = []
    for rx in _PHONE_RES:
        for m in rx.finditer(text):
            found.append(m.group(0).strip())
    return found


def _label_chunks(text: str) -> list[str]:
    out: list[str] = []
    for rx in _LABEL_RES:
        for m in rx.finditer(text):
            chunk = (m.group(1) or "").strip()
            chunk = re.sub(r"\s+", " ", chunk)
            if chunk and len(chunk) < 300:
                out.append(chunk)
    return out


def _leading_name_before_address(text: str) -> str:
    """
    e.g. 'David R,+1-6312522866, suite 10 ...' -> 'David R'
    """
    t = (text or "").strip()
    if not t or "\n" in t[:80]:
        return ""
    first_seg = t.split(",")[0].strip()
    if not first_seg or len(first_seg) > 60:
        return ""
    # Street line: "8 TAYLOR RD ...", "123 Main St"
    if re.match(r"^\d+\s+[A-Za-z0-9]", first_seg):
        return ""
    if re.search(r"\b(?:ST|AVE|RD|DR|BLVD|LN|CT|WAY)\b", first_seg, re.I):
        return ""
    if re.search(r"\d{5}", first_seg):
        return ""
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", first_seg):
        return ""
    if sum(1 for c in first_seg if c.isdigit()) > len(first_seg) // 3:
        return ""
    return first_seg


def extract_shipper_info(ship_from_raw: str) -> str:
    """从起始地原文（I 列）抽取发货侧联系人/电话等。"""
    text = (ship_from_raw or "").strip()
    if not text:
        return ""
    parts: list[str] = []
    parts.extend(_label_chunks(text))
    parts.extend(_phones(text))
    name = _leading_name_before_address(text.replace("\n", " "))
    if name and name not in parts:
        parts.insert(0, name)
    return _uniq_join(parts)


def extract_consignee_info(ship_to_raw: str, consignee_contact: str) -> str:
    """从目的地原文（K 列）与 J 列 consignee_contact 抽取收货/提货侧信息。"""
    parts: list[str] = []
    j = (consignee_contact or "").strip()
    if j:
        parts.append(j)
    text = (ship_to_raw or "").strip()
    if text:
        parts.extend(_label_chunks(text))
        parts.extend(_phones(text))
        name = _leading_name_before_address(text.replace("\n", " "))
        if name:
            parts.append(name)
    return _uniq_join(parts)
