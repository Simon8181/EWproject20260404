"""Gemini：按 ai_sheet_rules.yaml 对 Sheet 行做结构化字段补缺（合并路径批量调用）。"""

from __future__ import annotations

import json
import os
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import certifi

from app.settings import load_env
from app.sheet_refresh import load_ai_sheet_rules

_GEMINI_URL_TMPL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

# 与 merge 写库一致：模型不得改主键/状态/来源
_EXTRA_FORBIDDEN = frozenset({"quote_no", "status", "source_tabs"})


def v3_sheet_row_ai_enabled() -> bool:
    load_env()
    v = (os.environ.get("V3_SHEET_ROW_AI_ENABLED") or "0").strip().lower()
    return v in ("1", "true", "yes", "on")


def gemini_api_key_for_rules(rules: dict[str, Any]) -> str:
    load_env()
    ai_cfg = rules.get("ai") or {}
    env_key = str(ai_cfg.get("env_key") or "GEMINI_API_KEY").strip() or "GEMINI_API_KEY"
    return (os.environ.get(env_key) or "").strip()


def ai_batch_max_rows(rules: dict[str, Any]) -> int:
    rc = (rules.get("ai") or {}).get("refresh_context") or {}
    v = rc.get("max_changed_rows_per_call")
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 50
    return max(1, min(n, 100))


def ai_parallel_batch_workers(rules: dict[str, Any]) -> int:
    """并发调用 Gemini 的批次数上限（每批至多 ai_batch_max_rows 行）。"""
    rc = (rules.get("ai") or {}).get("refresh_context") or {}
    v = rc.get("parallel_batch_workers")
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 4
    return max(1, min(n, 32))


def build_ai_allowlist(rules: dict[str, Any]) -> frozenset[str]:
    tbl = rules.get("table_load") or {}
    forbidden: set[str] = set()
    for x in tbl.get("forbidden_output") or []:
        forbidden.add(str(x).strip())
    forbidden |= _EXTRA_FORBIDDEN
    names: set[str] = set()
    for cat in tbl.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        for f in cat.get("fields") or []:
            if isinstance(f, dict):
                nm = str(f.get("name") or "").strip()
                if nm:
                    names.add(nm)
    return frozenset(names - forbidden)


def _categories_field_summary(rules: dict[str, Any]) -> str:
    lines: list[str] = []
    tbl = rules.get("table_load") or {}
    for cat in tbl.get("categories") or []:
        if not isinstance(cat, dict):
            continue
        cz = str(cat.get("category_zh") or cat.get("id") or "")
        for f in cat.get("fields") or []:
            if not isinstance(f, dict):
                continue
            nm = str(f.get("name") or "").strip()
            if not nm or nm in _EXTRA_FORBIDDEN:
                continue
            dz = str(f.get("desc_zh") or "")
            lines.append(f"  - {nm}: {dz}" if dz else f"  - {nm}")
    return "\n".join(lines[:80])


def _http_post_json(url: str, body: dict[str, Any]) -> dict[str, Any] | str:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "EW-v3-sheet-row-ai/1.0",
        },
        method="POST",
    )
    try:
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
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


def enrich_generation_config(rules: dict[str, Any]) -> dict[str, Any]:
    """供调试端点展示的 generationConfig（与请求体一致）。"""
    return _generation_config(rules)


def _generation_config(rules: dict[str, Any]) -> dict[str, Any]:
    ai_cfg = rules.get("ai") or {}
    gen = ai_cfg.get("generation") or {}
    cfg: dict[str, Any] = {}
    t = gen.get("temperature")
    if t is not None:
        try:
            cfg["temperature"] = float(t)
        except (TypeError, ValueError):
            cfg["temperature"] = 0.1
    else:
        cfg["temperature"] = 0.1
    mime = str(gen.get("response_mime_type") or "application/json").strip()
    cfg["responseMimeType"] = mime
    return cfg


def _extract_response_text(raw: dict[str, Any]) -> str:
    candidates = raw.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return ""
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    if not isinstance(parts, list) or not parts:
        return ""
    return str((parts[0] or {}).get("text") or "").strip()


