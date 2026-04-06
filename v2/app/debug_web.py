from __future__ import annotations

import html
import json
import re
import threading
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .db import (
    ALLOWED_STATUS,
    clear_load_only,
    clear_load_quote_only,
    create_validation_job,
    ensure_schema,
    get_validation_job,
    has_running_validation_job,
    is_import_done,
    now_iso,
    open_db,
)
from .mapping import load_mapping
from .settings import get_settings
from .sheet_import import run_one_time_import
from .validation_runner import (
    new_job_id,
    run_validation_job_thread,
    validation_start_lock,
)
from .quote_web import router as _quote_router

app = FastAPI(title="EW v2 Debug", version="0.1.0")
app.include_router(_quote_router)

TAB_KEYS = ("quote", "order", "complete", "cancel")

_DEBUG_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, must-revalidate",
    "Pragma": "no-cache",
}

def _order_load_state_status_filter(load_state: str | None) -> tuple[str, tuple[str, ...]] | None:
    """
    text1 §6：待找车 `ordered`；已找到车 `carrier_assigned`；运输中 `picked`；
    「全部」不加过滤（含 ready_to_pick、unloaded 等）。
    """
    v = (load_state or "").strip().lower()
    if v in ("", "all"):
        return None
    if v == "waiting":
        return ("status = ?", ("ordered",))
    if v == "found":
        return ("status = ?", ("carrier_assigned",))
    if v == "transit":
        return ("status = ?", ("picked",))
    return None


def _normalize_order_load_state(load_state: str | None) -> str | None:
    v = (load_state or "").strip().lower()
    return v if v in ("waiting", "found", "transit") else None


def _pickup_eta_overdue(row: dict[str, str]) -> bool:
    eta = str(row.get("pickup_eta") or "").strip()
    if not eta:
        return False
    st = str(row.get("status") or "")
    if st in ("picked", "unloaded", "complete", "cancel"):
        return False
    try:
        iso = eta.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp() < datetime.now(timezone.utc).timestamp()
    except Exception:
        return False


def _city_zip_state_from_address(addr: str) -> str:
    """
    从 Geocode 常见格式或杂糅单行里解析 US：**City, ST ZIP**（逗号在市后，州+邮编）。
    例：「..., Houston, TX 77001, USA」→「Houston, TX 77001」
    """
    t = (addr or "").strip()
    if not t:
        return ""
    # 「… , City, ST 12345」
    m = re.search(r",\s*([^,]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b", t, re.I)
    if m:
        city = m.group(1).strip()
        st = m.group(2).upper()
        z = m.group(3)
        if re.match(r"^\d", city):
            parts = [p.strip() for p in t.split(",") if p.strip()]
            if len(parts) >= 3:
                city = parts[-3]
        return f"{city}, {st} {z}".strip()
    # 无逗号片段时：若句末有 ST ZIP，前一词可当 city
    m2 = re.search(
        r"([A-Za-z0-9\s\.\-]+?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*$", t, re.I
    )
    if m2:
        city = m2.group(1).strip().rstrip(",")
        if len(city) > 48:
            city = city[-48:].lstrip()
        st = m2.group(2).upper()
        z = m2.group(3)
        if city and not re.match(r"^\d+\s*$", city):
            return f"{city}, {st} {z}".strip()
        return f"{st} {z}"
    # 仅 ST + ZIP
    m3 = re.search(r"\b([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\b", t, re.I)
    if m3:
        return f"{m3.group(1).upper()} {m3.group(2)}"
    return ""


def _route_summary_collapsed(r: dict[str, str]) -> str:
    o = (r.get("origin_normalized") or "").strip() or (
        r.get("ship_from_raw") or ""
    ).strip()
    d = (r.get("dest_normalized") or "").strip() or (
        r.get("ship_to_raw") or ""
    ).strip()
    lo = _city_zip_state_from_address(o)
    ld = _city_zip_state_from_address(d)
    if lo or ld:
        return f"{lo or '—'} → {ld or '—'}"
    return ""


def _load_tab_detail_dl(r: dict[str, str]) -> str:
    """折叠展开后的字段列表（与旧版表格列一致）。"""

    def txt(key: str, maxlen: int | None = None) -> str:
        v = r.get(key)
        if v is None:
            s = ""
        else:
            s = str(v)
        if maxlen is not None and len(s) > maxlen:
            s = s[:maxlen] + "…"
        return s

    trouble = "Y" if int(r.get("is_trouble_case") or 0) else ""
    cargo = "Y" if int(r.get("cargo_ready") or 0) else ""
    validate_y = "Y" if int(r.get("validate_ok") or 0) else ""
    ai_retry_y = "Y" if int(r.get("used_ai_retry") or 0) else ""
    mile = (
        txt("distance_miles")
        if r.get("distance_miles") is not None
        else ""
    )
    ai_conf = (
        txt("ai_confidence")
        if r.get("ai_confidence") is not None
        else ""
    )

    pairs: list[tuple[str, str]] = [
        ("quote_no", txt("quote_no")),
        ("status", txt("status")),
        ("trouble", trouble),
        ("customer", txt("customer_name")),
        ("note_D", txt("note_d_raw", 400)),
        ("note_E", txt("note_e_raw", 400)),
        ("note_F", txt("note_f_raw", 400)),
        ("broker", txt("broker")),
        ("actual_driver_rate", txt("actual_driver_rate_raw")),
        ("carriers", txt("carriers", 400)),
        ("commodity", txt("commodity_desc")),
        ("ship_from", txt("ship_from_raw")),
        ("J_consignee", txt("consignee_contact")),
        ("shipper_info", txt("shipper_info", 500)),
        ("consignee_info", txt("consignee_info", 800)),
        ("ship_to", txt("ship_to_raw")),
        ("weight", txt("weight_raw")),
        ("dimension", txt("dimension_raw")),
        ("volume", txt("volume_raw")),
        ("mile", mile),
        ("origin_type", txt("origin_land_use")),
        ("dest_type", txt("dest_land_use")),
        ("validate_ok", validate_y),
        ("validate_error", txt("validate_error", 400)),
        ("ai_retry", ai_retry_y),
        ("ai_conf", ai_conf),
        ("origin_norm", txt("origin_normalized", 240)),
        ("dest_norm", txt("dest_normalized", 240)),
        ("customer_quote", txt("customer_quote_raw")),
        ("driver_rate", txt("driver_rate_raw")),
        ("pickup_eta", txt("pickup_eta")),
        ("delivery_eta", txt("delivery_eta")),
        ("pickup_tz", txt("pickup_tz")),
        ("delivery_tz", txt("delivery_tz")),
        ("cargo_ready", cargo),
        ("carrier_note", txt("carrier_note", 400)),
        ("op_by", txt("operator_updated_by")),
        ("op_at", txt("operator_updated_at")),
        ("source_tabs", txt("source_tabs")),
        ("updated_at", txt("updated_at")),
    ]
    parts = [
        f"<dt>{html.escape(label)}</dt><dd>{html.escape(val)}</dd>"
        for label, val in pairs
    ]
    return '<dl class="gf-detail-dl">' + "".join(parts) + "</dl>"


