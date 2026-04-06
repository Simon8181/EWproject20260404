from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import certifi

from .address_ai import normalize_addresses_with_gemini
from .settings import load_env

_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_DISTANCE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

_WAREHOUSE_HINTS = {"storage", "moving_company"}
_COMMERCIAL_HINTS = {
    "establishment",
    "point_of_interest",
    "store",
    "shopping_mall",
    "restaurant",
    "bank",
    "gas_station",
    "office",
    "hospital",
    "school",
    "airport",
    "parking",
}


@dataclass(frozen=True)
class RouteValidation:
    ok: bool
    distance_miles: float | None
    origin_land_use: str
    dest_land_use: str
    used_ai_retry: bool = False
    ai_confidence: float | None = None
    origin_normalized: str = ""
    dest_normalized: str = ""
    ai_notes: str = ""
    # Geocode formatted_address; maps_origin_formatted is written to load.ship_from_raw on success.
    maps_origin_formatted: str = ""
    maps_dest_formatted: str = ""
    error_message: str | None = None


def maps_api_key() -> str | None:
    key = (os.environ.get("GOOGLE_MAPS_API_KEY") or "").strip()
    if key:
        return key
    # Backward compatibility: old prefixed env name.
    key = (os.environ.get("V2_GOOGLE_MAPS_API_KEY") or "").strip()
    return key or None


def _http_get_json(url: str, timeout: float = 15.0) -> dict[str, object] | str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EW-v2/1.0"})
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.reason}"
    except OSError as e:
        return str(e)
    except json.JSONDecodeError as e:
        return str(e)


def _classify_land_use(types: tuple[str, ...]) -> str:
    s = {t.strip().lower() for t in types if t and str(t).strip()}
    if not s:
        return "unknown"
    if s & _WAREHOUSE_HINTS or any("warehouse" in t for t in s):
        return "warehouse"
    if s & _COMMERCIAL_HINTS:
        return "commercial"
    if (
        "street_address" in s or "premise" in s or "subpremise" in s or "route" in s
    ) and "establishment" not in s:
        return "residential"
    return "unknown"


def _geocode_json_body(
    raw: dict[str, object], *, key: str
) -> tuple[bool, tuple[str, ...], str | None, str]:
    if str(raw.get("status") or "") != "OK":
        detail = str(raw.get("error_message") or raw.get("status") or "GEOCODE_ERROR")
        return False, (), detail, ""
    results = raw.get("results") or []
    if not isinstance(results, list) or not results:
        return False, (), "GEOCODE_EMPTY", ""
    r0 = results[0]
    if not isinstance(r0, dict):
        return False, (), "GEOCODE_EMPTY", ""
    types = tuple(str(x) for x in (r0.get("types") or []) if str(x).strip())
    formatted = _extract_formatted_address(r0)
    if not formatted.strip():
        latlng_fmt = _formatted_via_latlng(r0, key=key)
        if latlng_fmt:
            formatted = latlng_fmt
    return True, types, None, formatted


def _formatted_via_latlng(r0: dict, *, key: str) -> str:
    """When forward geocode returns OK but no formatted string, reverse by lat/lng."""
    if not key:
        return ""
    geom = r0.get("geometry") or {}
    if not isinstance(geom, dict):
        return ""
    loc = geom.get("location") or {}
    if not isinstance(loc, dict):
        return ""
    try:
        lat_f = float(loc.get("lat"))
        lng_f = float(loc.get("lng"))
    except (TypeError, ValueError):
        return ""
    params = urllib.parse.urlencode(
        {"latlng": f"{lat_f},{lng_f}", "key": key}
    )
    url = f"{_GEOCODE_URL}?{params}"
    raw = _http_get_json(url)
    if not isinstance(raw, dict) or str(raw.get("status") or "") != "OK":
        return ""
    results = raw.get("results") or []
    if not isinstance(results, list) or not results:
        return ""
    r1 = results[0]
    if not isinstance(r1, dict):
        return ""
    return _extract_formatted_address(r1)


def _geocode_address_raw(stripped: str, key: str) -> dict[str, object] | str:
    """GET when URL is short (Google's default); POST only when GET would exceed limits."""
    q = urllib.parse.urlencode({"address": stripped, "key": key})
    url = f"{_GEOCODE_URL}?{q}"
    if len(url) <= 7800:
        raw = _http_get_json(url)
        return raw
    data = urllib.parse.urlencode({"address": stripped, "key": key}).encode("utf-8")
    try:
        req = urllib.request.Request(
            _GEOCODE_URL,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "EW-v2/1.0",
            },
        )
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=15.0, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.reason}"
    except OSError as e:
        return str(e)
    except json.JSONDecodeError as e:
        return str(e)


def _geocode(
    addr: str, *, key: str
) -> tuple[bool, tuple[str, ...], str | None, str]:
    stripped = (addr or "").strip()
    if not stripped:
        return False, (), "GEOCODE_EMPTY_ADDRESS", ""
    raw = _geocode_address_raw(stripped, key)
    if isinstance(raw, str):
        return False, (), raw, ""
    if not isinstance(raw, dict):
        return False, (), "GEOCODE_BAD_JSON", ""
    return _geocode_json_body(raw, key=key)


