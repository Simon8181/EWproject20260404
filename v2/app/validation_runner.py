from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any

from .address_validate import validate_route
from .party_ai import resolve_party_info
from .settings import load_env
from .db import (
    delete_load_and_validation_logs,
    ensure_schema,
    finish_validation_job,
    now_iso,
    open_db,
    update_validation_job_progress,
)


def _quote_no_sql_candidates(r: dict[str, Any]) -> list[str]:
    """Try DB PK variants (trim / raw) so UPDATE matches imported rows."""
    seen: set[str] = set()
    out: list[str] = []
    raw = r.get("quote_no")
    if raw is not None:
        s = str(raw)
        if s not in seen:
            seen.add(s)
            out.append(s)
        st = s.strip()
        if st and st not in seen:
            seen.add(st)
            out.append(st)
    return out


def run_validation_batch(
    conn: Any,
    rows: list[dict[str, Any]],
    *,
    job_id: str | None,
    log_trigger: str,
) -> None:
    total = len(rows)
    ok_count = 0
    fail_deleted = 0
    ai_retry_count = 0
    ai_recovered_count = 0
    ts = now_iso()
    processed = 0

    def _flush_progress(current_q: str) -> None:
        if not job_id:
            return
        update_validation_job_progress(
            conn,
            job_id,
            processed=processed,
            ok_count=ok_count,
            fail_deleted=fail_deleted,
            ai_retry_count=ai_retry_count,
            ai_recovered_count=ai_recovered_count,
            current_quote_no=current_q,
        )

    for r in rows:
        q_candidates = _quote_no_sql_candidates(r)
        if not q_candidates or not q_candidates[0].strip():
            processed += 1
            _flush_progress("")
            continue
        quote_no_log = q_candidates[0].strip()

        result = validate_route(
            str(r.get("ship_from_raw") or ""),
            str(r.get("ship_to_raw") or ""),
        )
        with conn:
            if result.ok:
                if result.used_ai_retry:
                    ai_retry_count += 1
                    ai_recovered_count += 1
                m_from = (result.maps_origin_formatted or "").strip()
                m_to = (result.maps_dest_formatted or "").strip()
                norm_o = (result.origin_normalized or "").strip()
                norm_d = (result.dest_normalized or "").strip()
                prev_from = str(r.get("ship_from_raw") or "")
                prev_to = str(r.get("ship_to_raw") or "")
                ship_from_out = m_from or norm_o or prev_from
                ship_to_out = m_to or norm_d or prev_to
                shipper_info, consignee_info = resolve_party_info(
                    ship_from_raw=prev_from,
                    ship_to_raw=prev_to,
                    ship_from_out=ship_from_out,
                    ship_to_out=ship_to_out,
                    consignee_contact=str(r.get("consignee_contact") or ""),
                )
                cur_rowcount = 0
                quote_key_used = ""
                for qk in q_candidates:
                    cur = conn.execute(
                        """
                        UPDATE load
                        SET ship_from_raw = ?,
                            ship_to_raw = ?,
                            shipper_info = ?,
                            consignee_info = ?,
                            distance_miles = ?,
                            origin_land_use = ?,
                            dest_land_use = ?,
                            validate_ok = 1,
                            validate_error = '',
                            validated_at = ?,
                            used_ai_retry = ?,
                            ai_confidence = ?,
                            origin_normalized = ?,
                            dest_normalized = ?,
                            ai_notes = ?,
                            updated_at = ?
                        WHERE quote_no = ?
                        """,
                        (
                            ship_from_out,
                            ship_to_out,
                            shipper_info,
                            consignee_info,
                            result.distance_miles,
                            result.origin_land_use,
                            result.dest_land_use,
                            ts,
                            1 if result.used_ai_retry else 0,
                            result.ai_confidence,
                            result.origin_normalized,
                            result.dest_normalized,
                            result.ai_notes,
                            ts,
                            qk,
                        ),
                    )
                    if cur.rowcount == 1:
                        cur_rowcount = 1
                        quote_key_used = qk
                        break
                if cur_rowcount != 1:
                    raise RuntimeError(
                        "地址校验成功但未能更新 load（0 行）："
                        f"quote_no 候选={q_candidates!r}。请确认该行仍在库中且主键一致。"
                    )
                conn.execute(
                    """
                    INSERT INTO load_validation_log(
                        quote_no, run_at, success, distance_miles,
                        origin_land_use, dest_land_use,
                        used_ai_retry, ai_confidence, origin_normalized, dest_normalized, ai_notes,
                        error_message
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, '')
                    """,
                    (
                        quote_key_used,
                        ts,
                        result.distance_miles,
                        result.origin_land_use,
                        result.dest_land_use,
                        1 if result.used_ai_retry else 0,
                        result.ai_confidence,
                        result.origin_normalized,
                        result.dest_normalized,
                        result.ai_notes,
                    ),
                )
                ok_count += 1
            else:
                if result.used_ai_retry:
                    ai_retry_count += 1
                for qk in q_candidates:
                    delete_load_and_validation_logs(conn, qk)
                fail_deleted += 1

        processed += 1
        _flush_progress(quote_no_log)

    with conn:
        conn.execute(
            """
            INSERT INTO load_sync_log(
                run_at, trigger, rows_read, rows_written, rows_skipped, success, error_message
            ) VALUES (?, ?, ?, ?, ?, 1, '')
            """,
            (ts, log_trigger, total, ok_count, fail_deleted),
        )


_start_lock = threading.Lock()


def validation_start_lock() -> threading.Lock:
    return _start_lock


def new_job_id() -> str:
    return str(uuid.uuid4())


def run_validation_job_thread(
    db_path: Path,
    job_id: str,
    rows: list[dict[str, Any]],
    log_trigger: str,
) -> None:
    load_env()
    conn = open_db(db_path)
    try:
        ensure_schema(conn)
        run_validation_batch(conn, rows, job_id=job_id, log_trigger=log_trigger)
        finish_validation_job(conn, job_id, status="done")
    except Exception as e:
        finish_validation_job(conn, job_id, status="error", error_message=str(e))
    finally:
        conn.close()