def _load_table_interaction_script() -> str:
    return r"""
<script>
(function () {
  function toggle(summaryTr) {
    var det = summaryTr.nextElementSibling;
    if (!det || det.getAttribute("data-gf-detail") !== "1") return;
    var btn = summaryTr.querySelector(".gf-expand-btn");
    var expanding = det.hasAttribute("hidden");
    if (expanding) {
      det.removeAttribute("hidden");
      summaryTr.setAttribute("aria-expanded", "true");
      if (btn) btn.textContent = "\u25BC";
    } else {
      det.setAttribute("hidden", "");
      summaryTr.setAttribute("aria-expanded", "false");
      if (btn) btn.textContent = "\u25B6";
    }
  }
  document.querySelectorAll("table.gf-load-table tbody").forEach(function (tb) {
    tb.addEventListener("click", function (ev) {
      var tr = ev.target.closest("tr.gf-load-summary");
      if (!tr || !tb.contains(tr)) return;
      toggle(tr);
    });
    tb.addEventListener("keydown", function (ev) {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      var tr = ev.target.closest("tr.gf-load-summary");
      if (!tr || !tb.contains(tr)) return;
      if (ev.target !== tr) return;
      if (ev.key === " ") ev.preventDefault();
      toggle(tr);
    });
  });
})();
</script>
"""


def _reminder_script_block() -> str:
    return r"""
<script>
(function () {
  const params = new URLSearchParams(location.search);
  const REMINDER_MS = (function () {
    const v = parseInt(params.get("reminder_interval_ms") || "", 10);
    return Number.isFinite(v) && v > 0 ? v : 30 * 60 * 1000;
  })();
  const STOP_AFTER_MS = 24 * 60 * 60 * 1000;
  const LS_FIRST = "ew_pickup_rem_first_ts_";
  const LS_LAST = "ew_pickup_rem_last_ts_";

  function parseDueAt(iso, tzHint) {
    if (!iso || !String(iso).trim()) return null;
    try {
      const t = Date.parse(String(iso).replace(/Z$/, "+00:00"));
      if (Number.isNaN(t)) return null;
      return t;
    } catch (e) {
      return null;
    }
  }

  function terminalStatus(st) {
    return ["picked", "unloaded", "complete", "cancel"].indexOf(
      String(st || "").trim()
    ) >= 0;
  }

  async function poll() {
    try {
      if (!("Notification" in window)) return;
      const perm = Notification.permission;
      if (perm !== "granted" && perm !== "default") return;
      const r = await fetch("/debug/api/reminder-candidates", { cache: "no-store" });
      if (!r.ok) return;
      const data = await r.json();
      const items = data.items || [];
      const now = Date.now();
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        const due = parseDueAt(it.pickup_eta, it.pickup_tz);
        if (!due || now < due) continue;
        if (terminalStatus(it.status)) continue;
        const q = String(it.quote_no || "");
        const kf = LS_FIRST + q;
        const kl = LS_LAST + q;
        let first = parseInt(localStorage.getItem(kf) || "0", 10);
        if (!first || !Number.isFinite(first)) {
          first = now;
          localStorage.setItem(kf, String(first));
        }
        if (now - first > STOP_AFTER_MS) continue;
        const last = parseInt(localStorage.getItem(kl) || "0", 10);
        if (last && now - last < REMINDER_MS) continue;
        if (perm === "default") {
          await Notification.requestPermission();
        }
        if (Notification.permission === "granted") {
          try {
            new Notification("EW：提货 ETA 已过仍未 picked", {
              body: q + "（" + String(it.pickup_eta || "") + "）",
            });
          } catch (e) {}
        }
        localStorage.setItem(kl, String(now));
      }
    } catch (e) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      poll();
      setInterval(poll, 60000);
    });
  } else {
    poll();
    setInterval(poll, 60000);
  }
})();
</script>
"""


def _conn():
    st = get_settings()
    conn = open_db(st.db_path)
    ensure_schema(conn)
    return conn, st


