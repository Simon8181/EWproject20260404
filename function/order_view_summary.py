"""订单卡片折叠行：起终点摘要、公里、A 列状态、报价摘要。"""

from __future__ import annotations

import ast
import re
import operator
from typing import Any

from function.address_display import extract_location_display_line
from function.order_zip import first_us_zip, is_valid_us_zip5, strip_us_zip_plus4_from_text
from function.order_view_html import esc


def first_nonempty_str(r: dict[str, Any], *keys: str) -> str:
    """Prefer first non-empty mapped field (e.g. Sheet 列名变更后可临时加备用键)."""
    for k in keys:
        v = r.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def summary_city_st_zip(
    *,
    formatted_google: str,
    fallback_address_blob: str,
    zip_only: str,
) -> str:
    """
    折叠行展示用：优先「City, ST 邮编」；有 Google formatted 则解析；
    否则从起运/目的正文解析；最后退回仅 5 位邮编。
    """
    z = (zip_only or "").strip()
    fg = strip_us_zip_plus4_from_text((formatted_google or "").strip())
    if fg:
        line = extract_location_display_line(fg)
        if line:
            line = strip_us_zip_plus4_from_text(line).strip()
        if line and line != "—":
            return line
    fb = strip_us_zip_plus4_from_text((fallback_address_blob or "").strip())
    if fb:
        line = extract_location_display_line(fb)
        if line:
            line = strip_us_zip_plus4_from_text(line).strip()
        if line and line != "—":
            return line
    return z if z else "—"


def summary_prefer_db_city_state_zip(
    r: dict[str, Any],
    *,
    city_key: str,
    state_key: str,
    formatted_google: str,
    fallback_address_blob: str,
    zip_only: str,
) -> str:
    """折叠行：若库中已有 Geocoding 写入的 city/state + 合法 5 位邮编，优先展示。"""
    c = str(r.get(city_key) or "").strip()
    st = str(r.get(state_key) or "").strip()
    z = (zip_only or "").strip()
    if c and st and is_valid_us_zip5(z):
        return f"{c}, {st} {z}"
    return summary_city_st_zip(
        formatted_google=formatted_google,
        fallback_address_blob=fallback_address_blob,
        zip_only=zip_only,
    )


def a_cell_badge_html(a_cell: str) -> str:
    """A 列填色：待找车 | 已经安排 | 其它视为未安排。"""
    ac = (a_cell or "").strip()
    if ac == "待找车":
        return '<span class="oc-a oc-a--wait" title="A 列填充色为红">待找车</span>'
    if ac == "已经安排":
        return '<span class="oc-a oc-a--ok" title="A 列填充色为绿">已经安排</span>'
    return '<span class="oc-a oc-a--open" title="A 列非红非绿或未填色">未安排</span>'


def summary_fold_quote_snippet(raw: str, *, max_len: int = 48) -> str:
    """折叠行单行展示：折叠空白，过长省略。"""
    t = " ".join((raw or "").split())
    if not t:
        return "—"
    if len(t) > max_len:
        t = t[: max_len - 1] + "…"
    return esc(t)


def _looks_like_year(v: float) -> bool:
    try:
        iv = int(abs(v))
    except (TypeError, ValueError):
        return False
    return len(str(iv)) == 4 and 1900 <= iv <= 2099


