from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import certifi

from .party_extract import extract_consignee_info, extract_shipper_info

_GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


@dataclass(frozen=True)
class AiPartyResult:
    ok: bool
    shipper_info: str
    consignee_info: str
    confidence: float
    notes: str
    error_message: str | None = None


def party_ai_enabled() -> bool:
    v = (
        os.environ.get("AI_PARTY_EXTRACT_ENABLED")
        or os.environ.get("V2_AI_PARTY_EXTRACT_ENABLED")
        or "1"
    ).strip().lower()
    return v in ("1", "true", "yes", "on")


def gemini_api_key() -> str | None:
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    return key or None


def party_gemini_model() -> str:
    return (
        os.environ.get("AI_PARTY_EXTRACT_MODEL")
        or os.environ.get("V2_AI_PARTY_EXTRACT_MODEL")
        or os.environ.get("AI_ADDRESS_MODEL")
        or os.environ.get("V2_AI_ADDRESS_MODEL")
        or "gemini-2.0-flash"
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


def _format_party_line(name: str, phone: str, company: str) -> str:
    parts = [(p or "").strip() for p in (name, phone, company) if (p or "").strip()]
    return " | ".join(parts)


def _parsed_obj_to_result(obj: dict) -> AiPartyResult:
    shipper = _format_party_line(
        str(obj.get("shipper_name") or ""),
        str(obj.get("shipper_phone") or ""),
        str(obj.get("shipper_company") or ""),
    )
    consignee = _format_party_line(
        str(obj.get("consignee_name") or ""),
        str(obj.get("consignee_phone") or ""),
        str(obj.get("consignee_company") or ""),
    )
    notes = str(obj.get("notes") or "").strip()
    try:
        confidence = float(obj.get("confidence") or 0.0)
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    if not shipper and not consignee:
        return AiPartyResult(
            ok=False,
            shipper_info="",
            consignee_info="",
            confidence=confidence,
            notes=notes,
            error_message="AI_EMPTY_PARTIES",
        )
    return AiPartyResult(
        ok=True,
        shipper_info=shipper,
        consignee_info=consignee,
        confidence=confidence,
        notes=notes,
        error_message=None,
    )


def extract_parties_with_gemini(
    ship_from_raw: str,
    ship_to_raw: str,
    ship_from_out: str,
    ship_to_out: str,
    consignee_contact: str,
) -> AiPartyResult:
    if not party_ai_enabled():
        return AiPartyResult(
            ok=False,
            shipper_info="",
            consignee_info="",
            confidence=0.0,
            notes="",
            error_message="PARTY_AI_DISABLED",
        )
    key = gemini_api_key()
    if not key:
        return AiPartyResult(
            ok=False,
            shipper_info="",
            consignee_info="",
            confidence=0.0,
            notes="",
            error_message="MISSING_GEMINI_API_KEY",
        )
    model = party_gemini_model()
    prompt = (
        "Extract shipper and consignee / pickup party contact details for US freight.\n"
        "Input includes spreadsheet free text (may mix Chinese/English labels) and validated "
        "address lines for context only — do not put full street addresses into name fields.\n"
        "Return JSON only with keys exactly:\n"
        "shipper_name, shipper_phone, shipper_company,\n"
        "consignee_name, consignee_phone, consignee_company,\n"
        "confidence, notes.\n"
        "confidence must be between 0 and 1. notes is a short optional string.\n"
        "Use empty string for unknown fields. shipper = shipping party at origin; "
        "consignee = receiving or pickup contact at destination.\n\n"
        f"ship_from_raw:\n{ship_from_raw}\n\n"
        f"ship_to_raw:\n{ship_to_raw}\n\n"
        f"consignee_contact_cell:\n{consignee_contact}\n\n"
        f"ship_from_normalized:\n{ship_from_out}\n\n"
        f"ship_to_normalized:\n{ship_to_out}\n"
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
        return AiPartyResult(
            ok=False,
            shipper_info="",
            consignee_info="",
            confidence=0.0,
            notes="",
            error_message=raw,
        )
    candidates = raw.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return AiPartyResult(False, "", "", 0.0, "", "PARTY_AI_EMPTY")
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    if not isinstance(parts, list) or not parts:
        return AiPartyResult(False, "", "", 0.0, "", "PARTY_AI_EMPTY_TEXT")
    text = str((parts[0] or {}).get("text") or "").strip()
    if not text:
        return AiPartyResult(False, "", "", 0.0, "", "PARTY_AI_EMPTY_TEXT")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return AiPartyResult(False, "", "", 0.0, "", "PARTY_AI_BAD_JSON")
    if not isinstance(obj, dict):
        return AiPartyResult(False, "", "", 0.0, "", "PARTY_AI_BAD_JSON")
    return _parsed_obj_to_result(obj)


def resolve_party_info(
    *,
    ship_from_raw: str,
    ship_to_raw: str,
    ship_from_out: str,
    ship_to_out: str,
    consignee_contact: str,
) -> tuple[str, str]:
    ai = extract_parties_with_gemini(
        ship_from_raw,
        ship_to_raw,
        ship_from_out,
        ship_to_out,
        consignee_contact,
    )
    if not ai.ok:
        return (
            extract_shipper_info(ship_from_out),
            extract_consignee_info(ship_to_out, consignee_contact),
        )
    shipper = (ai.shipper_info or "").strip() or extract_shipper_info(ship_from_out)
    consignee = (ai.consignee_info or "").strip() or extract_consignee_info(
        ship_to_out, consignee_contact
    )
    return shipper, consignee