def _render_layout(title: str, body: str) -> HTMLResponse:
    nav = (
        '<nav class="gf-nav" aria-label="主导航">'
        '<a href="/debug">Home</a>'
        '<a href="/quote" target="_blank" rel="noopener noreferrer">AI 收集报价数据</a>'
        '<a href="/debug/tab/quote">quote</a>'
        '<a href="/debug/tab/order">order</a>'
        '<a href="/debug/tab/complete">complete</a>'
        '<a href="/debug/tab/cancel">cancel</a>'
        "</nav>"
    )
    page = f"""<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet"/>
  <style>
    :root {{
      --gf-primary: #673ab7;
      --gf-primary-hover: #5e35b1;
      --gf-surface: #ffffff;
      --gf-page: #f8f7fc;
      --gf-text: #202124;
      --gf-muted: #5f6368;
      --gf-border: #dadce0;
      --gf-success: #34a853;
      --gf-error: #d93025;
      --gf-radius: 8px;
      --gf-shadow: 0 1px 2px rgba(60,64,67,.3), 0 1px 3px 1px rgba(60,64,67,.15);
    }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    body.gf-page {{
      margin: 0;
      min-height: 100vh;
      font-family: Roboto, system-ui, -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: var(--gf-text);
      background: var(--gf-page);
    }}
    .gf-header {{
      background: var(--gf-primary);
      color: #fff;
      box-shadow: var(--gf-shadow);
    }}
    .gf-header__inner {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 12px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px 20px;
    }}
    .gf-header__brand {{
      font-weight: 500;
      font-size: 1.125rem;
      letter-spacing: 0.02em;
    }}
    .gf-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 16px;
      align-items: center;
    }}
    .gf-nav a {{
      color: rgba(255,255,255,.95);
      text-decoration: none;
      font-size: 13px;
      font-weight: 500;
      padding: 4px 0;
      border-radius: 4px;
    }}
    .gf-nav a:hover {{ text-decoration: underline; color: #fff; }}
    .gf-nav a:focus-visible {{
      outline: 2px solid #fff;
      outline-offset: 2px;
    }}
    .gf-main {{
      padding: 24px 16px 48px;
    }}
    .gf-card {{
      max-width: 1200px;
      margin: 0 auto;
      background: var(--gf-surface);
      border-radius: var(--gf-radius);
      box-shadow: var(--gf-shadow);
      padding: 28px 32px 36px;
    }}
    .gf-title {{
      margin: 0 0 8px;
      font-size: 1.5rem;
      font-weight: 500;
      color: var(--gf-text);
      letter-spacing: -0.01em;
    }}
    .gf-card h2 {{
      font-size: 1.125rem;
      font-weight: 500;
      margin: 28px 0 12px;
      color: var(--gf-text);
    }}
    .gf-card h2:first-of-type {{ margin-top: 20px; }}
    .muted {{ color: var(--gf-muted); font-size: 13px; }}
    .ok {{
      border-left: 4px solid var(--gf-success);
      background: #e6f4ea;
      padding: 12px 16px;
      border-radius: 0 var(--gf-radius) var(--gf-radius) 0;
      margin: 0 0 16px;
      color: var(--gf-text);
    }}
    .err {{
      border-left: 4px solid var(--gf-error);
      background: #fce8e6;
      padding: 12px 16px;
      border-radius: 0 var(--gf-radius) var(--gf-radius) 0;
      margin: 0 0 16px;
      color: var(--gf-text);
    }}
    .gf-table-wrap {{
      overflow: auto;
      margin: 12px 0 24px;
      border: 1px solid var(--gf-border);
      border-radius: var(--gf-radius);
    }}
    .gf-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .gf-table th, .gf-table td {{
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
      border-bottom: 1px solid var(--gf-border);
    }}
    .gf-table th {{
      background: #f8f9fa;
      color: var(--gf-muted);
      font-weight: 500;
      position: sticky;
      top: 0;
      z-index: 1;
      border-bottom: 2px solid var(--gf-border);
      box-shadow: 0 1px 0 var(--gf-border);
    }}
    .gf-table tbody tr:hover {{ background: #f8f9fa; }}
    .gf-cards {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 12px;
      margin: 16px 0 20px;
    }}
    .gf-card-stat {{
      border: 1px solid var(--gf-border);
      border-radius: var(--gf-radius);
      padding: 16px;
      background: #fafafa;
    }}
    .count {{ font-weight: 500; font-size: 1.25rem; color: var(--gf-text); margin-top: 4px; }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 16px 0 24px;
      align-items: center;
    }}
    .actions form {{ margin: 0; }}
    .gf-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 0 24px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 500;
      border-radius: 4px;
      cursor: pointer;
      border: none;
      text-decoration: none;
      transition: background .15s, box-shadow .15s, border-color .15s;
    }}
    .gf-btn:focus-visible {{
      outline: 2px solid var(--gf-primary);
      outline-offset: 2px;
    }}
    .gf-btn-primary {{
      background: var(--gf-primary);
      color: #fff;
      box-shadow: 0 1px 2px rgba(60,64,67,.3);
    }}
    .gf-btn-primary:hover {{ background: var(--gf-primary-hover); }}
    .gf-btn-danger {{
      background: var(--gf-surface);
      color: var(--gf-error);
      border: 1px solid var(--gf-error);
      box-shadow: none;
    }}
    .gf-btn-danger:hover {{ background: #fce8e6; }}
    .gf-btn-ghost {{
      background: #ffffff;
      color: var(--gf-primary);
      border: 1px solid var(--gf-border);
      box-shadow: none;
    }}
    .gf-btn-ghost:hover {{ background: #f3e5f5; border-color: #ce93d8; }}
    .gf-order-filter {{
      border: 1px solid var(--gf-border);
      border-radius: var(--gf-radius);
      padding: 14px 16px;
      background: #f8f9fa;
      margin: 0 0 16px;
    }}
    .gf-order-filter__title {{
      font-weight: 500;
      margin: 0 0 10px;
      color: var(--gf-text);
      font-size: 14px;
    }}
    .gf-link {{
      color: var(--gf-primary);
      text-decoration: none;
      font-weight: 500;
    }}
    .gf-link:hover {{ text-decoration: underline; }}
    .gf-link:focus-visible {{
      outline: 2px solid var(--gf-primary);
      outline-offset: 2px;
      border-radius: 2px;
    }}
    .gf-link-list {{ margin: 8px 0 0; padding-left: 20px; }}
    .gf-link-list li {{ margin: 8px 0; }}
    .gf-progress {{
      height: 8px;
      background: #e8eaed;
      border-radius: 4px;
      overflow: hidden;
      margin: 16px 0;
    }}
    .gf-progress__bar {{
      height: 100%;
      width: 0%;
      background: var(--gf-success);
      transition: width 0.2s ease;
    }}
    .gf-card code, .gf-code {{
      background: #f1f3f4;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.9em;
      font-family: ui-monospace, monospace;
    }}
    tr.gf-row-overdue > td {{ background: #fff3e0; }}
    table.gf-load-table tbody tr.gf-load-summary {{
      cursor: pointer;
    }}
    table.gf-load-table tbody tr.gf-load-summary:focus-visible {{
      outline: 2px solid var(--gf-primary);
      outline-offset: -2px;
    }}
    table.gf-load-table tbody tr.gf-load-summary:hover td {{
      background: #f5f5f5;
    }}
    table.gf-load-table tbody tr.gf-load-summary.gf-row-overdue:hover td {{
      background: #ffe8cc;
    }}
    table.gf-load-table .gf-chev {{
      width: 2rem;
      text-align: center;
      font-size: 12px;
      color: var(--gf-muted);
      user-select: none;
    }}
    table.gf-load-table tr.gf-load-detail td {{
      padding: 14px 16px 18px;
      background: #fafafa;
      border-bottom: 1px solid var(--gf-border);
    }}
    .gf-detail-dl {{
      display: grid;
      grid-template-columns: 9.5rem 1fr;
      gap: 6px 16px;
      margin: 0;
      font-size: 13px;
    }}
    .gf-detail-dl dt {{
      margin: 0;
      color: var(--gf-muted);
      font-weight: 500;
    }}
    .gf-detail-dl dd {{
      margin: 0;
      word-break: break-word;
    }}
    .gf-sum-main {{ vertical-align: middle; line-height: 1.45; }}
    .gf-sum-qno {{ font-weight: 500; }}
    .gf-sum-route {{ font-size: 13px; }}
    .gf-sum-sep {{ margin: 0 0.35em; }}
  </style>
</head>
<body class="gf-page">
  <header class="gf-header">
    <div class="gf-header__inner">
      <span class="gf-header__brand">EW v2 Debug</span>
      {nav}
    </div>
  </header>
  <main class="gf-main">
    <article class="gf-card">
      <h1 class="gf-title">{html.escape(title)}</h1>
      {body}
    </article>
  </main>
{_reminder_script_block()}
</body>
</html>
"""
    return HTMLResponse(page, headers=dict(_DEBUG_NO_CACHE_HEADERS))