def _sanitize_delta(
    obj: Any, allowlist: frozenset[str]
) -> dict[str, str]:
    if not isinstance(obj, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in obj.items():
        sk = str(k).strip()
        if sk not in allowlist:
            continue
        sv = "" if v is None else str(v).strip()
        if sv:
            out[sk] = sv
    return out


def sanitize_enrich_delta(obj: Any, rules: dict[str, Any]) -> dict[str, str]:
    return _sanitize_delta(obj, build_ai_allowlist(rules))


def build_payload_rows_from_jobs(
    jobs: list[tuple[dict[str, Any], list[Any], str, dict[str, str]]],
    rules: dict[str, Any],
) -> list[dict[str, Any]]:
    allowlist = build_ai_allowlist(rules)
    deterministic_keys = sorted(allowlist)
    payload_rows: list[dict[str, Any]] = []
    for load, header_row, tab_key, cells in jobs:
        det = {k: load.get(k, "") for k in deterministic_keys}
        payload_rows.append(
            {
                "quote_no": str(load.get("quote_no") or ""),
                "tab_key": tab_key,
                "header_row": list(header_row),
                "cells": dict(cells),
                "deterministic": det,
            }
        )
    return payload_rows


def build_enrich_prompt(rules: dict[str, Any], payload_rows: list[dict[str, Any]]) -> str:
    instructions = str((rules.get("ai") or {}).get("instructions") or "").strip()
    tbl = rules.get("table_load") or {}
    desc = str(tbl.get("description") or "").strip()
    allowlist = build_ai_allowlist(rules)
    keys_sorted = sorted(allowlist)
    field_summary = _categories_field_summary(rules)
    return (
        f"{instructions}\n\n"
        f"【table_load 说明】\n{desc}\n\n"
        "【可输出的 load 字段（仅使用这些 name 作为 JSON 键；禁止 output quote_no/status/source_tabs）】\n"
        f"{field_summary}\n\n"
        f"【允许键名集合】\n{json.dumps(keys_sorted, ensure_ascii=False)}\n\n"
        "【任务】对下列 rows 逐一结合 header_row + cells 与 deterministic 已有值，输出**长度相同**的 JSON 数组。"
        " 每个元素为对象：只包含你能从格子里**明确**推断出的键；不要编造；无需补充则用 {}。"
        " 数组顺序必须与 rows 顺序一致。\n\n"
        f"rows = {json.dumps(payload_rows, ensure_ascii=False)}\n"
    )


def run_enrich_generate(
    rules: dict[str, Any], prompt: str
) -> tuple[dict[str, Any] | str, str]:
    """
    发起一次 generateContent，不改变 load。
    返回 (成功时为 API JSON dict，失败时为错误字符串, 模型文本或空字符串)。
    """
    key = gemini_api_key_for_rules(rules)
    if not key:
        return "MISSING_GEMINI_API_KEY", ""
    ai_cfg = rules.get("ai") or {}
    model = str(ai_cfg.get("model") or "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    url = _GEMINI_URL_TMPL.format(
        model=urllib.parse.quote(model, safe=""),
        key=urllib.parse.quote(key, safe=""),
    )
    body: dict[str, Any] = {
        "generationConfig": _generation_config(rules),
        "contents": [{"parts": [{"text": prompt}]}],
    }
    raw = _http_post_json(url, body)
    if isinstance(raw, str):
        return raw, ""
    text = _extract_response_text(raw)
    return raw, text


def apply_ai_delta_to_load(
    load: dict[str, Any],
    delta: dict[str, str],
    *,
    overwrite: bool,
) -> None:
    for k, sv in delta.items():
        if overwrite:
            load[k] = sv
        else:
            cur = load.get(k)
            if cur is None or str(cur).strip() == "":
                load[k] = sv


@dataclass
class AiEnrichRunStats:
    calls: int = 0
    rows: int = 0
    failures: int = 0
    skipped_db: int = 0
    errors: list[str] = field(default_factory=list)


def enrich_loads_batch(
    jobs: list[tuple[dict[str, Any], list[Any], str, dict[str, str]]],
    *,
    rules: dict[str, Any] | None = None,
    overwrite: bool = False,
    stats: AiEnrichRunStats | None = None,
) -> bool:
    """
    jobs: (load 字典, header_row, tab_key, cells A–U)
    就地写入 load。单批内一次 Gemini 请求。
    成功应用解析结果返回 True，否则 False。
    """
    if not jobs:
        return True
    rules = rules or load_ai_sheet_rules()
    allowlist = build_ai_allowlist(rules)
    payload_rows = build_payload_rows_from_jobs(jobs, rules)
    prompt = build_enrich_prompt(rules, payload_rows)

    key = gemini_api_key_for_rules(rules)
    if not key:
        if stats:
            stats.failures += len(jobs)
            stats.errors.append("MISSING_GEMINI_API_KEY")
        return False

    raw, text = run_enrich_generate(rules, prompt)
    if stats:
        stats.calls += 1
        stats.rows += len(jobs)

    if isinstance(raw, str):
        if stats:
            stats.failures += len(jobs)
            stats.errors.append(raw[:500])
        return False
    if not text:
        if stats:
            stats.failures += len(jobs)
            stats.errors.append("AI_EMPTY_TEXT")
        return False

    try:
        arr = json.loads(text)
    except json.JSONDecodeError:
        if stats:
            stats.failures += len(jobs)
            stats.errors.append("AI_BAD_JSON")
        return False

    if not isinstance(arr, list):
        if stats:
            stats.failures += len(jobs)
            stats.errors.append("AI_NOT_ARRAY")
        return False

    if len(arr) != len(jobs):
        if stats:
            stats.failures += len(jobs)
            stats.errors.append(f"AI_LEN_MISMATCH want={len(jobs)} got={len(arr)}")
        return False

    for i, item in enumerate(arr):
        delta = _sanitize_delta(item, allowlist)
        apply_ai_delta_to_load(jobs[i][0], delta, overwrite=overwrite)
    return True


def enrich_loads_batches_parallel(
    jobs: list[tuple[dict[str, Any], list[Any], str, dict[str, str]]],
    *,
    rules: dict[str, Any],
    batch_size: int,
    max_workers: int,
    overwrite: bool = False,
    stats: AiEnrichRunStats | None = None,
    progress: dict[str, Any] | None = None,
    progress_lock: threading.Lock | None = None,
) -> set[str]:
    """
    先按 batch_size 切批，再多线程并发调用 enrich_loads_batch（每批一次 Gemini）。
    合并完成后再调用，以便先得到总行数再并行请求。
    返回本 run 中 Gemini 成功写回 load 的 quote_no 集合。
    """
    enriched: set[str] = set()
    if not jobs:
        return enriched
    bs = max(1, int(batch_size))
    chunks: list[list[tuple[dict[str, Any], list[Any], str, dict[str, str]]]] = []
    for i in range(0, len(jobs), bs):
        chunks.append(jobs[i : i + bs])

    inflight_ews: set[str] = set()
    inflight_lock = threading.Lock()
    cap_ews = 48

    def _sync_formatting_ews() -> None:
        if progress is None:
            return
        lst = sorted(inflight_ews)
        progress["ai_formatting_ews"] = lst[:cap_ews]
        progress["ai_formatting_ews_more"] = max(0, len(lst) - cap_ews)

    def _flush_formatting(*, with_global_lock: bool) -> None:
        if with_global_lock and progress_lock is not None:
            with progress_lock:
                _sync_formatting_ews()
        else:
            _sync_formatting_ews()

    def _run_chunk(
        chunk: list[tuple[dict[str, Any], list[Any], str, dict[str, str]]],
    ) -> tuple[AiEnrichRunStats, int, set[str]]:
        nonlocal inflight_ews
        qns_chunk = {
            str(j[0].get("quote_no") or "").strip()
            for j in chunk
        }
        qns_chunk.discard("")
        with inflight_lock:
            inflight_ews |= qns_chunk
            _flush_formatting(with_global_lock=True)
        try:
            st = AiEnrichRunStats()
            ok = enrich_loads_batch(chunk, rules=rules, overwrite=overwrite, stats=st)
            qns: set[str] = set()
            if ok:
                for j in chunk:
                    ld = j[0]
                    qn = str(ld.get("quote_no") or "").strip()
                    if qn:
                        qns.add(qn)
            return st, len(chunk), qns
        finally:
            with inflight_lock:
                inflight_ews -= qns_chunk
                _flush_formatting(with_global_lock=True)

    mw = max(1, min(int(max_workers), len(chunks)))
    with ThreadPoolExecutor(max_workers=mw) as ex:
        futures = [ex.submit(_run_chunk, ch) for ch in chunks]
        for fut in as_completed(futures):
            st, n_done, qns = fut.result()
            enriched |= qns
            if stats is not None:
                stats.calls += st.calls
                stats.rows += st.rows
                stats.failures += st.failures
                stats.errors.extend(st.errors)
            if progress is not None:
                if progress_lock is not None:
                    with progress_lock:
                        progress["ai_done"] = int(progress.get("ai_done") or 0) + n_done
                else:
                    progress["ai_done"] = int(progress.get("ai_done") or 0) + n_done
    return enriched
