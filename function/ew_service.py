"""
EW HTTP 服务：浏览器访问与 `EW_CATALOG.yaml` 中 `/F/read/...` 路由一致的 Sheet 数据。

启动（仓库根目录）：
  uvicorn function.ew_service:app --host 127.0.0.1 --port 8000

示例：
  http://127.0.0.1:8000/  — 主页（需登录；未登录会跳转 /login）
  http://127.0.0.1:8000/f/read/quote?fmt=html&limit=50  — 需登录，或 ?token=EW_ADMIN_TOKEN
  http://127.0.0.1:8000/F/read/order?fmt=json  — 同上；分页 `page`（默认 1）、`per_page`（默认 20）；`limit` 兼容作每页条数
  http://127.0.0.1:8000/f/read/order?fmt=html&token=EW_ADMIN_TOKEN  — 书签（与 /admin 同令牌）；或先 /login 再打开
  http://127.0.0.1:8000/login  — 用户名/密码（config/ew_users.yaml），角色：开发者 / Boss / Broker
  http://127.0.0.1:8000/register  — 自助注册（首个账号=开发者；或 EW_SELF_REGISTER=1）
  http://127.0.0.1:8000/users  — 用户管理（仅开发者）
  http://127.0.0.1:8000/api/distance?origin=...&destination=...  — 驾车距离 mi（需 Maps API Key）
  http://127.0.0.1:8000/api/route?origin=...&destination=...  — mi + 起终点地址 types（Distance Matrix + Geocoding）
  http://127.0.0.1:8000/docs/ew-usage-guide-v1.pdf  — 使用守则（第一版，PDF，需登录）
  http://127.0.0.1:8000/config  — 配置页（路径 / 集成脱敏预览）
  http://127.0.0.1:8000/admin?token=...  — API 集成状态（需 EW_ADMIN_TOKEN）
"""

from __future__ import annotations

import html as html_module
import os

from urllib.parse import parse_qsl, quote, urlencode

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from function.admin_api_status import (
    admin_token_configured,
    render_admin_page,
    verify_admin_token,
)
from function.api_config import integration_snapshot, reload_api_env, save_order_google_miles_max_ui
from function.auth_roles import (
    can_edit_config,
    can_manage_users,
    can_sync_orders,
    can_view_config,
    can_view_integration,
    nav_user_caption,
)
from function.auth_users_store import (
    delete_user,
    list_users,
    register_new_user,
    set_password,
    set_role,
    user_count,
    verify_password,
)
from function.config_page import render_config_page
from function.ew_sort import sort_order_rows_for_display
from function.home_page import render_home_page
from function.login_page import render_login_page
from function.maps_distance import fetch_driving_distance, fetch_route_insight
from function.order_maps_enrich import batch_enrich_all_ew_orders_maps
from function.order_view import (
    ORDER_FORMAT_DATA_SKILL_LABEL,
    render_order_page,
    render_order_pagination_nav,
    render_peidan_page,
)
from function.sheet_sync.catalog import list_catalog_read_routes, resolve_rules_for_sheet
from function.sheet_sync.config import load_mapping
from function.sheet_sync.db_orders import load_ew_orders_from_db
from function.sheet_sync.render_html import html_document, html_table
from function.sheet_sync.rows import read_mapped_rows, read_mapped_sections
from function.sheet_sync.sync import sync_config_to_db
from function.session_auth import (
    ADMIN_SESSION_COOKIE,
    SESSION_MAX_AGE_SEC,
    issue_session_value,
    read_session,
    safe_next_path,
    signing_key_configured,
)
from function.register_page import render_register_page
from function.register_policy import (
    registration_allowed,
    registration_code_configured,
    verify_registration_code,
)
from function.usage_guide_pdf import build_usage_guide_v1_pdf_bytes
from function.users_page import render_users_page

# Env is loaded once in function.api_config (repo-root .env + config/*.env), not from CWD.

app = FastAPI(title="EW Sheet Service", version="1.0.0")


def _query_token_ok(request: Request) -> bool:
    """URL ?token= 与 EW_ADMIN_TOKEN 一致（/admin 书签、与 /f/read 内逻辑一致）。"""
    t = (request.query_params.get("token") or "").strip()
    return bool(admin_token_configured() and t and verify_admin_token(t))