def _feedback_block(msg: str | None, err: str | None) -> str:
    if msg:
        return f'<div class="ok">{html.escape(msg)}</div>'
    if err:
        return f'<div class="err">{html.escape(err)}</div>'
    return ""


@app.get("/debug", response_class=HTMLResponse)
def debug_home(msg: str | None = None, err: str | None = None) -> HTMLResponse:
    conn, st = _conn()
    count_row = conn.execute("SELECT COUNT(1) AS c FROM load").fetchone()
    rows_count = int(count_row["c"] if count_row else 0)
    lock_on = is_import_done(conn)
    log_rows = conn.execute(
        """
        SELECT run_at, trigger, rows_read, rows_written, rows_skipped, success, error_message
        FROM load_sync_log
        ORDER BY id DESC
        LIMIT 8
        """
    ).fetchall()
    cards = (
        f'<div class="gf-cards">'
        f'<div class="gf-card-stat"><div class="muted">当前 load 行数</div>'
        f'<div class="count" id="dbg-load-rows">{rows_count}</div></div>'
        f'<div class="gf-card-stat"><div class="muted">导入锁</div>'
        f'<div class="count" id="dbg-import-lock">{"ON" if lock_on else "OFF"}</div></div>'
        f'<div class="gf-card-stat"><div class="muted">环境</div><div class="count">{html.escape(st.app_env)}</div></div>'
        f"</div>"
    )
    forms = """
    <div class="actions">
      <form method="post" action="/debug/actions/validate-address">
        <button type="submit" class="gf-btn gf-btn-primary">验证地址（全量 I->K）</button>
      </form>
      <form method="post" action="/debug/actions/clear-load">
        <button type="submit" class="gf-btn gf-btn-danger">清空数据（仅 load）</button>
      </form>
      <div class="actions" style="margin:0;display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;">
        <form method="post" action="/debug/actions/import" style="display:inline;">
          <button type="submit" class="gf-btn gf-btn-primary">导入数据</button>
        </form>
        <a class="gf-btn gf-btn-ghost" href="/quote" target="_blank" rel="noopener noreferrer">AI 收集报价数据</a>
      </div>
    </div>
    """
    rows_html = "".join(
        f"<tr><td>{html.escape(str(r['run_at']))}</td>"
        f"<td>{html.escape(str(r['trigger']))}</td>"
        f"<td>{int(r['rows_read'])}</td>"
        f"<td>{int(r['rows_written'])}</td>"
        f"<td>{int(r['rows_skipped'])}</td>"
        f"<td>{'ok' if int(r['success']) == 1 else 'fail'}</td>"
        f"<td>{html.escape(str(r['error_message'] or ''))}</td></tr>"
        for r in log_rows
    )
    empty_log_row = '<tr><td colspan="7" class="muted">暂无</td></tr>'
    logs = (
        "<h2>最近导入日志</h2>"
        "<div class='gf-table-wrap'>"
        "<table class='gf-table'><thead><tr><th>run_at</th><th>trigger</th><th>read</th><th>written</th><th>skipped</th><th>success</th><th>error</th></tr></thead>"
        f"<tbody>{rows_html or empty_log_row}</tbody></table>"
        "</div>"
    )
    links = (
        "<h2>四个 tab 调试页</h2>"
        "<ul class='gf-link-list'>"
        "<li><a class='gf-link' href='/debug/tab/quote'>quote</a></li>"
        "<li><a class='gf-link' href='/debug/tab/order'>order</a></li>"
        "<li><a class='gf-link' href='/debug/tab/complete'>complete</a></li>"
        "<li><a class='gf-link' href='/debug/tab/cancel'>cancel</a></li>"
        "</ul>"
    )
    status_refresh = """
<script>
(function () {
  async function pull() {
    try {
      const r = await fetch("/debug/api/status", { cache: "no-store" });
      if (!r.ok) return;
      const j = await r.json();
      var el = document.getElementById("dbg-import-lock");
      if (el) el.textContent = j.import_lock === "on" ? "ON" : "OFF";
      el = document.getElementById("dbg-load-rows");
      if (el) el.textContent = String(j.rows_count);
    } catch (e) {}
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", pull);
  } else {
    pull();
  }
  window.addEventListener("pageshow", function (ev) {
    if (ev.persisted) pull();
  });
})();
</script>
"""
    body = _feedback_block(msg, err) + cards + forms + links + logs + status_refresh
    return _render_layout("EW v2 Debug", body)


