"""HTTP API：读 v2 `load` 分页列表；可选对本页未打过 Sheet 行 AI 的行拉表并多线程 Gemini 写回。"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.load_service import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    ROWS_SORT_SCAN_MAX,
    TAB_KEYS,
    fetch_tab_rows,
)
from app.load_tab_ai import ensure_tab_page_row_ai_enrich
from app.settings import get_settings
from app.sheet_sync import _get_v2_db

router = APIRouter(prefix="/api/core", tags=["core"])

_CLEAR_LOAD_CONFIRM = "DELETE_ALL_LOAD"


@router.post("/load/clear-all")
def api_clear_all_load(
    confirm: str = Query(
        ...,
        description=f"必须为 {_CLEAR_LOAD_CONFIRM!r}，防止误删",
    ),
) -> dict[str, Any]:
    """
    清空 SQLite 中 **全部** `load` 行及关联 import 日志（调试壳）。
    同时删除 `load_validation_log`、`load_sync_log` 全表；并重置 `import_lock.initial_load_done`。
    """
    if confirm.strip() != _CLEAR_LOAD_CONFIRM:
        raise HTTPException(
            status_code=400,
            detail=f"confirm 必须为 {_CLEAR_LOAD_CONFIRM!r}",
        )
    settings = get_settings()
    path = settings.db_path.resolve()
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"数据库文件不存在：{path}",
        )
    v2db = _get_v2_db()
    conn = v2db.open_db(path)
    v2db.ensure_schema(conn)
    try:
        n_load = int(conn.execute("SELECT COUNT(*) AS c FROM load").fetchone()["c"])
        conn.execute("DELETE FROM load_validation_log")
        conn.execute("DELETE FROM load_sync_log")
        conn.execute("DELETE FROM load")
        conn.execute("DELETE FROM import_lock WHERE lock_key = 'initial_load_done'")
        conn.commit()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
        n_remain = int(conn.execute("SELECT COUNT(*) AS c FROM load").fetchone()["c"])
        if n_remain != 0:
            raise HTTPException(
                status_code=500,
                detail=f"清空后仍剩 load 行数 {n_remain}，请检查是否有其它进程占用库：{path}",
            )
    finally:
        conn.close()
    return {
        "ok": True,
        "db_path": str(path),
        "deleted_load_rows": n_load,
        "load_remaining": 0,
        "note": "load / load_validation_log / load_sync_log 已清空；import_lock initial_load_done 已删",
    }


@router.get("/load/tab-rows")
def api_load_tab_rows(
    tab: str = Query(..., description="quote | order | complete | cancel"),
    page: int = Query(1, ge=1, description="从 1 开始"),
    page_size: int = Query(
        PAGE_SIZE_DEFAULT,
        ge=1,
        le=PAGE_SIZE_MAX,
        description=f"每页行数，最大 {PAGE_SIZE_MAX}",
    ),
    data_source: str | None = Query(
        None, description="可选：TRIM(data_source) 精确匹配"
    ),
    load_state: str | None = Query(
        None,
        description="仅 tab=order 时有效：waiting | found | transit",
    ),
    ensure_ai: bool = Query(
        False,
        description=(
            "true：对本页未打 AI 时间戳的行多线程 Gemini 补缺（较慢）；"
            "false：只读库分页（翻页应用默认 false）"
        ),
    ),
) -> dict[str, Any]:
    """按 source_tabs 包含指定 tab 键筛选 load 行，分页；排序与 Tab 列表一致（EW 尾号降序）。"""
    t = tab.strip().lower()
    if t not in TAB_KEYS:
        raise HTTPException(status_code=400, detail=f"无效 tab：{tab!r}")
    offset = (page - 1) * page_size
    settings = get_settings()
    rows, total, err = fetch_tab_rows(
        settings.db_path,
        t,
        offset=offset,
        limit=page_size,
        load_state=load_state if t == "order" else None,
        data_source=data_source,
    )
    if err == "invalid_tab":
        raise HTTPException(status_code=400, detail="invalid_tab")
    if err == "invalid_limit":
        raise HTTPException(status_code=400, detail="invalid_limit")
    if err == "invalid_offset":
        raise HTTPException(status_code=400, detail="invalid_offset")
    if err == "too_many_rows":
        raise HTTPException(
            status_code=400,
            detail=(
                f"匹配行数 {total} 超过本接口排序上限 {ROWS_SORT_SCAN_MAX}，"
                "请使用参数 data_source 等缩小范围后再分页"
            ),
        )
    if err == "db_missing":
        raise HTTPException(
            status_code=503,
            detail=f"数据库文件不存在：{settings.db_path}",
        )
    if err == "query_failed":
        raise HTTPException(status_code=500, detail="SQLite 查询失败")

    ensure_meta: dict[str, Any] = {}
    if ensure_ai and rows:
        ensure_meta = ensure_tab_page_row_ai_enrich(tab_key=t, page_rows=rows)
        if ensure_meta.get("ensure_ai_refetch"):
            rows, total, err2 = fetch_tab_rows(
                settings.db_path,
                t,
                offset=offset,
                limit=page_size,
                load_state=load_state if t == "order" else None,
                data_source=data_source,
            )
            if err2 == "db_missing":
                raise HTTPException(
                    status_code=503,
                    detail=f"数据库文件不存在：{settings.db_path}",
                )
            if err2 == "query_failed":
                raise HTTPException(status_code=500, detail="SQLite 查询失败")
            if err2:
                raise HTTPException(status_code=500, detail=str(err2))

    out: dict[str, Any] = {
        "tab": t,
        "db_path": str(settings.db_path),
        "page": page,
        "page_size": page_size,
        "total": total,
        "row_count": len(rows),
        "rows": rows,
    }
    if ensure_meta:
        out["ensure_ai"] = ensure_meta
    return out