@app.middleware("http")
async def require_login_middleware(request: Request, call_next):
    """未登录仅允许：/health、登录注册退出、/f/read/*（内含会话或 token 校验）、/admin*?token=。"""
    path = request.url.path
    if path == "/health":
        return await call_next(request)
    if path in ("/login", "/register", "/logout"):
        return await call_next(request)
    if path.lower().startswith("/f/read/"):
        return await call_next(request)
    if path.startswith("/admin") and _query_token_ok(request):
        return await call_next(request)
    if read_session(request):
        return await call_next(request)
    if path.lower().startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "需要登录"})
    next_q = path + (("?" + request.url.query) if request.url.query else "")
    return RedirectResponse(
        url="/login?next=" + quote(next_q, safe=""),
        status_code=303,
    )


def _session_nav(request: Request) -> tuple[str | None, str | None]:
    s = read_session(request)
    if not s:
        return None, None
    cap = nav_user_caption(s["username"], s["role"])
    return cap, s["role"]


def _authorized_for_read_data(request: Request, token: str | None) -> bool:
    """已登录会话，或 ?token= 与 EW_ADMIN_TOKEN 一致（书签/脚本）。"""
    if read_session(request):
        return True
    t = (token or "").strip()
    return bool(admin_token_configured() and t and verify_admin_token(t))


def _login_next_path_strip_token(request: Request) -> str:
    """用于 /login?next=，去掉 token 避免把管理令牌写进登录页 URL。"""
    path = request.url.path
    q = [
        (k, v)
        for k, v in parse_qsl(request.url.query, keep_blank_values=True)
        if k.casefold() != "token"
    ]
    return path + ("?" + urlencode(q) if q else "")


def _order_page_redirect(
    *,
    sync_err: str | None = None,
    synced: int | None = None,
    n: int | None = None,
    preserve_token: str | None = None,
    maps_enriched: int | None = None,
    maps_skipped: int | None = None,
    maps_cargo_updated: int | None = None,
    maps_err: str | None = None,
) -> RedirectResponse:
    """HTML order view; optional token keeps one-click sync / 格式化数据 补全书签。"""
    q: list[str] = ["fmt=html"]
    if sync_err is not None:
        q.append("sync_err=" + quote(str(sync_err), safe=""))
    if synced is not None:
        q.append(f"synced={int(synced)}")
    if n is not None:
        q.append(f"n={int(n)}")
    if maps_enriched is not None:
        q.append(f"maps_enriched={int(maps_enriched)}")
    if maps_skipped is not None:
        q.append(f"maps_skipped={int(maps_skipped)}")
    if maps_cargo_updated is not None:
        q.append(f"maps_cargo_updated={int(maps_cargo_updated)}")
    if maps_err is not None:
        q.append("maps_err=" + quote(str(maps_err), safe=""))
    if preserve_token:
        q.append("token=" + quote(preserve_token, safe=""))
    return RedirectResponse(url="/f/read/order?" + "&".join(q), status_code=303)


def _flat_query_params(request: Request) -> dict[str, str]:
    """Single-value map of current query string (last wins on duplicates)."""
    out: dict[str, str] = {}
    for k, v in request.query_params.multi_items():
        out[k] = v
    return out


@app.get("/", response_model=None)
def home(request: Request) -> HTMLResponse:
    items = list_catalog_read_routes()
    cap, role = _session_nav(request)
    return HTMLResponse(content=render_home_page(items, session_user=cap, role=role))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/docs/ew-usage-guide-v1.pdf", response_model=None)
def usage_guide_v1_pdf() -> Response:
    """第一版使用守则（PDF，中文）。"""
    data = build_usage_guide_v1_pdf_bytes()
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="EW_使用守则_v1.pdf"',
        },
    )


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
    同时返回：**驾车距离（mi）** + 起终点 **地址类型**（Geocoding 的 `types` 与 `location_type`），
    以及 **land_use**（由 types 映射的英文：warehouse / commercial / residential / unknown）。

    需启用 **Distance Matrix API** 与 **Geocoding API**；若 `ORDER_PLACES_LAND_USE=1` 还需 **Places API**（Place Details）。
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
        "origin_land_use": r.origin_land_use,
        "destination_land_use": r.destination_land_use,
        "origin_formatted_address": r.origin_formatted,
        "destination_formatted_address": r.destination_formatted,
        "origin_postal_code": r.origin_postal_code,
        "destination_postal_code": r.destination_postal_code,
        "origin_city": r.origin_city,
        "origin_state": r.origin_state,
        "destination_city": r.destination_city,
        "destination_state": r.destination_state,
        "google_distance_status": r.google_distance_status,
        "element_status": r.element_status,
        "origin_geocode_status": r.origin_geocode_status,
        "destination_geocode_status": r.destination_geocode_status,
    }
    if r.error_message:
        body["error"] = r.error_message
    return JSONResponse(content=body)