@app.get("/debug/api/status")
def debug_api_status() -> JSONResponse:
    conn, _ = _conn()
    count_row = conn.execute("SELECT COUNT(1) AS c FROM load").fetchone()
    rows_count = int(count_row["c"] if count_row else 0)
    lock_on = is_import_done(conn)
    return JSONResponse(
        {
            "rows_count": rows_count,
            "import_lock": "on" if lock_on else "off",
        },
        headers=dict(_DEBUG_NO_CACHE_HEADERS),
    )


@app.get("/debug/api/reminder-candidates")
def debug_api_reminder_candidates() -> JSONResponse:
    conn, _ = _conn()
    rows = conn.execute(
        """
        SELECT quote_no, status, pickup_eta, pickup_tz
        FROM load
        WHERE trim(pickup_eta) != ''
          AND status NOT IN ('picked','unloaded','complete','cancel')
        ORDER BY quote_no
        LIMIT 500
        """
    ).fetchall()
    items = [
        {
            "quote_no": str(r["quote_no"]),
            "status": str(r["status"]),
            "pickup_eta": str(r["pickup_eta"] or ""),
            "pickup_tz": str(r["pickup_tz"] or ""),
        }
        for r in rows
    ]
    return JSONResponse(
        {"items": items},
        headers=dict(_DEBUG_NO_CACHE_HEADERS),
    )


@app.post("/debug/actions/clear-load")
def action_clear_load() -> RedirectResponse:
    conn, _ = _conn()
    n = clear_load_only(conn)
    q = urlencode({"msg": f"已清空 load 数据，共 {n} 行；导入锁已关闭，可再次导入。"})
    return RedirectResponse(
        url=f"/debug?{q}",
        status_code=303,
        headers=dict(_DEBUG_NO_CACHE_HEADERS),
    )


@app.post("/debug/actions/clear-load-quote-tab")
def action_clear_load_quote_tab() -> RedirectResponse:
    conn, _ = _conn()
    n = clear_load_quote_only(conn)
    q = urlencode({"msg": f"已清空 quote tab 相关 load 行（source_tabs 含 quote），共 {n} 条。"})
    return RedirectResponse(
        url="/debug/tab/quote?" + q,
        status_code=303,
        headers=dict(_DEBUG_NO_CACHE_HEADERS),
    )


@app.post("/debug/actions/import")
def action_import() -> RedirectResponse:
    conn, st = _conn()
    try:
        mapping = load_mapping(st.mapping_path)
        stats = run_one_time_import(
            conn,
            mapping,
            credentials_file=str(st.google_credentials_path),
            app_env=st.app_env,
            force_reimport=False,
            trigger="debug-button",
        )
        ai_tail = ""
        if stats.ai_import_calls:
            ai_tail = (
                f" import_ai_calls={stats.ai_import_calls}"
                f" import_ai_failures={stats.ai_import_failures}"
            )
        q = urlencode(
            {
                "msg": (
                    f"导入完成: read={stats.rows_read}, written={stats.rows_written}, "
                    f"skipped={stats.rows_skipped}{ai_tail}"
                )
            }
        )
        return RedirectResponse(url=f"/debug?{q}", status_code=303)
    except Exception as e:
        q = urlencode({"err": f"导入失败: {e!s}"})
        return RedirectResponse(url=f"/debug?{q}", status_code=303)


