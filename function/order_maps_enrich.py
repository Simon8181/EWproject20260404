"""
Google Maps 批量补全（**不在** Sheet 同步中调用）。

由订单页「格式化数据（规范化邮编）」按钮触发：对 `ew_orders` 全表逐条检查；缺距离 / Geocode types / 跳转链接时
调用 `fetch_route_insight`，回写标准地址、Land use、驾车距离与 `maps_*_href`。

环境：`GOOGLE_MAPS_API_KEY`；`EW_ORDER_MAPS_BATCH_DELAY_MS` 每条之间的延迟（毫秒）。
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import psycopg
import psycopg.errors

from function.address_display import resolve_origin_for_order
from function.api_config import google_maps_api_key, reload_api_env
from function.ew_sort import sort_order_rows_for_display
from function.maps_distance import RouteInsightResult, fetch_route_insight
from function.order_cargo_ft import cargo_metrics_payload_from_row
from function.order_zip import first_us_zip, is_valid_us_zip5, strip_us_zip_plus4_from_text
from function.route_metrics import google_maps_directions_url, google_maps_search_url
from function.sheet_sync.config import database_url
from function.sheet_sync.db_orders import load_ew_orders_from_db

logger = logging.getLogger(__name__)

# 与 ew_orders 列一致（不含 Sheet 列）
MAPS_ENRICH_DB_COLUMNS: tuple[str, ...] = (
    "google_distance_miles",
    "google_distance_text",
    "google_route_duration_text",
    "origin_formatted_address",
    "destination_formatted_address",
    "origin_geocode_types",
    "destination_geocode_types",
    "origin_location_type",
    "destination_location_type",
    "origin_land_use",
    "destination_land_use",
    "maps_origin_geocode_status",
    "maps_dest_geocode_status",
    "maps_enriched_at",
    "maps_enrich_error",
    "maps_origin_href",
    "maps_dest_href",
    "maps_directions_href",
    "ship_from",
    "ship_from_zip",
    "ship_from_city",
    "ship_from_state",
    "consignee_address",
    "consignee_zip",
    "consignee_city",
    "consignee_state",
    "cargo_density_pcf",
    "freight_class_nmfc",
)


def pick_line_for_geocode(blob: str) -> str:
    """
    Geocoding 对多行「地址+联系人」整段查询易 ZERO_RESULTS；优先含邮编/门牌的一行。
    驾车距离仍用全文（Distance Matrix 更宽松）。
    """
    raw = (blob or "").strip()
    if not raw:
        return ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) <= 1:
        return lines[0] if lines else ""
    zip_us = re.compile(r"\b\d{5}(-\d{4})?\b")
    for ln in lines:
        if zip_us.search(ln) and len(ln) >= 8:
            return ln
    for ln in lines:
        if re.match(r"^\d+\s+\S", ln):
            return ln
    for ln in lines:
        if "," in ln and any(ch.isdigit() for ch in ln):
            return ln
    return lines[0]


def _batch_delay_sec() -> float:
    try:
        ms = int(os.environ.get("EW_ORDER_MAPS_BATCH_DELAY_MS", "0"))
    except ValueError:
        return 0.0
    return max(0.0, ms / 1000.0)


def _force_maps_reenrich() -> bool:
    """为 true 时不跳过「已补全」行，对全表重新请求 Google（费配额；用于验证或字段逻辑更新后重算）。"""
    v = (os.environ.get("EW_ORDER_MAPS_FORCE_ENRICH") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _has_origin_dest_for_maps(r: dict[str, Any]) -> bool:
    _, ship_maps_raw = resolve_origin_for_order(r)
    dest_addr = str(r.get("consignee_address", "") or "")
    dest_contact = str(r.get("consignee_contact", "") or "")
    dest_combined = "\n".join(x for x in (dest_addr.strip(), dest_contact.strip()) if x)
    o = (ship_maps_raw or "").strip() or str(r.get("ship_from", "") or "").strip()
    return len(o) >= 2 and len(dest_combined.strip()) >= 2


def _has_distance(r: dict[str, Any]) -> bool:
    if str(r.get("google_distance_text") or "").strip():
        return True
    v = r.get("google_distance_miles")
    if v is None or v == "":
        return False
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _has_geocode_types(r: dict[str, Any]) -> bool:
    """Geocode 的 types；若为空则退而求其次：两端 Land use 均有值（含 unknown）。"""
    ot = str(r.get("origin_geocode_types") or "").strip()
    dt = str(r.get("destination_geocode_types") or "").strip()
    if ot and dt:
        return True
    ol = str(r.get("origin_land_use") or "").strip()
    dl = str(r.get("destination_land_use") or "").strip()
    return bool(ol) and bool(dl)


def _has_map_hrefs(r: dict[str, Any]) -> bool:
    return (
        bool(str(r.get("maps_origin_href") or "").strip())
        and bool(str(r.get("maps_dest_href") or "").strip())
        and bool(str(r.get("maps_directions_href") or "").strip())
    )


def maps_row_complete(r: dict[str, Any]) -> bool:
    """同时具备：驾车距离、两端 Geocode types、三向跳转链接。"""
    return _has_distance(r) and _has_geocode_types(r) and _has_map_hrefs(r)


_ZIP_PLUS4_IN_TEXT = re.compile(r"\b\d{5}-\d{4}\b")
_ZIP9_RUN = re.compile(r"\b\d{5}\d{4}\b")


def _maps_row_needs_zip_canonicalize(r: dict[str, Any]) -> bool:
    """文案或邮编列里仍有 ZIP+4 / 9 位连写，或 zip 列非严格 5 位。"""
    blobs = [
        str(r.get("ship_from") or ""),
        str(r.get("consignee_address") or ""),
        str(r.get("consignee_contact") or ""),
        str(r.get("origin_formatted_address") or ""),
        str(r.get("destination_formatted_address") or ""),
    ]
    joined = "\n".join(blobs)
    if _ZIP_PLUS4_IN_TEXT.search(joined) or _ZIP9_RUN.search(joined):
        return True
    for key in ("ship_from_zip", "consignee_zip"):
        z = str(r.get(key) or "").strip()
        if z and not is_valid_us_zip5(z):
            return True
    return False


def _maps_row_needs_city_state_backfill(r: dict[str, Any]) -> bool:
    """
    折叠行要 City, ST + 5 位邮编：任一端缺 city/state 即应再跑（含 Geocode 曾非 OK、仅有 land_use 却标为「完整」的旧数据）。
    """
    if not _has_origin_dest_for_maps(r):
        return False
    if not str(r.get("ship_from_city") or "").strip() or not str(
        r.get("ship_from_state") or ""
    ).strip():
        return True
    if not str(r.get("consignee_city") or "").strip() or not str(
        r.get("consignee_state") or ""
    ).strip():
        return True
    return False


def _maps_row_should_skip_maps_api(r: dict[str, Any]) -> bool:
    """
    已齐 Maps 缓存且无需再补邮编/city/state 时可跳过（省配额）。
    """
    if _force_maps_reenrich():
        return False
    if not maps_row_complete(r):
        return False
    if _maps_row_needs_city_state_backfill(r):
        return False
    if _maps_row_needs_zip_canonicalize(r):
        return False
    return True


def maps_row_needs_attention(r: dict[str, Any]) -> bool:
    """有起终点文案但仍未凑齐 Maps 结果 → 高亮「待解决」。"""
    if not _has_origin_dest_for_maps(r):
        return False
    return not maps_row_complete(r)


def _apply_route_insight_to_payload(
    ri: RouteInsightResult,
    *,
    ship_maps_raw: str,
    dest_combined: str,
    now: datetime,
) -> dict[str, Any]:
    o_fmt = (ri.origin_formatted or "").strip()
    d_fmt = (ri.destination_formatted or "").strip()
    o_for_link = o_fmt or (ship_maps_raw or "").strip()
    d_for_link = d_fmt or (dest_combined or "").strip()

    err = (ri.error_message or "").strip()

    out: dict[str, Any] = {
        "google_distance_miles": ri.distance_miles,
        "google_distance_text": (ri.distance_text or "").strip() or None,
        "google_route_duration_text": (ri.duration_text or "").strip() or None,
        "origin_formatted_address": o_fmt or None,
        "destination_formatted_address": d_fmt or None,
        "origin_geocode_types": ";".join(ri.origin_types) if ri.origin_types else None,
        "destination_geocode_types": ";".join(ri.destination_types)
        if ri.destination_types
        else None,
        "origin_location_type": (ri.origin_location_type or "").strip() or None,
        "destination_location_type": (ri.destination_location_type or "").strip() or None,
        "origin_land_use": (ri.origin_land_use or "").strip() or None,
        "destination_land_use": (ri.destination_land_use or "").strip() or None,
        "maps_origin_geocode_status": (ri.origin_geocode_status or "").strip() or None,
        "maps_dest_geocode_status": (ri.destination_geocode_status or "").strip() or None,
        "maps_enriched_at": now,
        "maps_enrich_error": err if err else None,
        "maps_origin_href": google_maps_search_url(o_for_link) or None,
        "maps_dest_href": google_maps_search_url(d_for_link) or None,
        "maps_directions_href": google_maps_directions_url(o_for_link, d_for_link) or None,
    }

    # 回写 Sheet 镜像列：Google 标准起运 / 目的与邮编（下次 Sheet 同步会覆盖）
    zip_notes: list[str] = []
    if (ri.origin_geocode_status or "").strip() == "OK" and o_fmt:
        out["ship_from"] = strip_us_zip_plus4_from_text(o_fmt)
    oz_src = (ri.origin_postal_code or "").strip() or (first_us_zip(o_fmt) if o_fmt else "")
    oz = first_us_zip(oz_src) if oz_src else ""
    if oz:
        if is_valid_us_zip5(oz):
            out["ship_from_zip"] = oz
        else:
            zip_notes.append("起运邮编非美国5位数字")
    elif oz_src:
        zip_notes.append("起运邮编无法规范为美国5位")
    if (ri.origin_geocode_status or "").strip() == "OK":
        if (ri.origin_city or "").strip():
            out["ship_from_city"] = (ri.origin_city or "").strip()
        if (ri.origin_state or "").strip():
            out["ship_from_state"] = (ri.origin_state or "").strip()
    if (ri.destination_geocode_status or "").strip() == "OK" and d_fmt:
        out["consignee_address"] = strip_us_zip_plus4_from_text(d_fmt)
    dz_src = (ri.destination_postal_code or "").strip() or (first_us_zip(d_fmt) if d_fmt else "")
    dz = first_us_zip(dz_src) if dz_src else ""
    if dz:
        if is_valid_us_zip5(dz):
            out["consignee_zip"] = dz
        else:
            zip_notes.append("目的邮编非美国5位数字")
    elif dz_src:
        zip_notes.append("目的邮编无法规范为美国5位")
    if (ri.destination_geocode_status or "").strip() == "OK":
        if (ri.destination_city or "").strip():
            out["consignee_city"] = (ri.destination_city or "").strip()
        if (ri.destination_state or "").strip():
            out["consignee_state"] = (ri.destination_state or "").strip()
    if zip_notes:
        merged = "; ".join(zip_notes)
        if err:
            out["maps_enrich_error"] = f"{err}; {merged}"
        else:
            out["maps_enrich_error"] = merged

    return out


def _fetch_maps_payload_for_order_row(row: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    dest_addr = str(row.get("consignee_address", "") or "")
    dest_contact = str(row.get("consignee_contact", "") or "")
    dest_combined = "\n".join(x for x in (dest_addr.strip(), dest_contact.strip()) if x)

    _, ship_maps_raw = resolve_origin_for_order(row)
    o_full = (ship_maps_raw or "").strip() or str(row.get("ship_from", "") or "").strip()
    if len(o_full) < 2 or len(dest_combined.strip()) < 2:
        p: dict[str, Any] = {
            "maps_enriched_at": now,
            "maps_enrich_error": "missing origin or destination",
        }
        p.update(cargo_metrics_payload_from_row(row))
        return p

    geo_o = pick_line_for_geocode(ship_maps_raw) or (ship_maps_raw or "").strip()
    geo_d = pick_line_for_geocode(dest_combined) or dest_combined.strip()

    ri = fetch_route_insight(
        ship_maps_raw,
        dest_combined,
        origin_for_geocode=geo_o,
        destination_for_geocode=geo_d,
    )
    base = _apply_route_insight_to_payload(
        ri,
        ship_maps_raw=ship_maps_raw or "",
        dest_combined=dest_combined,
        now=now,
    )
    base.update(cargo_metrics_payload_from_row(row))
    return base


def _update_ew_order_maps(conn: psycopg.Connection, ew_quote_no: str, payload: dict[str, Any]) -> None:
    cols = [c for c in MAPS_ENRICH_DB_COLUMNS if c in payload]
    if not cols:
        return
    set_clause = ", ".join(f'"{c}" = %s' for c in cols)
    values = [payload[c] for c in cols]
    sql = f'UPDATE "ew_orders" SET {set_clause} WHERE "ew_quote_no" = %s'
    with conn.cursor() as cur:
        cur.execute(sql, values + [ew_quote_no])


def _apply_cargo_metrics_to_all_rows(
    conn: psycopg.Connection,
    rows_any: list[dict[str, Any]],
) -> int:
    """
    先全表写 Ft / Class（不调用 Google，不依赖 Maps 是否已齐）。
    返回成功写入（至少含密度或等级）的行数。
    """
    n = 0
    for r in rows_any:
        qn = str(r.get("ew_quote_no") or "").strip()
        if not qn:
            continue
        cargo_payload = cargo_metrics_payload_from_row(r)
        if not cargo_payload:
            continue
        try:
            _update_ew_order_maps(conn, qn, cargo_payload)
            conn.commit()
            n += 1
        except psycopg.errors.UndefinedColumn as e:
            conn.rollback()
            raise RuntimeError(
                "数据库缺少货物密度/等级列。请执行："
                "psql \"$DATABASE_URL\" -f db/migration_ew_orders_cargo_density.sql && "
                "psql \"$DATABASE_URL\" -f db/migration_ew_orders_freight_class.sql"
            ) from e
        except Exception:
            logger.exception("cargo metrics update failed for %s", qn)
            conn.rollback()
    return n


def batch_enrich_all_ew_orders_maps() -> dict[str, Any]:
    """
    全表排序与订单页一致。
    1) 先写货物 Ft / Class（本地计算，不依赖 Google）。
    2) 再对需补 Maps 的行请求 API（需 GOOGLE_MAPS_API_KEY）。
    返回 enriched、skipped、cargo_updated。
    """
    reload_api_env()
    raw = load_ew_orders_from_db()
    rows_any: list[dict[str, Any]] = [dict(r) for r in raw]
    rows_any = sort_order_rows_for_display(rows_any)

    url = database_url()
    cargo_updated = 0
    with psycopg.connect(url) as conn:
        cargo_updated = _apply_cargo_metrics_to_all_rows(conn, rows_any)

    if not google_maps_api_key():
        return {
            "enriched": 0,
            "skipped": len(rows_any),
            "cargo_updated": cargo_updated,
        }

    enriched = 0
    skipped = 0
    delay = _batch_delay_sec()

    with psycopg.connect(url) as conn:
        for r in rows_any:
            qn = str(r.get("ew_quote_no") or "").strip()
            if not qn:
                skipped += 1
                continue
            cargo_payload = cargo_metrics_payload_from_row(r)
            maps_skip = _maps_row_should_skip_maps_api(r) or not _has_origin_dest_for_maps(r)
            if maps_skip:
                skipped += 1
                continue
            try:
                payload = _fetch_maps_payload_for_order_row(r)
                payload.update(cargo_payload)
                _update_ew_order_maps(conn, qn, payload)
                conn.commit()
                enriched += 1
            except Exception as e:
                logger.exception("maps enrich failed for %s", qn)
                err_now = datetime.now(timezone.utc)
                with conn.cursor() as cur:
                    cur.execute(
                        'UPDATE "ew_orders" SET "maps_enriched_at" = %s, "maps_enrich_error" = %s '
                        'WHERE "ew_quote_no" = %s',
                        (err_now, str(e)[:2000], qn),
                    )
                conn.commit()
                enriched += 1
            if delay:
                time.sleep(delay)

    return {"enriched": enriched, "skipped": skipped, "cargo_updated": cargo_updated}


def maps_debug_first_row_db_lines(r0: dict[str, Any] | None) -> str:
    """供 ?debug_maps=1 展示首行数据库中的 Maps 缓存（无在线请求）。"""
    if not r0:
        return "（无订单行）"
    keys = [
        "google_distance_text",
        "google_distance_miles",
        "origin_land_use",
        "destination_land_use",
        "maps_origin_href",
        "maps_dest_href",
        "maps_directions_href",
        "maps_enriched_at",
        "maps_enrich_error",
    ]
    lines = []
    for k in keys:
        lines.append(f"{k}={r0.get(k)!r}")
    lines.append(f"maps_row_complete={maps_row_complete(r0)}")
    lines.append(f"maps_row_needs_attention={maps_row_needs_attention(r0)}")
    return "\n".join(lines)