@app.get("/config", response_model=None)
def config_ui(
    request: Request,
    saved: bool = Query(False, description="保存成功提示"),
    err: str | None = Query(None, description="错误信息"),
) -> HTMLResponse:
    """配置页：开发者可保存；Boss 只读；Broker 不可访问。"""
    s = read_session(request)
    if not s:
        return RedirectResponse(
            url="/login?next=" + quote("/config", safe=""),
            status_code=303,
        )
    role = s["role"]
    if not can_view_config(role):
        return RedirectResponse("/", status_code=303)
    cap = nav_user_caption(s["username"], role)
    read_only = not can_edit_config(role)
    return HTMLResponse(
        content=render_config_page(
            saved=bool(saved),
            error=err,
            can_save=can_edit_config(role) and admin_token_configured(),
            session_user=cap,
            role=role,
            read_only=read_only,
        )
    )


@app.post("/config/save", response_model=None)
def config_save(
    request: Request,
    token: str = Form(""),
    order_google_miles_max: str = Form(...),
) -> RedirectResponse:
    """仅开发者可保存（或带 EW_ADMIN_TOKEN 的脚本）。"""
    s = read_session(request)
    t = (token or "").strip()
    tok_ok = bool(admin_token_configured() and t and verify_admin_token(t))
    if tok_ok:
        pass
    elif s and can_edit_config(s["role"]):
        pass
    else:
        return RedirectResponse(
            url="/config?err=" + quote("需要开发者登录或有效 EW_ADMIN_TOKEN"),
            status_code=303,
        )
    if not admin_token_configured():
        return RedirectResponse(
            url="/config?err=" + quote("未配置 EW_ADMIN_TOKEN，无法写入 ew_settings"),
            status_code=303,
        )
    try:
        n = int(str(order_google_miles_max).strip())
    except ValueError:
        return RedirectResponse(
            url="/config?err=" + quote("ORDER_GOOGLE_MILES_MAX 必须是整数"),
            status_code=303,
        )
    if n < 1 or n > 9999:
        return RedirectResponse(
            url="/config?err=" + quote("ORDER_GOOGLE_MILES_MAX 需在 1～9999 之间"),
            status_code=303,
        )
    save_order_google_miles_max_ui(n)
    return RedirectResponse(url="/config?saved=1", status_code=303)


@app.get("/login", response_model=None)
def login_get(
    request: Request,
    next: str = Query("/f/read/order?fmt=html", description="登录成功后的相对路径"),
    err: str | None = Query(None, description="错误信息"),
) -> Response:
    np = safe_next_path(next)
    if read_session(request):
        return RedirectResponse(np, status_code=303)
    hint: str | None = None
    if not signing_key_configured():
        hint = (
            "未配置会话签名密钥：请在 <code>config/api.secrets.env</code> 设置 "
            "<code>EW_SESSION_SECRET</code>（推荐）或 <code>EW_ADMIN_TOKEN</code>，然后重启 uvicorn。"
        )
    elif user_count() == 0:
        hint = (
            "尚无用户：在仓库根目录执行 "
            "<code>python -m function.create_user 登录名 developer</code> 创建首个账号。"
        )
    return HTMLResponse(
        content=render_login_page(
            next_path=np,
            error=err,
            can_login=True,
            session_user=None,
            setup_hint=hint,
        )
    )