def _parse_fold_price_fallback_number(text: str) -> float | None:
    """算式失败时取格内数字；多个时取 max（略 1900–2099 年份）。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    compact = raw.replace(",", "").replace("$", " ")
    vals: list[float] = []
    for s in re.findall(r"[-+]?\d+(?:\.\d+)?", compact):
        try:
            v = float(s)
        except ValueError:
            continue
        if abs(v) <= 1e12:
            vals.append(v)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    non_year = [v for v in vals if not _looks_like_year(v)]
    return max(non_year if non_year else vals)


_FOLD_FORMULA_TRANS = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "＋": "+",
        "－": "-",
        "×": "*",
        "÷": "/",
        "＝": "=",
    }
)


def _normalize_fold_formula_chars(s: str) -> str:
    """全角括号、运算符 → ASCII；Unicode 减号/破折号 → hyphen，便于 ast 解析。"""
    t = s.translate(_FOLD_FORMULA_TRANS)
    for u in ("\u2212", "\u2013", "\u2014"):
        t = t.replace(u, "-")
    return t


_RE_NON_ARITH_PRINTABLE = re.compile(r"[^0-9.,+\-*/()$\s]")

# ``300 53ft``：金额 300 + 叫 53 英尺车，去掉 `` 53ft`` 避免与金额混算。
_TRUCK_LEN_FT = re.compile(r"\s+\d+\s*ft\b", re.IGNORECASE)


def _strip_truck_ft_length_note(s: str) -> str:
    """去掉 `` 53ft`` / `` 48 ft`` 等车长备注（紧跟在金额后的英制车长）。"""
    return _TRUCK_LEN_FT.sub("", s)


def _take_last_equals_suffix(s: str) -> str:
    """含 ``=`` 时只取最后一个等号右侧（``650+200=850`` → ``850``；先全角 ``＝`` 已归一）。"""
    if "=" not in s:
        return s
    return s.rsplit("=", 1)[-1].strip()


def _strip_text_for_price_formula(s: str) -> str:
    """
    先去掉字母与文字（`isalpha()`，含中文），再去掉非算式字符（冒号、备注符号等），
    只保留数字与 ``+ - * / ( ) , . $`` 及空白。
    """
    t = "".join(ch for ch in s if not ch.isalpha())
    t = _RE_NON_ARITH_PRINTABLE.sub("", t)
    return t.strip()


_TWO_NUM_RANGE = re.compile(
    r"^([-+]?\d+(?:\.\d+)?)\s*-\s*([-+]?\d+(?:\.\d+)?)$"
)


def _preprocess_price_cell(text: str) -> str | None:
    """与 `parse_fold_price_*` 共用：归一、车长 ft、等号、去文字。"""
    raw = str(text or "").strip()
    if not raw:
        return None
    raw = _normalize_fold_formula_chars(raw)
    raw = _strip_truck_ft_length_note(raw)
    raw = _take_last_equals_suffix(raw)
    raw = _strip_text_for_price_formula(raw)
    return raw if raw else None


def _safe_eval_price_ast(node: ast.AST) -> float:
    """仅允许 + − × ÷、括号、一元正负；结果为 float。"""
    if isinstance(node, ast.Expression):
        return _safe_eval_price_ast(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise ValueError
        if isinstance(node.value, (int, float)):
            v = float(node.value)
            if abs(v) > 1e12:
                raise ValueError
            return v
        raise ValueError
    if isinstance(node, ast.Num):  # Python < 3.8
        v = float(node.n)
        if abs(v) > 1e12:
            raise ValueError
        return v
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _safe_eval_price_ast(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
    ):
        left = _safe_eval_price_ast(node.left)
        right = _safe_eval_price_ast(node.right)
        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }
        fn = ops.get(type(node.op))
        if fn is None:
            raise ValueError
        if isinstance(node.op, ast.Div) and right == 0:
            raise ZeroDivisionError
        return float(fn(left, right))
    raise ValueError


def _try_parse_two_num_range(t: str) -> tuple[float, float] | None:
    """整串为 ``a - b`` 且 a≤b 时为区间，否则 None。"""
    if "=" in t:
        return None
    m = _TWO_NUM_RANGE.fullmatch(t.replace(",", "").replace("$", "").strip())
    if not m:
        return None
    try:
        a, b = float(m.group(1)), float(m.group(2))
    except ValueError:
        return None
    return (a, b) if a <= b else None


def parse_fold_price_scalar_or_range(
    text: str,
) -> float | tuple[float, float] | None:
    """标量或左≤右区间 ``(770,800)``；等号/车长/去文字后 ast，失败则回退。"""
    raw = _preprocess_price_cell(text)
    if not raw:
        return None
    r = _try_parse_two_num_range(raw)
    if r is not None:
        return r
    normalized = re.sub(r"\s+", " ", raw.replace(",", "").replace("$", " ")).strip()
    if not normalized:
        return None
    try:
        tree = ast.parse(normalized, mode="eval")
        v = _safe_eval_price_ast(tree)
        if abs(v) > 1e12:
            return None
        return v
    except ZeroDivisionError:
        return None
    except (SyntaxError, ValueError, TypeError):
        return _parse_fold_price_fallback_number(raw)


def parse_fold_price_expression(text: str) -> float | None:
    """
    报价单元格数值：区间 ``770-800`` 时取**中点**（785）；其余同 `parse_fold_price_scalar_or_range`。
    """
    v = parse_fold_price_scalar_or_range(text)
    if v is None:
        return None
    if isinstance(v, tuple):
        return (v[0] + v[1]) / 2.0
    return v


def _margin_dollar_body_unsigned(amt: float) -> str:
    a = abs(amt)
    if a >= 1000:
        return f"{a:,.0f}"
    if a >= 100:
        return f"{a:.1f}".rstrip("0").rstrip(".")
    return f"{a:.2f}".rstrip("0").rstrip(".")


def format_fold_margin_amount(diff: float) -> str:
    """差价：+$1,200 或 −$500（Unicode 减号）。"""
    sign = "+" if diff >= 0 else "−"
    return f"{sign}${_margin_dollar_body_unsigned(diff)}"


def format_fold_margin_range(lo: float, hi: float) -> str:
    """差价区间，如 ``+$470–$500``（两端均为正时）。"""
    if abs(lo - hi) < 1e-9:
        return format_fold_margin_amount(lo)
    a, b = (lo, hi) if lo <= hi else (hi, lo)
    if a >= 0 and b >= 0:
        return f"+${_margin_dollar_body_unsigned(a)}–${_margin_dollar_body_unsigned(b)}"
    return f"{format_fold_margin_amount(lo)}–{format_fold_margin_amount(hi)}"


def _margin_diff_minus(
    a: float | tuple[float, float],
    b: float | tuple[float, float],
) -> float | tuple[float, float] | None:
    """标量/区间差：待找车 P−U、已安排 U−W 同一套规则。"""
    if isinstance(a, tuple) and isinstance(b, float):
        return (a[0] - b, a[1] - b)
    if isinstance(a, float) and isinstance(b, tuple):
        return (a - b[1], a - b[0])
    if isinstance(a, float) and isinstance(b, float):
        return a - b
    if isinstance(a, tuple) and isinstance(b, tuple):
        return (a[0] - b[1], a[1] - b[0])
    return None


def _format_fold_margin_inner_and_class(
    diff: float | tuple[float, float],
) -> tuple[str, str]:
    if isinstance(diff, float):
        inner = format_fold_margin_amount(diff)
        cls = "oc-sum-margin-val"
        if diff < 0:
            cls += " oc-sum-margin-val--neg"
        elif diff > 0:
            cls += " oc-sum-margin-val--pos"
        return inner, cls
    lo, hi = diff
    if lo > hi:
        lo, hi = hi, lo
    inner = format_fold_margin_range(lo, hi)
    cls = "oc-sum-margin-val"
    if lo >= 0:
        cls += " oc-sum-margin-val--pos"
    elif hi <= 0:
        cls += " oc-sum-margin-val--neg"
    else:
        cls += " oc-sum-margin-val--range-mixed"
    return inner, cls


def summary_fold_margin_block(
    *,
    a_cell: str,
    quote_customer: str,
    quote_driver: str,
    booking_rate: str,
) -> str:
    """
    折叠行右下角：待找车 = 客户报价(P) − 司机价(U)；
    已经安排（已接单）= 司机价(U) − 接单 Rate(W)。
    P/U/W 支持单元格内加减乘除与括号（安全解析，非 eval）。
    客户报价为 ``770-800`` 区间、司机价为标量时，差价为区间（如 ``+$470–$500``）。
    """
    ac = (a_cell or "").strip()
    p = parse_fold_price_scalar_or_range(quote_customer)
    u = parse_fold_price_scalar_or_range(quote_driver)
    w = parse_fold_price_scalar_or_range(booking_rate)

    title: str
    diff: float | tuple[float, float] | None = None

    if ac == "待找车":
        title = "差价 = 客户报价(P) − 司机价(U)；区间时显示 P−U 的上下界"
        if p is not None and u is not None:
            diff = _margin_diff_minus(p, u)
    elif ac == "已经安排":
        title = "差价 = 司机价(U) − 接单 Rate(W)；区间时显示上下界"
        if u is not None and w is not None:
            diff = _margin_diff_minus(u, w)
    else:
        return ""

    if diff is None:
        inner = "—"
        cls = "oc-sum-margin-val oc-sum-margin-val--empty"
    else:
        inner, cls = _format_fold_margin_inner_and_class(diff)

    return (
        f'<div class="oc-sum-margin-line" title="{esc(title)}">'
        f'<span class="oc-sum-margin-ql">差价</span>'
        f'<span class="{cls}">{esc(inner)}</span>'
        f"</div>"
    )


def summary_total_km_from_miles(miles_val: Any) -> str:
    """由 `google_distance_miles`（英里）换算公里；无则 —。"""
    if miles_val is None:
        return "—"
    s = str(miles_val).strip()
    if not s:
        return "—"
    try:
        mi = float(s)
    except (TypeError, ValueError):
        return "—"
    if mi < 0 or mi > 1e7:
        return "—"
    km = mi * 1.609344
    if km >= 100:
        return f"{km:,.0f} 公里"
    if km >= 10:
        v = f"{km:.1f}".rstrip("0").rstrip(".")
        return f"{v} 公里"
    v = f"{km:.2f}".rstrip("0").rstrip(".")
    return f"{v} 公里"


def summary_fold_distance_mi_display(miles_val: Any) -> str:
    """折叠行「总里程」：与详情区 Google 驾车一致，单位 mi（英里）；无则 —。"""
    if miles_val is None:
        return "—"
    s = str(miles_val).strip()
    if not s:
        return "—"
    try:
        mi = float(s)
    except (TypeError, ValueError):
        return "—"
    if mi < 0 or mi > 1e7:
        return "—"
    if mi >= 100:
        return f"{mi:,.0f} mi"
    return f"{mi:.1f} mi"


def miles_float_for_summary_km(r: dict[str, Any]) -> float | None:
    """优先数值英里列，否则从 `google_distance_text` 解析 `… mi`。"""
    v = r.get("google_distance_miles")
    if v is not None and str(v).strip() != "":
        try:
            mi = float(v)
            if 0 <= mi <= 1e7:
                return mi
        except (TypeError, ValueError):
            pass
    t = str(r.get("google_distance_text") or "").strip()
    if not t:
        return None
    m = re.search(r"([\d,.]+)\s*(?:mi\b|miles?\b)", t, re.IGNORECASE)
    if not m:
        return None
    try:
        mi = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    if 0 <= mi <= 1e7:
        return mi
    return None
