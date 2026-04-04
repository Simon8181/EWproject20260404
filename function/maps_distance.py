"""
Google Maps：**Distance Matrix**（驾车 **英里 mi**）+ **Geocoding**（地址类型）。

- **距离（mile）**：Distance Matrix 的 `distance.value` 为米，换算为 **mi**；请求 `units=imperial` 时 `distance_text` 为 **「x mi」** 文案（不依赖 Sheet Q 列）。
- **地址类型（可查）**：**Geocoding API** 对起、终点各查一次，返回：
  - **`types`**：地点类别，如 `street_address`（门牌级）、`route`、`locality`（城市）、`premise` 等；
  - **`geometry.location_type`**：定位精度，如 `ROOFTOP`、`APPROXIMATE` 等。

需在 GCP 启用：**Distance Matrix API**、**Geocoding API**，并配置 **`GOOGLE_MAPS_API_KEY`**。

文档：
- https://developers.google.com/maps/documentation/distance-matrix
- https://developers.google.com/maps/documentation/geocoding
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from function.api_config import maps_api_key

_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def _http_get_json(url: str, timeout: float = 15.0) -> dict[str, object] | str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EW-Sheet-Service/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.reason}"
    except OSError as e:
        return str(e)
    except json.JSONDecodeError as e:
        return str(e)


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
    """单地址地理编码：类型与精度。"""

    ok: bool
    types: tuple[str, ...]
    """Google 地点类别，如 street_address、route、locality、country。"""
    location_type: str | None
    """定位精度：ROOFTOP、RANGE_INTERPOLATED、GEOMETRIC_CENTER、APPROXIMATE。"""
    formatted_address: str
    google_status: str
    error_message: str | None = None


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
    fmt = str(r0.get("formatted_address") or "")

    return GeocodeDetailResult(
        ok=True,
        types=types_t,
        location_type=loc_s,
        formatted_address=fmt,
        google_status=gstatus,
        error_message=None,
    )


def fetch_route_insight(origin: str, destination: str) -> RouteInsightResult:
    """
    合并：**驾车距离（mi）** + 起终点 **地址 types / location_type** + 规范地址。
    忽略 Sheet Q 列；全部来自 Maps API。
    """
    dr = fetch_driving_distance(origin, destination)
    go = fetch_geocode_detail(origin)
    gd = fetch_geocode_detail(destination)

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
        error_message="; ".join(err_parts) if err_parts and not ok else (None if ok else "; ".join(err_parts)),
    )