@app.post("/debug/actions/patch-load")
def action_patch_load(
    quote_no: str = Form(...),
    return_tab: str = Form("order"),
    status: str = Form(""),
    pickup_eta: str = Form(""),
    delivery_eta: str = Form(""),
    pickup_tz: str = Form(""),
    delivery_tz: str = Form(""),
    carrier_note: str = Form(""),
    cargo_ready: str = Form(""),
    operator_name: str = Form(""),
) -> RedirectResponse:
    qn = (quote_no or "").strip()
    safe_tab = return_tab if return_tab in TAB_KEYS else "order"
    base = f"/debug/tab/{safe_tab}"
    conn, _ = _conn()
    cur = conn.execute(
        """
        SELECT pickup_eta, delivery_eta, pickup_tz, delivery_tz, carrier_note, cargo_ready
        FROM load WHERE quote_no = ?
        """,
        (qn,),
    ).fetchone()
    if not cur:
        q = urlencode({"err": f"未找到 quote_no：{qn}"})
        return RedirectResponse(
            url=f"{base}?{q}",
            status_code=303,
            headers=dict(_DEBUG_NO_CACHE_HEADERS),
        )

    pe_in = pickup_eta.strip()
    de_in = delivery_eta.strip()
    ptz_in = pickup_tz.strip()
    dtz_in = delivery_tz.strip()
    new_pe = pe_in if pe_in else str(cur["pickup_eta"] or "")
    new_de = de_in if de_in else str(cur["delivery_eta"] or "")
    new_ptz = ptz_in if ptz_in else str(cur["pickup_tz"] or "")
    new_dtz = dtz_in if dtz_in else str(cur["delivery_tz"] or "")
    cur_cn = str(cur["carrier_note"] or "")
    cn_in = carrier_note.strip()
    new_cn = cn_in if cn_in else cur_cn

    if str(new_pe).strip() and not str(new_ptz).strip():
        q = urlencode(
            {"err": "已填写提货 ETA 时必须填写 pickup_tz（IANA），或先清空 ETA。"}
        )
        return RedirectResponse(
            url=f"{base}?{q}",
            status_code=303,
            headers=dict(_DEBUG_NO_CACHE_HEADERS),
        )
    if str(new_de).strip() and not str(new_dtz).strip():
        q = urlencode(
            {"err": "已填写送达 ETA 时必须填写 delivery_tz（IANA），或先清空 ETA。"}
        )
        return RedirectResponse(
            url=f"{base}?{q}",
            status_code=303,
            headers=dict(_DEBUG_NO_CACHE_HEADERS),
        )

    st = (status or "").strip()
    if st and st not in ALLOWED_STATUS:
        q = urlencode({"err": f"无效 status：{st}"})
        return RedirectResponse(
            url=f"{base}?{q}",
            status_code=303,
            headers=dict(_DEBUG_NO_CACHE_HEADERS),
        )

    cr_sel = (cargo_ready or "").strip()
    if cr_sel == "":
        cr = int(cur["cargo_ready"] or 0)
    else:
        cr = 1 if cr_sel == "1" else 0

    op = (operator_name or "").strip() or "debug"
    ts = now_iso()

    fields = [
        "pickup_eta = ?",
        "delivery_eta = ?",
        "pickup_tz = ?",
        "delivery_tz = ?",
        "carrier_note = ?",
        "cargo_ready = ?",
        "operator_updated_by = ?",
        "operator_updated_at = ?",
        "updated_at = ?",
    ]
    vals: list[object] = [
        new_pe,
        new_de,
        new_ptz,
        new_dtz,
        new_cn,
        cr,
        op,
        ts,
        ts,
    ]
    if st:
        fields.insert(0, "status = ?")
        vals.insert(0, st)
    conn.execute(
        f"UPDATE load SET {', '.join(fields)} WHERE quote_no = ?",
        tuple(vals + [qn]),
    )
    conn.commit()
    q = urlencode({"msg": f"已更新 {qn}"})
    return RedirectResponse(
        url=f"{base}?{q}",
        status_code=303,
        headers=dict(_DEBUG_NO_CACHE_HEADERS),
    )


@app.post("/debug/actions/validate-address")
def action_validate_address() -> RedirectResponse:
    with validation_start_lock():
        conn, st = _conn()
        if has_running_validation_job(conn):
            q = urlencode({"err": "已有地址验证任务进行中，请等待完成后再试。"})
            return RedirectResponse(url=f"/debug?{q}", status_code=303)
        raw_rows = conn.execute(
            "SELECT quote_no, ship_from_raw, consignee_contact, ship_to_raw FROM load ORDER BY quote_no"
        ).fetchall()
        rows = [dict(r) for r in raw_rows]
        job_id = new_job_id()
        create_validation_job(
            conn, job_id=job_id, kind="all", tab_key="", total=len(rows)
        )
        conn.commit()
        db_path = st.db_path.resolve()

    threading.Thread(
        target=run_validation_job_thread,
        args=(db_path, job_id, rows, "validate-address"),
        daemon=True,
    ).start()
    return RedirectResponse(url=f"/debug/validation/{job_id}", status_code=303)


@app.post("/debug/actions/validate-address-tab")
def action_validate_address_tab(
    tab_key: str = Form(...),
    load_state: str = Form(""),
) -> RedirectResponse:
    if tab_key not in TAB_KEYS:
        q = urlencode({"err": f"无效 tab: {tab_key}"})
        return RedirectResponse(url=f"/debug?{q}", status_code=303)
    ls_q = _normalize_order_load_state(load_state) if tab_key == "order" else None
    with validation_start_lock():
        conn, st = _conn()
        if has_running_validation_job(conn):
            qd: dict[str, str] = {"err": "已有地址验证任务进行中，请等待完成后再试。"}
            if ls_q:
                qd["load_state"] = ls_q
            q = urlencode(qd)
            return RedirectResponse(url=f"/debug/tab/{tab_key}?{q}", status_code=303)
        rows = _tab_rows(tab_key, load_state=ls_q)
        job_id = new_job_id()
        create_validation_job(
            conn, job_id=job_id, kind="tab", tab_key=tab_key, total=len(rows)
        )
        conn.commit()
        db_path = st.db_path.resolve()

    threading.Thread(
        target=run_validation_job_thread,
        args=(db_path, job_id, rows, f"validate-address:{tab_key}"),
        daemon=True,
    ).start()
    q = urlencode({"return_tab": tab_key})
    return RedirectResponse(
        url=f"/debug/validation/{job_id}?{q}",
        status_code=303,
    )


def _job_to_api_dict(row: object) -> dict[str, object]:
    r = dict(row)  # type: ignore[arg-type]
    return {str(k): v for k, v in r.items()}


@app.get("/debug/api/validation-job/{job_id}")
def api_validation_job(job_id: str) -> JSONResponse:
    conn, _ = _conn()
    row = get_validation_job(conn, job_id)
    if not row:
        return JSONResponse({"error": "not_found"}, status_code=404)
    return JSONResponse(_job_to_api_dict(row))