@app.post("/login", response_model=None)
def login_post(
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/f/read/order?fmt=html"),
) -> RedirectResponse:
    np = safe_next_path(next)
    if not signing_key_configured():
        return RedirectResponse(
            url="/login?err=" + quote("未配置 EW_SESSION_SECRET 或 EW_ADMIN_TOKEN") + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    role = verify_password(username, password)
    if not role:
        return RedirectResponse(
            url="/login?err=" + quote("用户名或密码错误") + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    val = issue_session_value(username, role)
    if not val:
        return RedirectResponse(
            url="/login?err=" + quote("无法签发会话") + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    resp = RedirectResponse(np, status_code=303)
    resp.set_cookie(
        ADMIN_SESSION_COOKIE,
        val,
        max_age=SESSION_MAX_AGE_SEC,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


@app.get("/register", response_model=None)
def register_get(
    request: Request,
    next: str = Query("/f/read/order?fmt=html", description="注册成功后跳转"),
    err: str | None = Query(None, description="错误信息"),
) -> Response:
    reload_api_env()
    if read_session(request):
        return RedirectResponse(safe_next_path(next), status_code=303)
    np = safe_next_path(next)
    allowed = registration_allowed()
    signing_ok = signing_key_configured()
    show_code = registration_code_configured()
    closed_message: str | None = None
    if not allowed:
        closed_message = (
            "已有账号且未开启自助注册。请在仓库根目录 .env 或 config/api.secrets.env 中设置 "
            "EW_SELF_REGISTER=1，保存后重启 uvicorn；或由开发者登录后在「用户」中添加账号。"
        )
    return HTMLResponse(
        content=render_register_page(
            next_path=np,
            error=err,
            allowed=allowed,
            signing_ok=signing_ok,
            show_code_field=show_code,
            closed_message=closed_message,
            first_user=user_count() == 0,
        )
    )


@app.post("/register", response_model=None)
def register_post(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    password2: str = Form(""),
    next: str = Form("/f/read/order?fmt=html"),
    registration_code: str = Form(""),
    role: str = Form(""),
) -> RedirectResponse:
    reload_api_env()
    np = safe_next_path(next)
    if read_session(request):
        return RedirectResponse(np, status_code=303)
    if not registration_allowed():
        return RedirectResponse(
            "/register?err=" + quote("当前不允许注册") + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    if not signing_key_configured():
        return RedirectResponse(
            "/register?err=" + quote("未配置 EW_SESSION_SECRET 或 EW_ADMIN_TOKEN") + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    if registration_code_configured() and not verify_registration_code(registration_code):
        return RedirectResponse(
            "/register?err=" + quote("注册码错误") + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    if (password or "") != (password2 or ""):
        return RedirectResponse(
            "/register?err=" + quote("两次密码不一致") + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    try:
        assigned = register_new_user(
            (username or "").strip(),
            password,
            requested_role=(role or "").strip() or None,
        )
    except ValueError as e:
        return RedirectResponse(
            "/register?err=" + quote(str(e)) + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    un = (username or "").strip()
    val = issue_session_value(un, assigned)
    if not val:
        return RedirectResponse(
            "/register?err=" + quote("无法签发会话") + "&next=" + quote(np, safe=""),
            status_code=303,
        )
    resp = RedirectResponse(np, status_code=303)
    resp.set_cookie(
        ADMIN_SESSION_COOKIE,
        val,
        max_age=SESSION_MAX_AGE_SEC,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp


@app.get("/logout", response_model=None)
def logout_get() -> RedirectResponse:
    r = RedirectResponse("/", status_code=303)
    r.delete_cookie(ADMIN_SESSION_COOKIE, path="/")
    return r


@app.get("/users", response_model=None)
def users_manage_get(
    request: Request,
    ok: int | None = Query(None),
    err: str | None = Query(None),
) -> Response:
    s = read_session(request)
    if not s or not can_manage_users(s["role"]):
        return RedirectResponse(
            url="/login?next=" + quote("/users", safe=""),
            status_code=303,
        )
    rows = list_users()
    cap = nav_user_caption(s["username"], s["role"])
    flash_ok = "已保存。" if ok == 1 else None
    return HTMLResponse(
        content=render_users_page(
            rows,
            session_caption=cap,
            role=s["role"],
            flash_ok=flash_ok,
            flash_err=err,
        )
    )


@app.post("/users/add", response_model=None)
def users_add(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    role: str = Form("broker"),
) -> RedirectResponse:
    s = read_session(request)
    if not s or not can_manage_users(s["role"]):
        return RedirectResponse("/login?next=" + quote("/users", safe=""), status_code=303)
    try:
        set_password(username, password, role)
    except ValueError as e:
        return RedirectResponse("/users?err=" + quote(str(e)), status_code=303)
    return RedirectResponse("/users?ok=1", status_code=303)


@app.post("/users/delete", response_model=None)
def users_delete_post(
    request: Request,
    username: str = Form(""),
) -> RedirectResponse:
    s = read_session(request)
    if not s or not can_manage_users(s["role"]):
        return RedirectResponse("/login?next=" + quote("/users", safe=""), status_code=303)
    if username.strip() == s["username"]:
        return RedirectResponse("/users?err=" + quote("不能删除当前登录用户"), status_code=303)
    if not delete_user(username):
        return RedirectResponse("/users?err=" + quote("用户不存在"), status_code=303)
    return RedirectResponse("/users?ok=1", status_code=303)


@app.post("/users/role", response_model=None)
def users_role_post(
    request: Request,
    username: str = Form(""),
    role: str = Form(""),
) -> RedirectResponse:
    s = read_session(request)
    if not s or not can_manage_users(s["role"]):
        return RedirectResponse("/login?next=" + quote("/users", safe=""), status_code=303)
    try:
        set_role(username, role)
    except (ValueError, KeyError) as e:
        return RedirectResponse("/users?err=" + quote(str(e)), status_code=303)
    return RedirectResponse("/users?ok=1", status_code=303)


@app.get("/admin", response_model=None)
def admin_ui(
    request: Request,
    token: str | None = Query(None, description="Must match EW_ADMIN_TOKEN"),
) -> HTMLResponse:
    """Read-only API / integration status。开发者 / Boss：已登录会话；或 ?token= EW_ADMIN_TOKEN。"""
    s = read_session(request)
    if s and can_view_integration(s["role"]):
        return HTMLResponse(content=render_admin_page())
    if not admin_token_configured():
        raise HTTPException(
            status_code=503,
            detail="Set EW_ADMIN_TOKEN or log in as developer/boss",
        )
    if verify_admin_token(token):
        return HTMLResponse(content=render_admin_page())
    raise HTTPException(
        status_code=401,
        detail="Log in (developer/boss) or use /admin?token=EW_ADMIN_TOKEN",
    )


@app.get("/admin/api-status.json")
def admin_api_status_json(
    request: Request,
    token: str | None = Query(None),
) -> JSONResponse:
    """Same data as /admin for scripts."""
    s = read_session(request)
    if s and can_view_integration(s["role"]):
        return JSONResponse(content={"integrations": integration_snapshot()})
    if not admin_token_configured():
        raise HTTPException(status_code=503, detail="Set EW_ADMIN_TOKEN")
    if verify_admin_token(token):
        return JSONResponse(content={"integrations": integration_snapshot()})
    raise HTTPException(status_code=401, detail="Invalid token or session")


@app.post("/F/read/order/sync", response_model=None)
@app.post("/f/read/order/sync", response_model=None)
def post_order_sheet_sync(request: Request, token: str = Form("")) -> RedirectResponse:
    """从 Google Sheet 同步至 `ew_quote_no`。需 EW_ADMIN_TOKEN 或已登录为 developer（Boss/Broker 会话不可）。"""
    t = (token or "").strip()
    tok_ok = bool(admin_token_configured() and t and verify_admin_token(t))
    s = read_session(request)
    sess_ok = bool(s and can_sync_orders(s["role"]))
    if not (tok_ok or sess_ok):
        return _order_page_redirect(sync_err="请先登录，或在表单中提供有效 EW_ADMIN_TOKEN")
    preserve = t if tok_ok else None
    try:
        mapping_path = resolve_rules_for_sheet("/F/read/order")
        cfg = load_mapping(mapping_path)
        counts = sync_config_to_db(cfg, set_synced_at=True)
        n = int(sum(counts.values()))
        return _order_page_redirect(synced=1, n=n, preserve_token=preserve)
    except FileNotFoundError as e:
        return _order_page_redirect(sync_err=str(e), preserve_token=preserve)
    except Exception as e:
        return _order_page_redirect(sync_err=str(e), preserve_token=preserve)


@app.post("/F/read/order/google-maps", response_model=None)
@app.post("/f/read/order/google-maps", response_model=None)
def post_order_google_maps(request: Request, token: str = Form("")) -> RedirectResponse:
    """对 `ew_orders` 全表补全（格式化数据）：规范化邮编、驾车距离、地址类型、标准地址与地图链接；权限同 Sheet 同步。"""
    t = (token or "").strip()
    tok_ok = bool(admin_token_configured() and t and verify_admin_token(t))
    s = read_session(request)
    sess_ok = bool(s and can_sync_orders(s["role"]))
    if not (tok_ok or sess_ok):
        return _order_page_redirect(maps_err="请先登录，或在表单中提供有效 EW_ADMIN_TOKEN")
    preserve = t if tok_ok else None
    try:
        stats = batch_enrich_all_ew_orders_maps()
        return _order_page_redirect(
            maps_enriched=int(stats["enriched"]),
            maps_skipped=int(stats["skipped"]),
            maps_cargo_updated=int(stats.get("cargo_updated", 0)),
            preserve_token=preserve,
        )
    except Exception as e:
        return _order_page_redirect(maps_err=str(e), preserve_token=preserve)


@app.get("/F/read/order/peidan", response_model=None)
@app.get("/f/read/order/peidan", response_model=None)
def read_order_peidan(
    request: Request,
    admin_bookmark_token: str | None = Query(
        None,
        alias="token",
        description="与下单页相同：EW_ADMIN_TOKEN 书签",
    ),
) -> Response:
    """配单技能页：与 /f/read/order 相同鉴权（会话或 ?token=）。"""
    query_token = (admin_bookmark_token or "").strip()
    if not _authorized_for_read_data(request, query_token):
        return RedirectResponse(
            url="/login?next=" + quote(_login_next_path_strip_token(request), safe=""),
            status_code=303,
        )
    cap, nav_role = _session_nav(request)
    tok_ok = bool(admin_token_configured() and query_token and verify_admin_token(query_token))
    return HTMLResponse(
        content=render_peidan_page(
            session_user=cap,
            role=nav_role,
            back_token=query_token if tok_ok else None,
        )
    )


@app.get("/F/read/{name}", response_model=None)
@app.get("/f/read/{name}", response_model=None)
def read_sheet(
    name: str,
    request: Request,
    fmt: str = Query(
        "json",
        description="json 或 html",
    ),
    limit: int | None = Query(
        None,
        ge=1,
        description="非 order：最多返回行数。order：兼容旧参数，作为每页条数（等同 per_page）",
    ),
    page: int = Query(1, ge=1, description="order：页码，从 1 起"),
    per_page: int = Query(20, ge=1, le=200, description="order：每页条数，默认 20"),
    debug_maps: bool = Query(
        False,
        description="订单 HTML：显示 Maps（距离/地址类型）调用条件与首行 API 状态",
    ),
    sync_err: str | None = Query(
        None,
        description="订单页：同步错误提示（URL 参数，仅 HTML 使用）",
    ),
    synced: int | None = Query(
        None,
        description="订单页：1 表示刚完成 Sheet→DB 同步",
    ),
    sync_n: int | None = Query(
        None,
        alias="n",
        description="订单页：最近一次同步 upsert 行数",
    ),
    maps_enriched: int | None = Query(
        None,
        description="订单页：格式化数据（规范化邮编等）补全发起请求的行数",
    ),
    maps_skipped: int | None = Query(
        None,
        description="订单页：补全时跳过（已完整或无地址）的行数",
    ),
    maps_cargo_updated: int | None = Query(
        None,
        description="订单页：本次写入货物密度 Ft 与 NMFC Class 的行数",
    ),
    maps_err: str | None = Query(
        None,
        description="订单页：格式化数据补全错误",
    ),
    admin_bookmark_token: str | None = Query(
        None,
        alias="token",
        description="与 /admin 相同：EW_ADMIN_TOKEN，用于下单页一键刷新（书签）",
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

    query_token = (admin_bookmark_token or "").strip()
    if not _authorized_for_read_data(request, query_token):
        if media == "json":
            raise HTTPException(
                status_code=401,
                detail="需要登录（Cookie）或在 URL 中提供 ?token=（与 EW_ADMIN_TOKEN 一致）",
            )
        return RedirectResponse(
            url="/login?next=" + quote(_login_next_path_strip_token(request), safe=""),
            status_code=303,
        )

    if name.casefold() == "order":
        db_fallback_warning: str | None = None
        try:
            db_rows = load_ew_orders_from_db()
        except Exception as e:
            # 与改库前一致：库不可用则仍从 Sheet 拉列表，避免整页 503
            db_fallback_warning = (
                f"数据库不可用（{e}）。请配置 DATABASE_URL、启动 Postgres，并执行 db/schema_order.sql 创建 ew_orders；"
                "就绪后列表将自动从库读取，「从 Sheet 刷新」才会写入库。"
            )
            db_rows = read_mapped_rows(cfg, None)

        rows = sort_order_rows_for_display(db_rows)
        total = len(rows)
        eff_per = min(int(limit), 200) if limit is not None else per_page
        total_pages = max(1, (total + eff_per - 1) // eff_per) if total else 1
        page_i = min(max(1, page), total_pages)
        start = (page_i - 1) * eff_per
        rows_page = rows[start : start + eff_per]

        if media == "json":
            headers: dict[str, str] = {}
            if db_fallback_warning:
                headers["X-EW-Order-Source"] = "sheet-fallback"
                headers["X-EW-Order-Warning"] = db_fallback_warning[:800]
            body: dict[str, object] = {
                "items": rows_page,
                "total": total,
                "page": page_i,
                "per_page": eff_per,
                "total_pages": total_pages,
            }
            return JSONResponse(content=body, headers=headers)

        sync_flash_ok: str | None = None
        if synced == 1:
            sync_flash_ok = (
                f"已从 Google Sheet 同步至数据库（upsert 约 {sync_n} 行）。"
                if sync_n is not None
                else "已从 Google Sheet 同步至数据库。"
            )

        maps_flash_ok: str | None = None
        maps_flash_err: str | None = maps_err
        if maps_enriched is not None:
            sk = int(maps_skipped) if maps_skipped is not None else 0
            en = int(maps_enriched)
            cargo_n = (
                int(maps_cargo_updated) if maps_cargo_updated is not None else None
            )
            cargo_line = ""
            if cargo_n is not None and cargo_n > 0:
                cargo_line = (
                    f"已根据 L/M/N 与重量写入货物密度（Ft）与等级（Class）{cargo_n} 条。"
                )
            if en == 0 and sk == 0:
                maps_flash_ok = (
                    (cargo_line + " " if cargo_line else "")
                    + f"{ORDER_FORMAT_DATA_SKILL_LABEL}：无订单行可处理。"
                )
            elif en == 0 and sk > 0:
                maps_flash_ok = (
                    (cargo_line + " " if cargo_line else "")
                    + f"{ORDER_FORMAT_DATA_SKILL_LABEL}：本次未调用 Google API（{sk} 条已补全或缺起/终点），页面无新 Maps 数据属正常。"
                    + (
                        " 若要强制全表重算，请设 EW_ORDER_MAPS_FORCE_ENRICH=1 并重启服务后再点。"
                        if not cargo_line
                        else ""
                    )
                )
            else:
                maps_flash_ok = (
                    (cargo_line + " " if cargo_line else "")
                    + f"{ORDER_FORMAT_DATA_SKILL_LABEL}：已对 {en} 条发起 API 并写库"
                    + (f"（跳过 {sk} 条：已完整或无起终点）。" if maps_skipped is not None else "。")
                )

        tok = query_token
        tok_ok = bool(admin_token_configured() and tok and verify_admin_token(tok))
        s = read_session(request)
        role = s["role"] if s else None
        session_ok = bool(s and can_sync_orders(role))
        order_sync_via_session = bool(
            not db_fallback_warning
            and session_ok
            and not tok_ok,
        )
        show_sync = bool(
            not db_fallback_warning
            and (tok_ok or session_ok),
        )
        cap, nav_role = _session_nav(request)

        pg_html = ""
        if total > 0:
            pg_html = render_order_pagination_nav(
                page=page_i,
                per_page=eff_per,
                total=total,
                preserved_query=_flat_query_params(request),
            )

        return HTMLResponse(
            content=render_order_page(
                rows_page,
                debug_maps=debug_maps,
                sync_flash_err=sync_err,
                sync_flash_ok=sync_flash_ok,
                maps_flash_ok=maps_flash_ok,
                maps_flash_err=maps_flash_err,
                show_sync_form=show_sync,
                show_maps_enrich_form=show_sync,
                db_fallback_warning=db_fallback_warning,
                order_sync_prefilled_token=tok if tok_ok else None,
                order_sync_via_session=order_sync_via_session,
                session_user=cap,
                role=nav_role,
                pagination_html=pg_html,
            )
        )

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