def _extract_formatted_address(r0: dict) -> str:
    """Prefer Geocoding `formatted_address`; build a fallback if the API omits it."""
    fa = str(r0.get("formatted_address") or "").strip()
    if fa:
        return fa
    comps = r0.get("address_components")
    if isinstance(comps, list) and comps:
        long_names: list[str] = []
        for c in comps:
            if not isinstance(c, dict):
                continue
            ln = str(c.get("long_name") or "").strip()
            if ln:
                long_names.append(ln)
        if long_names:
            return ", ".join(long_names)
    pc = r0.get("plus_code")
    if isinstance(pc, dict):
        cc = str(pc.get("compound_code") or "").strip()
        if cc:
            return cc
    return ""


def _distance_miles(origin: str, destination: str, *, key: str) -> tuple[float | None, str | None]:
    params = urllib.parse.urlencode(
        {
            "origins": origin.strip(),
            "destinations": destination.strip(),
            "mode": "driving",
            "units": "imperial",
            "key": key,
        }
    )
    raw = _http_get_json(f"{_DISTANCE_URL}?{params}")
    if isinstance(raw, str):
        return None, raw
    if str(raw.get("status") or "") != "OK":
        return None, str(raw.get("status") or "DISTANCE_ERROR")
    rows = raw.get("rows") or []
    if not isinstance(rows, list) or not rows:
        return None, "DISTANCE_EMPTY"
    elems = (rows[0] or {}).get("elements") or []
    if not isinstance(elems, list) or not elems:
        return None, "DISTANCE_EMPTY"
    e0 = elems[0] or {}
    if str(e0.get("status") or "") != "OK":
        return None, str(e0.get("status") or "DISTANCE_ELEMENT_ERROR")
    meters = ((e0.get("distance") or {}).get("value")) if isinstance(e0, dict) else None
    if not isinstance(meters, (int, float)):
        return None, "DISTANCE_VALUE_MISSING"
    return round(float(meters) / 1609.344, 2), None


def validate_route(ship_from: str, ship_to: str) -> RouteValidation:
    load_env()
    origin = (ship_from or "").strip()
    dest = (ship_to or "").strip()
    if not origin or not dest:
        return RouteValidation(False, None, "unknown", "unknown", error_message="起终点地址不能为空")
    key = maps_api_key()
    if not key:
        return RouteValidation(False, None, "unknown", "unknown", error_message="缺少 GOOGLE_MAPS_API_KEY")

    ok_o, types_o, err_o, fmt_o = _geocode(origin, key=key)
    if ok_o:
        ok_d, types_d, err_d, fmt_d = _geocode(dest, key=key)
        if ok_d:
            o_dm = fmt_o if fmt_o else origin
            d_dm = fmt_d if fmt_d else dest
            miles, err_m = _distance_miles(o_dm, d_dm, key=key)
            if not err_m:
                return RouteValidation(
                    True,
                    miles,
                    _classify_land_use(types_o),
                    _classify_land_use(types_d),
                    origin_normalized=fmt_o,
                    dest_normalized=fmt_d,
                    maps_origin_formatted=fmt_o,
                    maps_dest_formatted=fmt_d,
                )
            initial_err = f"distance: {err_m}"
        else:
            initial_err = f"dest: {err_d}"
    else:
        initial_err = f"origin: {err_o}"

    # AI retry only when direct Google validation failed.
    ai = normalize_addresses_with_gemini(origin, dest)
    if not ai.ok:
        return RouteValidation(
            False,
            None,
            "unknown",
            "unknown",
            used_ai_retry=True,
            ai_confidence=ai.confidence,
            origin_normalized=ai.origin_normalized,
            dest_normalized=ai.destination_normalized,
            ai_notes=ai.notes,
            error_message=f"{initial_err}; ai: {ai.error_message}",
        )

    ok_o2, types_o2, err_o2, fmt_o2 = _geocode(ai.origin_normalized, key=key)
    if not ok_o2:
        return RouteValidation(
            False,
            None,
            "unknown",
            "unknown",
            used_ai_retry=True,
            ai_confidence=ai.confidence,
            origin_normalized=ai.origin_normalized,
            dest_normalized=ai.destination_normalized,
            ai_notes=ai.notes,
            error_message=f"{initial_err}; ai_origin: {err_o2}",
        )
    ok_d2, types_d2, err_d2, fmt_d2 = _geocode(ai.destination_normalized, key=key)
    if not ok_d2:
        return RouteValidation(
            False,
            None,
            _classify_land_use(types_o2),
            "unknown",
            used_ai_retry=True,
            ai_confidence=ai.confidence,
            origin_normalized=ai.origin_normalized,
            dest_normalized=ai.destination_normalized,
            ai_notes=ai.notes,
            error_message=f"{initial_err}; ai_dest: {err_d2}",
        )
    miles2, err_m2 = _distance_miles(
        fmt_o2 if fmt_o2 else ai.origin_normalized,
        fmt_d2 if fmt_d2 else ai.destination_normalized,
        key=key,
    )
    if err_m2:
        return RouteValidation(
            False,
            None,
            _classify_land_use(types_o2),
            _classify_land_use(types_d2),
            used_ai_retry=True,
            ai_confidence=ai.confidence,
            origin_normalized=ai.origin_normalized,
            dest_normalized=ai.destination_normalized,
            ai_notes=ai.notes,
            error_message=f"{initial_err}; ai_distance: {err_m2}",
        )
    return RouteValidation(
        True,
        miles2,
        _classify_land_use(types_o2),
        _classify_land_use(types_d2),
        used_ai_retry=True,
        ai_confidence=ai.confidence,
        origin_normalized=ai.origin_normalized,
        dest_normalized=ai.destination_normalized,
        ai_notes=ai.notes,
        maps_origin_formatted=fmt_o2,
        maps_dest_formatted=fmt_d2,
    )

