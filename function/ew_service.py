"""
EW HTTP 服务：浏览器访问与 `EW_CATALOG.yaml` 中 `/F/read/...` 路由一致的 Sheet 数据。

启动（仓库根目录）：
  uvicorn function.ew_service:app --host 127.0.0.1 --port 8000

示例：
  http://127.0.0.1:8000/  — 主页（目录导航）
  http://127.0.0.1:8000/f/read/quote?fmt=html&limit=50
  http://127.0.0.1:8000/F/read/order?fmt=json
  http://127.0.0.1:8000/api/distance?origin=...&destination=...  — 驾车距离 mi（需 Maps API Key）
  http://127.0.0.1:8000/api/route?origin=...&destination=...  — mi + 起终点地址 types（Distance Matrix + Geocoding）
  http://127.0.0.1:8000/admin?token=...  — API 集成状态（需 EW_ADMIN_TOKEN）
"""

from __future__ import annotations

import html as html_module
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response

from function.admin_api_status import (
    admin_token_configured,
    render_admin_page,
    verify_admin_token,
)
from function.api_config import integration_snapshot
from function.ew_sort import sort_rows_by_ew_quote_no_desc
from function.home_page import render_home_page
from function.maps_distance import fetch_driving_distance, fetch_route_insight
from function.order_view import render_order_page
from function.sheet_sync.catalog import list_catalog_read_routes, resolve_rules_for_sheet
from function.sheet_sync.config import load_mapping
from function.sheet_sync.render_html import html_document, html_table
from function.sheet_sync.rows import read_mapped_rows, read_mapped_sections

load_dotenv()

app = FastAPI(title="EW Sheet Service", version="1.0.0")


@app.get("/", response_model=None)
def home() -> HTMLResponse:
    items = list_catalog_read_routes()
    return HTMLResponse(content=render_home_page(items))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/distance")
def api_driving_distance(
    origin: str = Query(..., min_length=2, description="起点地址（任意可被 Google 解析的文本）"),
    destination: str = Query(
        ...,
        min_length=2,
        description="终点地址",
    ),
) -> JSONResponse:
    """
    Google Distance Matrix：驾车距离（**英里 mi**）与时间。

    需 `GOOGLE_MAPS_API_KEY` + 启用 **Distance Matrix API**。不含地址类型；需要 types 请用 `/api/route`。
    """
    r = fetch_driving_distance(origin, destination)
    body: dict[str, object] = {
        "ok": r.ok,
        "distance_miles": r.distance_miles,
        "distance_km": r.distance_km,
        "distance_text": r.distance_text,
        "duration_seconds": r.duration_seconds,
        "duration_text": r.duration_text,
        "google_status": r.google_status,
        "element_status": r.element_status,
    }
    if r.error_message:
        body["error"] = r.error_message
    return JSONResponse(content=body)


@app.get("/api/route")
def api_route_insight(
    origin: str = Query(..., min_length=2, description="起点"),
    destination: str = Query(..., min_length=2, description="终点"),
) -> JSONResponse:
    """
    同时返回：**驾车距离（mi）** + 起终点 **地址类型**（Geocoding 的 `types` 与 `location_type`）。

    需启用 **Distance Matrix API** 与 **Geocoding API**。
    """
    r = fetch_route_insight(origin, destination)
    body: dict[str, object] = {
        "ok": r.ok,
        "distance_miles": r.distance_miles,
        "distance_km": r.distance_km,
        "distance_text": r.distance_text,
        "duration_seconds": r.duration_seconds,
        "duration_text": r.duration_text,
        "origin_types": list(r.origin_types),
        "destination_types": list(r.destination_types),
        "origin_location_type": r.origin_location_type,
        "destination_location_type": r.destination_location_type,
        "origin_formatted_address": r.origin_formatted,
        "destination_formatted_address": r.destination_formatted,
        "google_distance_status": r.google_distance_status,
        "element_status": r.element_status,
    }
    if r.error_message:
        body["error"] = r.error_message
    return JSONResponse(content=body)


@app.get("/admin", response_model=None)
def admin_ui(
    token: str | None = Query(None, description="Must match EW_ADMIN_TOKEN"),
) -> HTMLResponse:
    """Read-only API / integration status (keys never shown in full)."""
    if not admin_token_configured():
        raise HTTPException(
            status_code=503,
            detail="Admin UI disabled: set EW_ADMIN_TOKEN in config/api.secrets.env",
        )
    if not verify_admin_token(token):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid token. Use /admin?token=YOUR_TOKEN",
        )
    return HTMLResponse(content=render_admin_page())


@app.get("/admin/api-status.json")
def admin_api_status_json(
    token: str | None = Query(None),
) -> JSONResponse:
    """Same data as /admin for scripts."""
    if not admin_token_configured():
        raise HTTPException(status_code=503, detail="Set EW_ADMIN_TOKEN")
    if not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Invalid token")
    return JSONResponse(content={"integrations": integration_snapshot()})


@app.get("/F/read/{name}", response_model=None)
@app.get("/f/read/{name}", response_model=None)
def read_sheet(
    name: str,
    fmt: str = Query(
        "json",
        description="json 或 html",
    ),
    limit: int | None = Query(
        None,
        ge=1,
        description="最多返回行数；省略则返回全部（大表慎用）",
    ),
) -> Response:
    route = f"/F/read/{name}"
    try:
        mapping_path = resolve_rules_for_sheet(route)
        cfg = load_mapping(mapping_path)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    os.environ.setdefault("MAPPING_FILE", str(cfg.mapping_path))

    media = (fmt or "json").strip().lower()
    if media not in ("json", "html"):
        raise HTTPException(
            status_code=400,
            detail="fmt must be json or html",
        )

    if name.casefold() == "order":
        rows = sort_rows_by_ew_quote_no_desc(read_mapped_rows(cfg, limit))
        if media == "json":
            return JSONResponse(content=rows)
        return HTMLResponse(content=render_order_page(rows))

    if media == "json":
        data = read_mapped_rows(cfg, limit)
        return JSONResponse(content=data)

    parts: list[str] = []
    for label, sec_rows in read_mapped_sections(cfg, limit):
        block = html_table(sec_rows)
        if len(cfg.jobs) > 1:
            block = f"<h2>{html_module.escape(label)}</h2>" + block
        parts.append(block)
    if not parts:
        parts.append(html_table([]))
    return HTMLResponse(content=html_document(parts))