@app.get("/debug/validation/{job_id}", response_class=HTMLResponse)
def validation_progress_page(job_id: str, return_tab: str | None = None) -> HTMLResponse:
    conn, _ = _conn()
    row = get_validation_job(conn, job_id)
    if not row:
        body = (
            "<p class='err'>任务不存在</p>"
            "<p><a class='gf-link' href='/debug'>返回 Debug 首页</a></p>"
        )
        return _render_layout("验证进度", body)

    esc_id = html.escape(job_id)
    safe_tab = return_tab if (return_tab and return_tab in TAB_KEYS) else None
    back_href = f"/debug/tab/{safe_tab}" if safe_tab else "/debug"
    back_label = (
        f"返回 tab {html.escape(safe_tab)}" if safe_tab else "返回 Debug 首页"
    )

    script = f"""
<script>
const jobId = {json.dumps(job_id)};
const apiUrl = '/debug/api/validation-job/' + encodeURIComponent(jobId);
let timer = null;

function pct(processed, total) {{
  if (!total) return 0;
  return Math.min(100, Math.round((processed / total) * 100));
}}

function render(j) {{
  const st = (j.status || '').toLowerCase();
  document.getElementById('status').textContent = st;
  document.getElementById('processed').textContent = j.processed ?? 0;
  document.getElementById('total').textContent = j.total ?? 0;
  document.getElementById('ok').textContent = j.ok_count ?? 0;
  document.getElementById('deleted').textContent = j.fail_deleted ?? 0;
  document.getElementById('ai_retry').textContent = j.ai_retry_count ?? 0;
  document.getElementById('ai_recovered').textContent = j.ai_recovered_count ?? 0;
  document.getElementById('current').textContent = j.current_quote_no || '—';
  const p = pct(Number(j.processed || 0), Number(j.total || 0));
  document.getElementById('bar').style.width = p + '%';
  document.getElementById('pct').textContent = p + '%';
  const pr = document.getElementById('gf-progress-root');
  if (pr) pr.setAttribute('aria-valuenow', String(p));
  const errEl = document.getElementById('errbox');
  if (j.error_message) {{
    errEl.style.display = 'block';
    errEl.textContent = j.error_message;
  }} else {{
    errEl.style.display = 'none';
    errEl.textContent = '';
  }}
  if (st === 'done' || st === 'error') {{
    if (timer) clearInterval(timer);
    timer = null;
    document.getElementById('hint').textContent =
      st === 'done' ? '任务已完成，可返回查看数据。' : '任务失败，请查看错误信息。';
  }}
}}

async function poll() {{
  try {{
    const r = await fetch(apiUrl);
    if (!r.ok) return;
    const j = await r.json();
    render(j);
  }} catch (e) {{}}
}}

poll();
timer = setInterval(poll, 1000);
</script>
"""

    body = f"""
<p class="muted">任务 ID：<code class="gf-code">{esc_id}</code></p>
<p id="hint" class="muted">后台验证进行中，进度每秒刷新。</p>
<div class="gf-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" id="gf-progress-root">
  <div id="bar" class="gf-progress__bar"></div>
</div>
<p><strong id="pct">0%</strong> · 状态 <strong id="status">—</strong></p>
<div class="gf-cards">
  <div class="gf-card-stat"><div class="muted">已处理 / 总数</div>
    <div class="count"><span id="processed">0</span> / <span id="total">0</span></div></div>
  <div class="gf-card-stat"><div class="muted">成功</div><div class="count" id="ok">0</div></div>
  <div class="gf-card-stat"><div class="muted">删除（验证失败）</div><div class="count" id="deleted">0</div></div>
  <div class="gf-card-stat"><div class="muted">AI 重试次数</div><div class="count" id="ai_retry">0</div></div>
  <div class="gf-card-stat"><div class="muted">AI 救回</div><div class="count" id="ai_recovered">0</div></div>
</div>
<p class="muted">当前 <code class="gf-code" id="current">—</code></p>
<div id="errbox" class="err" style="display:none"></div>
<p><a class="gf-link" href="{html.escape(back_href)}">{back_label}</a></p>
{script}
"""
    return _render_layout("地址验证进度", body)


