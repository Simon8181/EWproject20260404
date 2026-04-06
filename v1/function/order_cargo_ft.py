"""
货物密度（PCF，lb/ft³）：由 L 重量 + M 尺寸 / N 体积（m³）在「格式化数据」时计算。

优先使用 N 列 `volume_m3` 换算立方英尺；若无，则从 M 列 `dimensions_class` 解析 L×W×H
（默认英寸，可带 in/cm/m/mm 后缀；无单位时若单边 > 200 按厘米理解）。

NMFC 货运等级（Freight Class）：在得到 PCF 后按**密度区间**映射到常用 50–500 等级。
区间依据业界公开的 NMFC 密度分类表；正式开单请以 NMFTA / 承运人规则为准，表会随规则更新。
"""

from __future__ import annotations

import re
from typing import Any, Match

# 1 m³ = 35.31466672148859 ft³
_M3_TO_FT3: float = 35.31466672148859
_IN3_PER_FT3: float = 1728.0

_FLOAT_ANY = re.compile(r"([-+]?[\d,]+(?:\.\d+)?)")

# 密度（lb/ft³）下界 → NMFC 等级；自高向低匹配，首条命中即采用；小于 1 PCF → 500。
# （与常见 LTL 密度对照表一致；含 77.5、92.5 等半级。）
_NMFC_MIN_PCF_TO_CLASS: tuple[tuple[float, float], ...] = (
    (50.0, 50),
    (35.0, 55),
    (30.0, 60),
    (22.5, 65),
    (15.0, 70),
    (13.5, 77.5),
    (12.0, 85),
    (10.5, 92.5),
    (9.0, 100),
    (8.0, 110),
    (7.0, 125),
    (6.0, 150),
    (5.0, 175),
    (4.0, 200),
    (3.0, 250),
    (2.0, 300),
    (1.0, 400),
)


def freight_class_nmfc_from_pcf(pcf: float) -> float | None:
    """
    由密度（lb/ft³）得到 NMFC 常用等级（50、55、…、77.5、…、500）。
    实际等级还受 NMFC 品名条款、可堆性等影响，此处仅为密度法估算。
    """
    if pcf is None or pcf <= 0:
        return None
    for min_pcf, cls in _NMFC_MIN_PCF_TO_CLASS:
        if pcf >= min_pcf:
            return cls
    return 500.0


_DIM3 = re.compile(
    r"(\d+(?:\.\d+)?)\s*[x×*X]\s*(\d+(?:\.\d+)?)\s*[x×*X]\s*(\d+(?:\.\d+)?)\s*(in|inch|inches|\"|'|cm|mm|m|meter|metres)?",
    re.IGNORECASE,
)
# 48-40-60 / 48 – 40 – 40（连字符）
_DIM3_DASH = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*(in|inch|inches|\"|cm|mm|m|meter|metres)?",
    re.IGNORECASE,
)


def _parse_first_float(s: str) -> float | None:
    m = _FLOAT_ANY.search((s or "").replace(",", ""))
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    return v


def parse_weight_lbs(text: str) -> float | None:
    """取 L 列重量数字（取首个合理正数）；若明显为 kg 则换算为 lb。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    low = raw.lower()
    # 去掉常见前缀噪音
    raw_clean = re.sub(
        r"(?i)^\s*(weight|lbs?|lb\.|毛重|净重|重量)\s*[:：]?\s*",
        "",
        raw,
    )
    v = _parse_first_float(raw_clean)
    if v is None:
        return None
    if re.search(r"\bkg\b", low) and not re.search(r"\blb", low):
        v *= 2.20462262185
    if v <= 0 or v > 1e7:
        return None
    return v


def _volume_m3_str_to_ft3(s: str) -> float | None:
    """N 列体积：按 m³ 理解（忽略 ft³/cuft 等少见写法，可后续扩展）。"""
    raw = str(s or "").strip()
    if not raw:
        return None
    low = raw.lower()
    v = _parse_first_float(raw)
    if v is None:
        return None
    if re.search(r"\b(ft3|ft³|cu\.?\s*ft|cf)\b", low):
        return max(0.0, v)
    if re.search(r"\bm3\b|m³|立方米", low):
        return max(0.0, v * _M3_TO_FT3)
    # 默认按 m³（与列名 volume_m3 一致）
    return max(0.0, v * _M3_TO_FT3)


def _dim_match_to_ft3(m: Match[str]) -> float | None:
    """单个 L×W×H 匹配 → 立方英尺。"""
    try:
        a, b, c = float(m.group(1)), float(m.group(2)), float(m.group(3))
    except (TypeError, ValueError):
        return None
    unit = (m.group(4) or "").strip().lower()
    if unit in ("cm",):
        a, b, c = a / 2.54, b / 2.54, c / 2.54
    elif unit in ("mm",):
        a, b, c = a / 25.4, b / 25.4, c / 25.4
    elif unit in ("m", "meter", "metres"):
        a, b, c = a * 39.3700787, b * 39.3700787, c * 39.3700787
    elif not unit:
        if max(a, b, c) > 120.0:
            a, b, c = a / 2.54, b / 2.54, c / 2.54
    vol_in3 = a * b * c
    ft3 = vol_in3 / _IN3_PER_FT3
    if ft3 <= 0 or ft3 > 1e9:
        return None
    return ft3


def _dims_text_to_ft3(text: str) -> float | None:
    """M 列：解析第一组三边长 → 立方英尺。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    m = _DIM3.search(raw) or _DIM3_DASH.search(raw)
    if not m:
        return None
    return _dim_match_to_ft3(m)


