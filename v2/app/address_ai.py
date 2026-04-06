from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import certifi

from .settings import load_env

_GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


@dataclass(frozen=True)
class AiAddressResult:
    ok: bool
    origin_normalized: str
    destination_normalized: str
    confidence: float
    notes: str
    error_message: str | None = None


def ai_enabled() -> bool:
    v = (
        os.environ.get("AI_ADDRESS_ENABLED")
        or os.environ.get("V2_AI_ADDRESS_ENABLED")
        or "1"
    ).strip().lower()
    return v in ("1", "true", "yes", "on")


def gemini_api_key() -> str | None:
    load_env()
    for name in ("GEMINI_API_KEY", "V2_GEMINI_API_KEY"):
        key = (os.environ.get(name) or "").strip()
        if key:
            return key
    return None


def gemini_model() -> str:
    return (
        os.environ.get("AI_ADDRESS_MODEL")
        or os.environ.get("V2_AI_ADDRESS_MODEL")
        or "gemini-2.5-flash"
    ).strip()


def _http_post_json(url: str, body: dict) -> dict[str, object] | str:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "EW-v2/1.0"},
        method="POST",
    )
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
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


def normalize_addresses_with_gemini(origin_raw: str, destination_raw: str) -> AiAddressResult:
    if not ai_enabled():
        return AiAddressResult(
            ok=False,
            origin_normalized="",
            destination_normalized="",
            confidence=0.0,
            notes="",
            error_message="AI_DISABLED",
        )
    key = gemini_api_key()
    if not key:
        return AiAddressResult(
            ok=False,
            origin_normalized="",
            destination_normalized="",
            confidence=0.0,
            notes="",
            error_message="MISSING_GEMINI_API_KEY",
        )
    model = gemini_model()
    prompt = (
        "Normalize two US freight addresses for Google Maps geocoding.\n"
        "Keep only useful address text, remove noise/notes.\n"
        "Return JSON only with keys: "
        "origin_normalized, destination_normalized, confidence, notes.\n"
        "confidence must be between 0 and 1.\n"
        f"origin_raw: {origin_raw}\n"
        f"destination_raw: {destination_raw}\n"
    )
    url = _GEMINI_URL_TMPL.format(
        model=urllib.parse.quote(model, safe=""),
        key=urllib.parse.quote(key, safe=""),
    )
    body = {
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        "contents": [{"parts": [{"text": prompt}]}],
    }
    raw = _http_post_json(url, body)
    if isinstance(raw, str):
        return AiAddressResult(
            ok=False,
            origin_normalized="",
            destination_normalized="",
            confidence=0.0,
            notes="",
            error_message=raw,
        )
    candidates = raw.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return AiAddressResult(False, "", "", 0.0, "", "AI_EMPTY")
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    if not isinstance(parts, list) or not parts:
        return AiAddressResult(False, "", "", 0.0, "", "AI_EMPTY_TEXT")
    text = str((parts[0] or {}).get("text") or "").strip()
    if not text:
        return AiAddressResult(False, "", "", 0.0, "", "AI_EMPTY_TEXT")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return AiAddressResult(False, "", "", 0.0, "", "AI_BAD_JSON")
    origin = str(obj.get("origin_normalized") or "").strip()
    dest = str(obj.get("destination_normalized") or "").strip()
    notes = str(obj.get("notes") or "").strip()
    try:
        confidence = float(obj.get("confidence") or 0.0)
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    if not origin or not dest:
        return AiAddressResult(False, origin, dest, confidence, notes, "AI_MISSING_FIELDS")
    return AiAddressResult(True, origin, dest, confidence, notes, None)

