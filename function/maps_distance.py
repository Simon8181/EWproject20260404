"""
Google Maps：**Distance Matrix**（驾车 **英里 mi**）+ **Geocoding**（地址类型）。

- **距离（mile）**：Distance Matrix 的 `distance.value` 为米，换算为 **mi**；请求 `units=imperial` 时 `distance_text` 为 **「x mi」** 文案（不依赖 Sheet Q 列）。
- **地址类型（可查）**：**Geocoding API** 对起、终点各查一次，返回：
  - **`types`**：地点类别，如 `street_address`（门牌级）、`route`、`locality`（城市）、`premise` 等；
  - **`geometry.location_type`**：定位精度，如 `ROOFTOP`、`APPROXIMATE` 等。
- **用途标签（land use）**：Geocoding 的 `types` **不会**直接给出 residential / commercial / warehouse。
  本模块将 Google 返回的 type 集合 **映射**为英文：`warehouse`、`commercial`、`residential`、`unknown`。
  若设置 **`ORDER_PLACES_LAND_USE=1`**，在 Geocode 成功后会对 **`place_id`** 再调 **Place Details**（`fields=types`），
  合并 Places 的细分类（如 `storage`）后再分类；需在 GCP 额外启用 **Places API**，且每端多一次 HTTPS。

需在 GCP 启用：**Distance Matrix API**、**Geocoding API**，并配置 **`GOOGLE_MAPS_API_KEY`**。

**回退**：若用整段文字算距失败，但两端 Geocode 已得到 **坐标**，则再用 **起点→终点坐标** 调 Distance Matrix（与在 Maps 里用两点算路一致）；地址类型仍来自成功的那次 Geocode。

文档：
- https://developers.google.com/maps/documentation/distance-matrix
- https://developers.google.com/maps/documentation/geocoding
- https://developers.google.com/maps/documentation/places/web-service/details
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import certifi

from function.api_config import maps_api_key

_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
_PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# --- Land-use labels (English) from merged Geocoding + Places `types` ---
_WAREHOUSE_TYPES: frozenset[str] = frozenset(
    {
        "storage",
        "moving_company",
    }
)
LAND_USE_VALUES: frozenset[str] = frozenset(
    ("warehouse", "commercial", "residential", "unknown")
)

_COMMERCIAL_TYPES: frozenset[str] = frozenset(
    {
        "establishment",
        "point_of_interest",
        "store",
        "shopping_mall",
        "clothing_store",
        "electronics_store",
        "furniture_store",
        "hardware_store",
        "home_goods_store",
        "department_store",
        "supermarket",
        "convenience_store",
        "pharmacy",
        "restaurant",
        "food",
        "bakery",
        "bar",
        "cafe",
        "meal_takeaway",
        "meal_delivery",
        "bank",
        "atm",
        "gas_station",
        "car_dealer",
        "car_repair",
        "car_rental",
        "car_wash",
        "parking",
        "lodging",
        "movie_theater",
        "gym",
        "spa",
        "night_club",
        "office",
        "real_estate_agency",
        "accounting",
        "insurance_agency",
        "lawyer",
        "hospital",
        "doctor",
        "dentist",
        "school",
        "university",
        "library",
        "post_office",
        "subway_station",
        "train_station",
        "transit_station",
        "bus_station",
        "airport",
        "travel_agency",
        "beauty_salon",
        "hair_care",
    }
)


def _places_land_use_enabled() -> bool:
    v = (os.environ.get("ORDER_PLACES_LAND_USE") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def classify_land_use(types: tuple[str, ...]) -> str:
    """
    Map merged Geocoding / Places `types` to warehouse | commercial | residential | unknown.

    Google does not provide a dedicated "residential" type; "residential" here means
    street-level address components without business POI markers (best-effort).
    """
    s = {x.strip().lower() for x in types if x and str(x).strip()}
    if not s:
        return "unknown"

    if s & _WAREHOUSE_TYPES or any("warehouse" in t for t in s):
        return "warehouse"

    if {"park", "natural_feature", "campground"} & s:
        return "unknown"

    if s & _COMMERCIAL_TYPES:
        return "commercial"

    addrish = (
        "street_address" in s
        or "premise" in s
        or "subpremise" in s
        or "route" in s
    )
    if addrish and "establishment" not in s and "point_of_interest" not in s:
        return "residential"

    return "unknown"


def normalize_land_use_label(value: str | None) -> str:
    """Clamp to warehouse | commercial | residential | unknown."""
    v = (value or "unknown").strip().lower()
    if v not in LAND_USE_VALUES:
        return "unknown"
    return v


def _http_get_json(url: str, timeout: float = 15.0) -> dict[str, object] | str:
    # Use certifi's CA bundle: on some macOS/Python installs the default chain
    # fails with CERTIFICATE_VERIFY_FAILED / unable to get local issuer certificate.
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        req = urllib.request.Request(url, headers={"User-Agent": "EW-Sheet-Service/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.reason}"
    except OSError as e:
        return str(e)
    except json.JSONDecodeError as e:
        return str(e)


def fetch_place_types(place_id: str) -> tuple[str, ...]:
    """Place Details `types` only; empty on failure."""
    pid = (place_id or "").strip()
    key = maps_api_key()
    if not pid or not key:
        return ()
    params = urllib.parse.urlencode(
        {"place_id": pid, "fields": "types", "key": key}
    )
    url = f"{_PLACE_DETAILS_URL}?{params}"
    raw = _http_get_json(url)
    if isinstance(raw, str):
        return ()
    if str(raw.get("status") or "") != "OK":
        return ()
    result = raw.get("result")
    if not isinstance(result, dict):
        return ()
    tr = result.get("types") or []
    if not isinstance(tr, list):
        return ()
    return tuple(str(x) for x in tr)


@dataclass(frozen=True)
class DrivingDistanceResult:
    """驾车矩阵：路程与时间。"""

    ok: bool
    distance_meters: float | None
    distance_km: float | None
    distance_miles: float | None
    distance_text: str
    duration_seconds: int | None
    duration_text: str
    google_status: str
    element_status: str | None
    error_message: str | None = None


@dataclass(frozen=True)
class GeocodeDetailResult:
    """单地址地理编码：类型与精度，以及 geometry.location（供坐标算距回退）。"""

    ok: bool
    types: tuple[str, ...]
    """Google 地点类别，如 street_address、route、locality、country。"""
    location_type: str | None
    """定位精度：ROOFTOP、RANGE_INTERPOLATED、GEOMETRIC_CENTER、APPROXIMATE。"""
    formatted_address: str
    google_status: str
    error_message: str | None = None
    lat: float | None = None
    lng: float | None = None
    place_id: str | None = None
    """Geocoding `place_id`；若开启 ORDER_PLACES_LAND_USE 则用于 Place Details。"""
    place_types: tuple[str, ...] = ()
    """Place Details 返回的 types（仅当 ORDER_PLACES_LAND_USE=1 且请求成功）。"""
    land_use: str | None = None
    """当 ok=True 时为 warehouse / commercial / residential / unknown 之一。"""


def land_use_for_geocode_side(g: GeocodeDetailResult) -> str:
    """Recorded label for one side after a geocode attempt (failed geocode → unknown)."""
    if not g.ok:
        return "unknown"
    return normalize_land_use_label(g.land_use)


@dataclass(frozen=True)
class RouteInsightResult:
    """一次「起点 + 终点」：**驾车 mi** + 两端 **types / location_type**（供 quote 等复用）。"""

    ok: bool
    distance_miles: float | None
    distance_km: float | None
    distance_text: str
    duration_seconds: int | None
    duration_text: str
    origin_types: tuple[str, ...]
    destination_types: tuple[str, ...]
    origin_location_type: str | None
    destination_location_type: str | None
    origin_formatted: str
    destination_formatted: str
    google_distance_status: str
    element_status: str | None
    # 各端 Geocoding 的 status（OK、REQUEST_DENIED、ZERO_RESULTS 等），便于排查「有里程无类型」
    origin_geocode_status: str
    destination_geocode_status: str
    origin_land_use: str | None = None  # warehouse|commercial|residential|unknown when set
    destination_land_use: str | None = None
    error_message: str | None = None


def fetch_driving_distance(origin: str, destination: str) -> DrivingDistanceResult:
    """
    驾车距离与时间；`units=imperial`，`distance_text` 为 **英里** 文案；数值由米换算 **mi / km**。
    """
    o = (origin or "").strip()
    d = (destination or "").strip()
    key = maps_api_key()
    if not key:
        return DrivingDistanceResult(
            ok=False,
            distance_meters=None,
            distance_km=None,
            distance_miles=None,
            distance_text="",
            duration_seconds=None,
            duration_text="",
            google_status="MISSING_KEY",
            element_status=None,
            error_message="Set GOOGLE_MAPS_API_KEY (Distance Matrix API enabled).",
        )
    if len(o) < 2 or len(d) < 2:
        return DrivingDistanceResult(
            ok=False,
            distance_meters=None,
            distance_km=None,
            distance_miles=None,
            distance_text="",
            duration_seconds=None,
            duration_text="",
            google_status="INVALID_INPUT",
            element_status=None,
            error_message="origin and destination must be non-empty.",
        )

    params = urllib.parse.urlencode(
        {
            "origins": o,
            "destinations": d,
            "units": "imperial",
            "mode": "driving",
            "key": key,
        }
    )
    url = f"{_DISTANCE_MATRIX_URL}?{params}"
    raw = _http_get_json(url)
    if isinstance(raw, str):
        return DrivingDistanceResult(
            ok=False,
            distance_meters=None,
            distance_km=None,
            distance_miles=None,
            distance_text="",
            duration_seconds=None,
            duration_text="",
            google_status="REQUEST_FAILED",
            element_status=None,
            error_message=raw,
        )

    gstatus = str(raw.get("status") or "")
    if gstatus != "OK":
        return DrivingDistanceResult(
            ok=False,
            distance_meters=None,
            distance_km=None,
            distance_miles=None,
            distance_text="",
            duration_seconds=None,
            duration_text="",
            google_status=gstatus,
            element_status=None,
            error_message=str(raw.get("error_message") or gstatus),
        )

    rows = raw.get("rows") or []
    if not rows or not isinstance(rows[0], dict):
        return DrivingDistanceResult(
            ok=False,
            distance_meters=None,
            distance_km=None,
            distance_miles=None,
            distance_text="",
            duration_seconds=None,
            duration_text="",
            google_status=gstatus,
            element_status="NO_ROWS",
            error_message="empty rows",
        )

    elements = rows[0].get("elements") or []
    if not elements or not isinstance(elements[0], dict):
        return DrivingDistanceResult(
            ok=False,
            distance_meters=None,
            distance_km=None,
            distance_miles=None,
            distance_text="",
            duration_seconds=None,
            duration_text="",
            google_status=gstatus,
            element_status="NO_ELEMENTS",
            error_message="no elements",
        )

    el = elements[0]
    estatus = str(el.get("status") or "")
    if estatus != "OK":
        return DrivingDistanceResult(
            ok=False,
            distance_meters=None,
            distance_km=None,
            distance_miles=None,
            distance_text="",
            duration_seconds=None,
            duration_text="",
            google_status=gstatus,
            element_status=estatus,
            error_message=estatus,
        )

    dist = el.get("distance") or {}
    dur = el.get("duration") or {}
    dist_text = str(dist.get("text") or "")
    dur_text = str(dur.get("text") or "")
    meters = dist.get("value")
    seconds = dur.get("value")

    dm: float | None = None
    km: float | None = None
    mi: float | None = None
    if isinstance(meters, (int, float)):
        dm = float(meters)
        km = dm / 1000.0
        mi = dm / 1609.344

    sec_i: int | None = None
    if isinstance(seconds, (int, float)):
        sec_i = int(seconds)

    return DrivingDistanceResult(
        ok=True,
        distance_meters=dm,
        distance_km=km,
        distance_miles=mi,
        distance_text=dist_text,
        duration_seconds=sec_i,
        duration_text=dur_text,
        google_status=gstatus,
        element_status=estatus,
        error_message=None,
    )


def fetch_geocode_detail(address: str) -> GeocodeDetailResult:
    """
    查询单地址的 **types**（地址/地点类型）与 **location_type**（定位精度）。
    """
    a = (address or "").strip()
    key = maps_api_key()
    if not key:
        return GeocodeDetailResult(
            ok=False,
            types=(),
            location_type=None,
            formatted_address="",
            google_status="MISSING_KEY",
            error_message="Set GOOGLE_MAPS_API_KEY (Geocoding API enabled).",
        )
    if len(a) < 2:
        return GeocodeDetailResult(
            ok=False,
            types=(),
            location_type=None,
            formatted_address="",
            google_status="INVALID_INPUT",
            error_message="address empty",
        )

    params = urllib.parse.urlencode({"address": a, "key": key})
    url = f"{_GEOCODE_URL}?{params}"
    raw = _http_get_json(url)
    if isinstance(raw, str):
        return GeocodeDetailResult(
            ok=False,
            types=(),
            location_type=None,
            formatted_address="",
            google_status="REQUEST_FAILED",
            error_message=raw,
        )

    gstatus = str(raw.get("status") or "")
    if gstatus != "OK":
        return GeocodeDetailResult(
            ok=False,
            types=(),
            location_type=None,
            formatted_address="",
            google_status=gstatus,
            error_message=str(raw.get("error_message") or gstatus),
        )

    results = raw.get("results") or []
    if not results or not isinstance(results[0], dict):
        return GeocodeDetailResult(
            ok=False,
            types=(),
            location_type=None,
            formatted_address="",
            google_status=gstatus,
            error_message="ZERO_RESULTS",
        )

    r0 = results[0]
    types_raw = r0.get("types") or []
    types_t = tuple(str(x) for x in types_raw) if isinstance(types_raw, list) else ()
    geom = r0.get("geometry") or {}
    loc_type = geom.get("location_type")
    loc_s = str(loc_type) if loc_type is not None else None
    loc_pt = geom.get("location") or {}
    lat_v = loc_pt.get("lat")
    lng_v = loc_pt.get("lng")
    lat_f = float(lat_v) if isinstance(lat_v, (int, float)) else None
    lng_f = float(lng_v) if isinstance(lng_v, (int, float)) else None
    fmt = str(r0.get("formatted_address") or "")
    place_id = str(r0.get("place_id") or "").strip() or None

    place_types_t: tuple[str, ...] = ()
    if place_id and _places_land_use_enabled():
        place_types_t = fetch_place_types(place_id)

    merged_types = tuple(types_t) + place_types_t
    land_use_v = classify_land_use(merged_types)

    return GeocodeDetailResult(
        ok=True,
        types=types_t,
        location_type=loc_s,
        formatted_address=fmt,
        google_status=gstatus,
        error_message=None,
        lat=lat_f,
        lng=lng_f,
        place_id=place_id,
        place_types=place_types_t,
        land_use=land_use_v,
    )


def _address_variants(primary_hint: str, full_blob: str) -> list[str]:
    """优先 hint，再全文，再逐行；去重且长度≥2。"""
    out: list[str] = []
    seen: set[str] = set()
    for part in [primary_hint, full_blob] + [
        ln.strip() for ln in (full_blob or "").splitlines() if ln.strip()
    ]:
        p = (part or "").strip()
        if len(p) >= 2 and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _geocode_first_ok(variants: list[str]) -> GeocodeDetailResult:
    """多候选串依次 Geocode，返回首个 OK；全失败则返回最后一次尝试（便于展示 status）。"""
    last: GeocodeDetailResult | None = None
    for v in variants:
        r = fetch_geocode_detail(v)
        last = r
        if r.ok and r.google_status == "OK":
            return r
    if last is not None:
        return last
    return GeocodeDetailResult(
        ok=False,
        types=(),
        location_type=None,
        formatted_address="",
        google_status="NO_VARIANTS",
        error_message="no address variants",
    )


def _driving_distance_via_coords(go: GeocodeDetailResult, gd: GeocodeDetailResult) -> DrivingDistanceResult | None:
    """两端均有坐标时，用 lat,lng 调 Distance Matrix（文本失败时常能成功）。"""
    if not (go.ok and gd.ok and go.lat is not None and go.lng is not None and gd.lat is not None and gd.lng is not None):
        return None
    return fetch_driving_distance(f"{go.lat},{go.lng}", f"{gd.lat},{gd.lng}")


def fetch_route_insight(
    origin: str,
    destination: str,
    *,
    origin_for_geocode: str | None = None,
    destination_for_geocode: str | None = None,
) -> RouteInsightResult:
    """
    合并：**驾车距离（mi）** + 起终点 **types / location_type**。

    1. 对起、终点做多候选 **Geocode**（hint、全文、分行），拿到类型与坐标。
    2. 驾车距离先对 **全文** 调 Distance Matrix。
    3. 若距离仍失败且两端 Geocode 均有 **lat/lng**，再用 **坐标对** 调 Matrix（与 Maps 网页「两点」一致）。
    """
    o_full = (origin or "").strip()
    d_full = (destination or "").strip()
    o_hint = (origin_for_geocode if origin_for_geocode is not None else o_full).strip()
    d_hint = (destination_for_geocode if destination_for_geocode is not None else d_full).strip()
    if len(o_hint) < 2:
        o_hint = o_full
    if len(d_hint) < 2:
        d_hint = d_full

    go = _geocode_first_ok(_address_variants(o_hint, o_full))
    gd = _geocode_first_ok(_address_variants(d_hint, d_full))

    dr = fetch_driving_distance(o_full, d_full)
    if not dr.ok:
        dr2 = _driving_distance_via_coords(go, gd)
        if dr2 is not None and dr2.ok:
            dr = dr2

    ok = dr.ok
    err_parts: list[str] = []
    if dr.error_message:
        err_parts.append(dr.error_message)
    if not go.ok and go.error_message:
        err_parts.append(f"origin geocode: {go.error_message}")
    if not gd.ok and gd.error_message:
        err_parts.append(f"destination geocode: {gd.error_message}")

    return RouteInsightResult(
        ok=ok,
        distance_miles=dr.distance_miles,
        distance_km=dr.distance_km,
        distance_text=dr.distance_text,
        duration_seconds=dr.duration_seconds,
        duration_text=dr.duration_text,
        origin_types=go.types,
        destination_types=gd.types,
        origin_location_type=go.location_type,
        destination_location_type=gd.location_type,
        origin_formatted=go.formatted_address,
        destination_formatted=gd.formatted_address,
        google_distance_status=dr.google_status,
        element_status=dr.element_status,
        origin_geocode_status=go.google_status,
        destination_geocode_status=gd.google_status,
        origin_land_use=land_use_for_geocode_side(go),
        destination_land_use=land_use_for_geocode_side(gd),
        error_message="; ".join(err_parts) if err_parts and not ok else (None if ok else "; ".join(err_parts)),
    )