def find_all_dims_ft3(dimensions_class: str) -> list[float]:
    """M 列中所有 L×W×H 组 → 各自立方英尺（多组视为多块托盘尺寸）。"""
    raw = str(dimensions_class or "").strip()
    if not raw:
        return []
    out: list[float] = []
    for rx in (_DIM3, _DIM3_DASH):
        for m in rx.finditer(raw):
            ft3 = _dim_match_to_ft3(m)
            if ft3 is not None and ft3 > 0:
                out.append(ft3)
    return out


def parse_ctn_pallet_count(text: str) -> int | None:
    """G 列件数/板数：取首个 1–999 的整数；无则 None。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    m = re.search(r"(\d+)", raw.replace(",", ""))
    if not m:
        return None
    n = int(m.group(1))
    if n < 1 or n > 999:
        return None
    return n


def volume_ft3_from_cargo_fields(
    *,
    dimensions_class: str,
    volume_m3: str,
) -> float | None:
    """优先 N 列 m³，其次 M 列三边。"""
    vf = _volume_m3_str_to_ft3(volume_m3)
    if vf is not None and vf > 0:
        return vf
    return _dims_text_to_ft3(dimensions_class)


def compute_cargo_density_pcf(
    *,
    weight_lbs: str,
    volume_m3: str,
    dimensions_class: str,
) -> float | None:
    """
    密度 = weight_lb / volume_ft³；无法得到正体积或正重量时返回 None。
    """
    w = parse_weight_lbs(weight_lbs)
    if w is None:
        return None
    vf = volume_ft3_from_cargo_fields(
        dimensions_class=dimensions_class,
        volume_m3=volume_m3,
    )
    if vf is None or vf <= 0:
        return None
    d = w / vf
    if d <= 0 or d > 1e7:
        return None
    return d


def cargo_metrics_payload_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """供写库：`cargo_density_pcf`、可选 `freight_class_nmfc`（密度法等级）。"""
    d = compute_cargo_density_pcf(
        weight_lbs=str(row.get("weight_lbs") or ""),
        volume_m3=str(row.get("volume_m3") or ""),
        dimensions_class=str(row.get("dimensions_class") or ""),
    )
    if d is None:
        return {}
    out: dict[str, Any] = {"cargo_density_pcf": round(d, 2)}
    fc = freight_class_nmfc_from_pcf(d)
    if fc is not None:
        out["freight_class_nmfc"] = fc
    return out


def format_freight_class_fold(value: Any) -> str:
    """NMFC 等级展示（50–500、77.5 / 92.5 等）；无则 —。"""
    if value is None or str(value).strip() == "":
        return "—"
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if x <= 0:
        return "—"
    # 与常见半级一致时保留一位小数
    if abs(x - 77.5) < 0.05 or abs(x - 92.5) < 0.05:
        return f"{x:.1f}"
    if abs(x - round(x)) < 0.01:
        return str(int(round(x)))
    return f"{x:g}"


def format_cargo_density_fold(value: Any) -> str:
    """折叠行展示：一位小数；无则 —。"""
    if value is None or str(value).strip() == "":
        return "—"
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if x <= 0:
        return "—"
    if x >= 100:
        return f"{x:.0f}"
    return f"{x:.1f}"


def _uniform_pallet_class_suffix(
    weight_lbs: float,
    volume_ft3_per_pallet: float,
    pallet_count: int,
) -> str | None:
    """板重均分、每板同体积时的 NMFC Class 文案。"""
    if pallet_count < 1 or volume_ft3_per_pallet <= 0:
        return None
    pcf = (weight_lbs / float(pallet_count)) / volume_ft3_per_pallet
    fc = freight_class_nmfc_from_pcf(pcf)
    if fc is None:
        return None
    fs = format_freight_class_fold(fc)
    if pallet_count > 1:
        return f"每板 Class {fs}（共 {pallet_count} 板，密度法）"
    return f"Class {fs}（密度法）"


def per_pallet_classes_suffix_text(row: dict[str, Any]) -> str | None:
    """
    「货物/尺寸」尺寸原文后：按 G 列板数或多组 M 尺寸展示 NMFC 密度法等级。
    """
    w = parse_weight_lbs(str(row.get("weight_lbs") or ""))
    if w is None:
        return None
    ctn = parse_ctn_pallet_count(str(row.get("ctn_total") or ""))
    vol_m3 = str(row.get("volume_m3") or "")
    dims = str(row.get("dimensions_class") or "")

    vf_n = _volume_m3_str_to_ft3(vol_m3)
    if vf_n is not None and vf_n > 0:
        np = max(1, ctn or 1)
        v_per = vf_n / float(np)
        return _uniform_pallet_class_suffix(w, v_per, np)

    dim_vols = find_all_dims_ft3(dims)
    if not dim_vols:
        return None
    if len(dim_vols) == 1:
        np = max(1, ctn or 1)
        return _uniform_pallet_class_suffix(w, dim_vols[0], np)

    k = len(dim_vols)
    wp = w / float(k)
    parts: list[str] = []
    for i, vp in enumerate(dim_vols):
        if vp <= 0:
            continue
        fc = freight_class_nmfc_from_pcf(wp / vp)
        fs = format_freight_class_fold(fc) if fc is not None else "—"
        parts.append(f"板{i + 1} Class {fs}")
    if not parts:
        return None
    return "；".join(parts) + "（密度法，重量按尺寸组均分）"