def _tab_rows(tab_key: str, *, load_state: str | None = None) -> list[dict[str, str]]:
    conn, _ = _conn()
    extra_where = ""
    params: list[str] = [tab_key]
    if tab_key == "order":
        filt = _order_load_state_status_filter(load_state)
        if filt:
            frag, frag_params = filt
            extra_where = f" AND {frag}"
            params.extend(list(frag_params))
    rows = conn.execute(
        f"""
        SELECT quote_no, status, is_trouble_case, customer_name, commodity_desc,
               note_d_raw, note_e_raw, note_f_raw,
               broker, actual_driver_rate_raw, carriers,
               ship_from_raw, consignee_contact, shipper_info, consignee_info, ship_to_raw, weight_raw, dimension_raw, volume_raw,
               distance_miles, origin_land_use, dest_land_use, validate_ok, validate_error,
               used_ai_retry, ai_confidence, origin_normalized, dest_normalized,
               customer_quote_raw, driver_rate_raw,
               pickup_eta, delivery_eta, pickup_tz, delivery_tz,
               cargo_ready, carrier_note, operator_updated_by, operator_updated_at,
               source_tabs, updated_at
        FROM load
        WHERE instr(',' || source_tabs || ',', ',' || ? || ',') > 0
        {extra_where}
        ORDER BY updated_at DESC, quote_no DESC
        LIMIT 1000
        """,
        tuple(params),
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/debug/tab/{tab_key}", response_class=HTMLResponse)
def debug_tab_page(
    tab_key: str,
    msg: str | None = None,
    err: str | None = None,
    load_state: str | None = None,
) -> HTMLResponse:
    if tab_key not in TAB_KEYS:
        return _render_layout(
            "Tab 不存在",
            "<p class='err'>无效 tab key</p>"
            "<p><a class='gf-link' href='/debug'>返回 Debug 首页</a></p>",
        )
    if tab_key == "order":
        raw_ls = (load_state or "").strip().lower()
        if raw_ls in ("waiting", "found", "transit"):
            state = raw_ls
            ls = _normalize_order_load_state(load_state)
        else:
            state = "all"
            ls = None
    else:
        state = ""
        ls = None

    rows = _tab_rows(tab_key, load_state=ls)
    head = (
        "<tr>"
        '<th class="gf-chev" scope="col"></th>'
        '<th scope="col">单号 · 起止（City, ST ZIP）</th>'
        "</tr>"
    )
    body_rows: list[str] = []
    for r in rows:
        overdue = _pickup_eta_overdue(r)
        sum_cls = "gf-load-summary"
        if overdue:
            sum_cls += " gf-row-overdue"
        tip = "提货 ETA 已过仍未 picked · 点击展开/收起" if overdue else "点击展开/收起详情"
        qn = html.escape(str(r.get("quote_no", "")))
        route = _route_summary_collapsed(r)
        route_html = (
            '<span class="gf-sum-sep muted">·</span>'
            f'<span class="gf-sum-route muted">{html.escape(route)}</span>'
            if route
            else ""
        )
        dl = _load_tab_detail_dl(r)
        body_rows.append(
            f"<tr class=\"{sum_cls}\" title=\"{html.escape(tip)}\" "
            'tabindex="0" role="button" aria-expanded="false">'
            '<td class="gf-chev"><span class="gf-expand-btn" aria-hidden="true">▶</span></td>'
            f'<td class="gf-sum-main"><span class="gf-sum-qno">{qn}</span>{route_html}</td></tr>'
            f"<tr class=\"gf-load-detail\" data-gf-detail=\"1\" hidden><td colspan=\"2\">{dl}</td></tr>"
        )
    empty_data_row = '<tr><td colspan="2" class="muted">暂无数据</td></tr>'
    state_label = {
        "all": "全部",
        "waiting": "待找车",
        "found": "已找到车",
        "transit": "运输中",
    }.get(state, "全部")
    order_filter = ""
    if tab_key == "order":
        sel_all = state == "all"
        sel_wait = state == "waiting"
        sel_found = state == "found"
        sel_tr = state == "transit"
        order_filter = (
            "<div class='gf-order-filter' role='region' aria-label='找车状态筛选'>"
            "<div class='gf-order-filter__title'>找车状态（order 列表筛选，对齐 text1 §6）</div>"
            "<p class='muted' style='margin:0 0 10px;font-size:13px'>"
            "待找车：<code class='gf-code'>ordered</code>；"
            "已找到车：<code class='gf-code'>carrier_assigned</code>；"
            "运输中：<code class='gf-code'>picked</code>。"
            "「全部」包含 <code class='gf-code'>ready_to_pick</code>、<code class='gf-code'>unloaded</code> 等。"
            "</p>"
            "<div class='actions' style='margin:0; flex-wrap:wrap'>"
            f"<a class='gf-btn {'gf-btn-primary' if sel_all else 'gf-btn-ghost'}' "
            "href='/debug/tab/order' style='text-decoration:none'>全部</a>"
            f"<a class='gf-btn {'gf-btn-primary' if sel_wait else 'gf-btn-ghost'}' "
            "href='/debug/tab/order?load_state=waiting' style='text-decoration:none'>待找车</a>"
            f"<a class='gf-btn {'gf-btn-primary' if sel_found else 'gf-btn-ghost'}' "
            "href='/debug/tab/order?load_state=found' style='text-decoration:none'>已找到车</a>"
            f"<a class='gf-btn {'gf-btn-primary' if sel_tr else 'gf-btn-ghost'}' "
            "href='/debug/tab/order?load_state=transit' style='text-decoration:none'>运输中</a>"
            f"<span class='muted' style='margin-left:4px'>当前：<b>{html.escape(state_label)}</b></span>"
            "</div></div>"
        )
    validate_ls = ""
    if tab_key == "order" and state in ("waiting", "found", "transit"):
        validate_ls = (
            f'<input type="hidden" name="load_state" value="{html.escape(state)}"/>'
        )
    clear_quote = ""
    if tab_key == "quote":
        clear_quote = (
            '<form method="post" action="/debug/actions/clear-load-quote-tab">'
            '<button type="submit" class="gf-btn gf-btn-danger" '
            'title="删除 load 中 source_tabs 含 quote 的行（不影响 order/complete/cancel 等）">'
            "清空数据</button>"
            "</form>"
        )
    actions = (
        '<div class="actions">'
        f"{clear_quote}"
        f'<form method="post" action="/debug/actions/validate-address-tab">'
        f'<input type="hidden" name="tab_key" value="{html.escape(tab_key)}"/>'
        f"{validate_ls}"
        '<button type="submit" class="gf-btn gf-btn-primary">仅验证当前 tab</button>'
        "</form>"
        "</div>"
    )
    tbody_html = "".join(body_rows) if body_rows else empty_data_row
    body = (
        _feedback_block(msg, err)
        + order_filter
        + actions
        + f"<p class='muted'>tab=<b>{html.escape(tab_key)}</b>，共 {len(rows)} 条（最多 1000）；"
        "默认仅显示单号，点击行展开详情。</p>"
        "<div class='gf-table-wrap'>"
        "<table class='gf-table gf-load-table'><thead>"
        + head
        + "</thead><tbody>"
        + tbody_html
        + "</tbody></table></div>"
        + _load_table_interaction_script()
    )
    return _render_layout(f"Debug Tab: {tab_key}", body)

