from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import certifi

from .address_ai import gemini_api_key, gemini_model
from .mapping import DEFAULT_AI_IMPORT_ALLOWLIST
from .settings import load_env

_GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


def import_ai_globally_enabled() -> bool:
    load_env()
    v = (os.environ.get("AI_SHEET_IMPORT_ENABLED") or "0").strip().lower()
    return v in ("1", "true", "yes", "on")


def _http_post_json(url: str, body: dict) -> dict[str, object] | str:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "EW-v2-sheet-import-ai/1.0"},
        method="POST",
    )
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="ignore")
        except Exception:
            detail = ""
        return f"HTTP {e.code}: {e.reason} {detail}".strip()
    except OSError as e:
        return str(e)
    except json.JSONDecodeError as e:
        return str(e)


def parse_import_aggregated(
    *,
    quote_no: str,
    contexts: list[dict[str, Any]],
    rules: str,
    allowlist: frozenset[str],
    current_fields: dict[str, str],
) -> tuple[dict[str, str], str | None]:
    """Call Gemini; return (delta dict, error_message or None)."""
    if not import_ai_globally_enabled():
        return {}, "AI_SHEET_IMPORT_DISABLED"
    key = gemini_api_key()
    if not key:
        return {}, "MISSING_GEMINI_API_KEY"
    model = gemini_model()
    eff_rules = rules.strip() or (
        "无额外规则：仅根据原始格子与当前合并行，在允许字段内补缺；"
        "不得编造地址、重量或金额；不确定则不要输出该键。"
    )
    keys_hint = sorted(allowlist & DEFAULT_AI_IMPORT_ALLOWLIST)
    prompt = (
        "你是物流 Sheet 导入助手。根据规则与下列 JSON，为尚未填好的字段给出建议。\n"
        f"规则：\n{eff_rules}\n\n"
        f"quote_no: {quote_no}\n"
        "tab_row_snapshots（每行含 tab_key 与 cells，cells 为 A–U 与 _A_COLOR）：\n"
        f"{json.dumps(contexts, ensure_ascii=False)}\n\n"
        "当前已由确定性映射合并的字段（可能仍不完整）：\n"
        f"{json.dumps(current_fields, ensure_ascii=False)}\n\n"
        "只输出一个 JSON 对象；键必须属于下列集合之一，且只填写你能从快照或规则中**明确**推断的值；"
        f"键集合：{keys_hint}\n"
        "不要输出 status、quote_no、source_tabs；不要编造。\n"
    )
    url = _GEMINI_URL_TMPL.format(
        model=urllib.parse.quote(model, safe=""),
        key=urllib.parse.quote(key, safe=""),
    )
    body = {
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        "contents": [{"parts": [{"text": prompt}]}],
    }
    raw = _http_post_json(url, body)
    if isinstance(raw, str):
        return {}, raw
    candidates = raw.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return {}, "AI_EMPTY"
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    if not isinstance(parts, list) or not parts:
        return {}, "AI_EMPTY_TEXT"
    text = str((parts[0] or {}).get("text") or "").strip()
    if not text:
        return {}, "AI_EMPTY_TEXT"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return {}, "AI_BAD_JSON"
    if not isinstance(obj, dict):
        return {}, "AI_BAD_JSON"
    out: dict[str, str] = {}
    for k, v in obj.items():
        sk = str(k).strip()
        if sk not in allowlist or sk not in DEFAULT_AI_IMPORT_ALLOWLIST:
            continue
        sv = "" if v is None else str(v).strip()
        if sv:
            out[sk] = sv
    return out, None
