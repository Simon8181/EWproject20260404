"""
EW v3 web shell: same visual language as v2 Debug (gf-*), clean paths without query params on nav.

Run (推荐，减轻 reload 打断长请求):
  ./run_web.sh
或:
  cd v3 && python3 -m uvicorn app.web:app --host 127.0.0.1 --port 8011 \\
    --reload --reload-dir app --reload-dir core --reload-delay 1.5

长时间「四表合并 + AI」时若整页无响应：可能是请求仍执行中，或 --reload 因保存文件重启了进程导致连接中断。
此时可另开标签访问 / 试连接；稳定跑长任务时请去掉 --reload 再启动。
"""

from __future__ import annotations

import html
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.listener import listeners

from app.load_routes import router as load_routes_router
from app.settings import load_env
from app.sheet_refresh import router as sheet_refresh_router
from app.sheet_sync import router as sheet_sync_router

_DEBUG_BRAND = "EW v3 Debug Simon"


def _expose_api_error_traceback() -> bool:
    """是否在 JSON 错误里附带 traceback；默认开（调试壳）。生产可设 V3_EXPOSE_API_TRACEBACK=0。"""
    load_env()
    v = (os.environ.get("V3_EXPOSE_API_TRACEBACK") or "1").strip().lower()
    return v in ("1", "true", "yes", "on")
TAB_KEYS = ("quote", "order", "complete", "cancel")

_NO_CACHE = {
    "Cache-Control": "no-store, must-revalidate",
    "Pragma": "no-cache",
}


def _merge_sync_client_script() -> str:
    """四表合并：预览 merge 统计与 quote_no_customer_response 计数；可选 apply 写入 V2_DB_PATH。"""
    return r"""
(function () {
  var btnPre = document.getElementById("sheet-merge-preview-btn");
  var btnApply = document.getElementById("sheet-merge-apply-btn");
  var chkAi = document.getElementById("sheet-merge-ai");
  var chkOw = document.getElementById("sheet-merge-ai-overwrite");
  var out = document.getElementById("sheet-merge-result");
  var statusEl = document.getElementById("sheet-merge-status");
  var progWrap = document.getElementById("sheet-merge-long-progress");
  var progTimer = document.getElementById("sheet-merge-long-progress-timer");
  var progTitle = document.getElementById("sheet-merge-progress-title");
  var progDetail = document.getElementById("sheet-merge-progress-detail");
  if (!out) return;

  var progInterval = null;
  var progPoll = null;
  function pad2m(n) {
    return n < 10 ? "0" + n : String(n);
  }
  function renderMergeServerProgress(p) {
    if (!progDetail) return;
    if (!p || p.active === false) {
      progDetail.textContent = "";
      return;
    }
    var lines = [];
    if (p.phase === "sheet") lines.push("服务端：拉取 Google Sheet…");
    else if (p.phase === "merge") {
      var m = "服务端：四表合并… 已纳入 " + (p.merge_rows || 0) + " 行";
      if (p.merge_total != null) m += "（本批合计 " + p.merge_total + " 行）";
      else m += "（合并进行中…）";
      lines.push(m);
    } else if (p.phase === "validate") {
      lines.push(
        "服务端：合并行校验完成，准备多线程 Gemini…（已合并 " +
          (p.merge_total != null ? p.merge_total : p.merge_rows || 0) +
          " 行）"
      );
    } else if (p.phase === "ai") {
      lines.push(
        "服务端：AI 补缺（已合并 " +
          (p.merge_total != null ? p.merge_total : p.ai_total || 0) +
          " 行，并发按批请求 Gemini）… " +
          (p.ai_done || 0) +
          " / " +
          (p.ai_total || 0) +
          " 行（每批返回后才增加计数）"
      );
      var ewsM = p.ai_formatting_ews || [];
      if (ewsM.length) {
        lines.push(
          "当前请求中的 EW：" + ewsM.map(function (q) { return esc(String(q)); }).join(", ")
        );
      }
      if ((p.ai_formatting_ews_more || 0) > 0) {
        lines.push("… 另有 " + p.ai_formatting_ews_more + " 个未列出（并发多批）");
      }
    }
    else if (p.phase === "persist") lines.push("服务端：写入 SQLite…");
    progDetail.textContent = lines.join("\n");
  }
  function startMergePoll() {
    if (progPoll) clearInterval(progPoll);
    progPoll = setInterval(function () {
      fetch("/api/core/sheet/long-task-progress", {
        headers: { Accept: "application/json" },
      })
        .then(function (r) {
          return r.json();
        })
        .then(renderMergeServerProgress)
        .catch(function () {});
    }, 450);
  }
  function stopMergePoll() {
    if (progPoll) {
      clearInterval(progPoll);
      progPoll = null;
    }
    renderMergeServerProgress({ active: false });
  }
  function startMergePageProgress(apply, useAi) {
    if (!progWrap || !progTimer) return;
    if (progTitle) {
      if (apply) {
        progTitle.textContent = useAi
          ? "正在写入数据库（拉表、合并、AI 分批补缺）…"
          : "正在写入数据库（拉表、合并，不调 Gemini）…";
      } else {
        progTitle.textContent = useAi
          ? "正在生成合并预览（拉表、合并、AI 分批补缺）…"
          : "正在生成合并预览（拉表、合并，不调 Gemini）…";
      }
    }
    progWrap.hidden = false;
    var t0 = Date.now();
    progTimer.textContent = "已等待 0:00";
    if (progInterval) clearInterval(progInterval);
    progInterval = setInterval(function () {
      var s = Math.floor((Date.now() - t0) / 1000);
      progTimer.textContent =
        "已等待 " + Math.floor(s / 60) + ":" + pad2m(s % 60);
    }, 500);
    if (useAi) startMergePoll();
    else if (progDetail)
      progDetail.textContent = "服务端处理中（未启用 Gemini 时无 AI 细进度）…";
  }
  function stopMergePageProgress() {
    stopMergePoll();
    if (progInterval) {
      clearInterval(progInterval);
      progInterval = null;
    }
    if (progWrap) progWrap.hidden = true;
  }

  function esc(s) {
    s = s == null ? "" : String(s);
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showError(msg) {
    out.innerHTML = "<div class=\"gf-sync-err\">" + esc(msg) + "</div>";
  }

  function mergeFullQuoteBLastPanel(full, data) {
    if (!full) return "";
    if (full.applied) {
      var sheetN =
        full.last_b_sheet_row_1based != null && full.last_b_sheet_row_1based !== ""
          ? Number(full.last_b_sheet_row_1based)
          : NaN;
      var bHtml =
        full.last_b_column_b != null && full.last_b_column_b !== ""
          ? "<code class=\"gf-code\">" + esc(String(full.last_b_column_b)) + "</code>"
          : "<span class=\"muted\">（空）</span>";
      var ewHtml =
        full.last_b_ew_id != null && full.last_b_ew_id !== ""
          ? "<code class=\"gf-code\">" + esc(String(full.last_b_ew_id)) + "</code>"
          : "<span class=\"muted\">—</span>";
      var rowHtml = Number.isFinite(sheetN) ? esc(String(sheetN)) : "—";
      var firstRow =
        full.first_data_row_1based != null
          ? esc(String(full.first_data_row_1based))
          : "2";
      var trunc = "";
      if (full.last_b_may_be_truncated_by_quote_cap) {
        var capF =
          full.quote_extend_fetch_max_total_rows != null
            ? esc(String(full.quote_extend_fetch_max_total_rows))
            : "";
        trunc =
          "<p class=\"gf-b-last-warn\"><strong>提示</strong>：已达 quote 连续拉取总上限" +
          (capF
            ? "（<code class=\"gf-code\">" + capF + "</code> 行）"
            : "") +
          "，末行仍有 B，表中更下方可能仍有行。可增大 <code class=\"gf-code\">quote_extend_fetch_max_total_rows</code>。</p>";
      } else if (full.last_b_may_be_truncated_by_max_rows) {
        trunc =
          "<p class=\"gf-b-last-warn\"><strong>提示</strong>：已达本批 <code class=\"gf-code\">max_rows</code> 上限且 B 最后落在末行，表中更下方可能仍有行。</p>";
      }
      return (
        "<section class=\"gf-b-last-panel gf-b-last-panel--full\" aria-label=\"整张 quote 表 B 列最后有值\">" +
        "<h2 class=\"gf-b-last-panel__title\">B 列最后有值（整张 quote 表 · 本批拉取）</h2>" +
        "<p class=\"muted gf-b-last-sub\">与报价工作表中、本批范围内的「最下方 B 非空」一致（<strong>未</strong>按 order/complete/cancel 过滤）。</p>" +
        "<dl>" +
        "<dt>B 列格内容</dt><dd>" +
        bHtml +
        "</dd>" +
        "<dt>工作表行号</dt><dd>" +
        rowHtml +
        "</dd>" +
        "<dt>EW 号（C 列）</dt><dd>" +
        ewHtml +
        "</dd>" +
        "<dt>本批内数据行下标</dt><dd>" +
        esc(String(full.last_b_data_row_index)) +
        "（从 0 起；首条数据行=<strong>" +
        firstRow +
        "</strong>）</dd>" +
        "</dl>" +
        trunc +
        "</section>"
      );
    }
    if (full.reason === "no_column_b_data") {
      return (
        "<section class=\"gf-b-last-panel gf-b-last-panel--muted\" aria-label=\"整张 quote 表 B 列最后有值\">" +
        "<h2 class=\"gf-b-last-panel__title\">B 列最后有值（整张 quote 表 · 本批）</h2>" +
        "<p class=\"muted\">quote 表本批拉取中<strong>无 B 列非空</strong>。</p>" +
        "</section>"
      );
    }
    return "";
  }

  function mergeQuoteBLastPanel(bt, data) {
    if (!bt) return "";
    if (bt.applied) {
      var sheetN =
        bt.last_b_sheet_row_1based != null && bt.last_b_sheet_row_1based !== ""
          ? Number(bt.last_b_sheet_row_1based)
          : NaN;
      var bHtml =
        bt.last_b_column_b != null && bt.last_b_column_b !== ""
          ? "<code class=\"gf-code\">" + esc(String(bt.last_b_column_b)) + "</code>"
          : "<span class=\"muted\">（空）</span>";
      var ewHtml =
        bt.last_b_ew_id != null && bt.last_b_ew_id !== ""
          ? "<code class=\"gf-code\">" + esc(String(bt.last_b_ew_id)) + "</code>"
          : "<span class=\"muted\">—</span>";
      var rowHtml = Number.isFinite(sheetN) ? esc(String(sheetN)) : "—";
      var remIdx = esc(String(bt.last_b_data_row_index));
      var tabIdx =
        bt.last_b_quote_tab_row_index_0based != null
          ? esc(String(bt.last_b_quote_tab_row_index_0based))
          : remIdx;
      var firstRow =
        bt.first_data_row_1based != null ? esc(String(bt.first_data_row_1based)) : "2";
      var trunc = "";
      if (bt.last_b_may_be_truncated_by_quote_cap) {
        var capR =
          bt.quote_extend_fetch_max_total_rows != null
            ? esc(String(bt.quote_extend_fetch_max_total_rows))
            : "";
        trunc =
          "<p class=\"gf-b-last-warn\"><strong>提示</strong>：已达 quote 连续拉取总上限" +
          (capR
            ? "（<code class=\"gf-code\">" + capR + "</code> 行）"
            : "") +
          "，末行仍有 B，下方可能仍有数据。</p>";
      } else if (bt.last_b_may_be_truncated_by_max_rows) {
        trunc =
          "<p class=\"gf-b-last-warn\"><strong>提示</strong>：已达本批 <code class=\"gf-code\">max_rows</code> 上限且 B 最后落在 quote 表末行，下方可能仍有数据。</p>";
      }
      var diffNote =
        bt.remainder_differs_from_full_tab_last_b
          ? "<p class=\"muted gf-b-last-sub\"><strong>说明</strong>：若此处 EW 与上一块「整张 quote」不同，通常是因为该单号已出现在 <strong>order / complete / cancel</strong>，不会进入 quote <strong>remainder</strong>；B 尾比例只在 remainder 上计算。</p>"
          : "";
      return (
        "<section class=\"gf-b-last-panel\" aria-label=\"B 列最后有值 remainder\">" +
        "<h2 class=\"gf-b-last-panel__title\">B 列最后有值（remainder · 合并切分用）</h2>" +
        "<p class=\"muted gf-b-last-sub\">仅包含未在前三表（cancel→complete→order）出现过的单号后的报价行。</p>" +
        diffNote +
        "<dl>" +
        "<dt>B 列格内容</dt><dd>" +
        bHtml +
        "</dd>" +
        "<dt>工作表行号</dt><dd>" +
        rowHtml +
        "</dd>" +
        "<dt>EW 号（C 列）</dt><dd>" +
        ewHtml +
        "</dd>" +
        "<dt>remainder 内行下标</dt><dd>" +
        remIdx +
        "（从 0 起）</dd>" +
        "<dt>quote 表内行下标</dt><dd>" +
        tabIdx +
        "（从 0 起；首条数据行=<strong>" +
        firstRow +
        "</strong>）</dd>" +
        "</dl>" +
        trunc +
        "</section>"
      );
    }
    if (bt.reason === "no_column_b_data") {
      return (
        "<section class=\"gf-b-last-panel\" aria-label=\"B 列最后有值\">" +
        "<h2 class=\"gf-b-last-panel__title\">B 列最后有值（quote 合并）</h2>" +
        "<p class=\"muted\">quote <strong>remainder</strong> 内<strong>无 B 列非空</strong>，无法确定「最后有值」行。</p>" +
        "</section>"
      );
    }
    if (bt.reason === "tail_percent_disabled_or_empty") {
      return (
        "<section class=\"gf-b-last-panel gf-b-last-panel--muted\" aria-label=\"B 列最后有值\">" +
        "<h2 class=\"gf-b-last-panel__title\">B 列最后有值（quote 合并）</h2>" +
        "<p class=\"muted\">未计算：B 列尾比例为 0 / 或未启用；或 quote remainder 为空。</p>" +
        "</section>"
      );
    }
    return "";
  }

  function renderMerge(data) {
    var parts = [];
    parts.push(
      "<p class=\"gf-sync-meta\">完成时间：" + esc(new Date().toISOString()) + "</p>"
    );
    if (data.persisted) {
      parts.push(
        "<p class=\"muted\"><strong>已写入数据库</strong> · rows_written=<strong>" +
          esc(String(data.rows_written || 0)) +
          "</strong></p>"
      );
    }
    var errs = data.errors || [];
    if (errs.length) {
      parts.push("<p class=\"muted\">Sheet 警告：</p><ul class=\"gf-link-list\">");
      errs.forEach(function (e) {
        parts.push("<li>" + esc(e) + "</li>");
      });
      parts.push("</ul>");
    }
    var m = data.merge || {};
    var st = m.stats || {};
    var uniqEwTop =
      typeof data.merged_unique_ew === "number"
        ? data.merged_unique_ew
        : typeof st.total === "number"
          ? st.total
          : null;
    if (uniqEwTop !== null) {
      parts.push(
        "<p class=\"gf-sync-meta\"><strong>合并后唯一 EW 条数：</strong>" +
          esc(String(uniqEwTop)) +
          (m.ai_enrich_enabled
            ? "（本请求已启用 Gemini 补缺）"
            : "（本请求未调 Gemini）") +
          "</p>"
      );
    }
    var fullEarly = m.quote_tab_last_b_full || {};
    var fullPanel = mergeFullQuoteBLastPanel(fullEarly, data);
    if (fullPanel) parts.push(fullPanel);
    var btEarly = m.quote_remainder_b_tail || {};
    var bMergePanel = mergeQuoteBLastPanel(btEarly, data);
    if (bMergePanel) parts.push(bMergePanel);
    parts.push("<p class=\"muted\"><strong>合并统计</strong>（cancel → complete → order → quote）：</p>");
    parts.push("<ul class=\"gf-link-list\">");
    parts.push("<li>cancel：<strong>" + esc(String(st.cancel || 0)) + "</strong></li>");
    parts.push("<li>complete：<strong>" + esc(String(st.complete || 0)) + "</strong></li>");
    parts.push("<li>order：<strong>" + esc(String(st.order || 0)) + "</strong></li>");
    parts.push(
      "<li>quote（pending_quote）：<strong>" +
        esc(String(st.quote_pending_quote || 0)) +
        "</strong></li>"
    );
    parts.push(
      "<li>quote（<code class=\"gf-code\">quoted</code>，P 列有给客价）：<strong>" +
        esc(String(st.quote_quoted || 0)) +
        "</strong></li>"
    );
    parts.push(
      "<li>quote（<code class=\"gf-code\">quote_no_customer_response</code>）：<strong>" +
        esc(String(st.quote_no_customer_response || 0)) +
        "</strong></li>"
    );
    parts.push("<li>合计：<strong>" + esc(String(st.total || 0)) + "</strong></li>");
    parts.push(
      "<li>已跳过（<strong>B 列无数据</strong>）：<strong>" +
        esc(String(st.skipped_non_compliant_no_column_b || 0)) +
        "</strong></li>"
    );
    parts.push(
      "<li>已跳过（非列表行 / C 列无 EW / 已在较前阶段出现 / 同表重复 EW）：<strong>" +
        esc(String(st.skipped_non_list_row || 0)) +
        "</strong> / <strong>" +
        esc(String(st.skipped_non_compliant_no_ew_id || 0)) +
        "</strong> / <strong>" +
        esc(String(st.skipped_ew_in_earlier_stage || 0)) +
        "</strong> / <strong>" +
        esc(String(st.skipped_duplicate_ew_same_tab || 0)) +
        "</strong></li>"
    );
    parts.push("</ul>");
    var mval = m.validation || {};
    if (mval.rules_zh && mval.rules_zh.length) {
      parts.push(
        "<p class=\"muted\"><strong>合并行规则</strong>：" +
          esc(mval.rules_zh.join("；")) +
          "。</p>"
      );
    }
    var bt = btEarly;
    if (bt.applied) {
      var sheetRowM =
        bt.last_b_sheet_row_1based != null && bt.last_b_sheet_row_1based !== ""
          ? Number(bt.last_b_sheet_row_1based)
          : NaN;
      var ewMerge =
        bt.last_b_ew_id != null && bt.last_b_ew_id !== ""
          ? " <strong>B 列最后有值</strong>所在行 EW 号（C 列）：<code class=\"gf-code\">" +
            esc(String(bt.last_b_ew_id)) +
            "</code>（quote remainder 内下标 <strong>" +
            esc(String(bt.last_b_data_row_index)) +
            "</strong>" +
            (Number.isFinite(sheetRowM)
              ? "；<strong>工作表行号</strong> <strong>" +
                esc(String(sheetRowM)) +
                "</strong>（按 quote 表内行序映射）"
              : "") +
            "）。"
          : "";
      var bMerge =
        bt.last_b_column_b != null && bt.last_b_column_b !== ""
          ? " 该行 <strong>B 列内容</strong>：<code class=\"gf-code\">" +
            esc(String(bt.last_b_column_b)) +
            "</code>。"
          : "";
      parts.push(
        "<p class=\"muted\">Quote remainder <strong>仅含 B 列有值的行</strong>（Sheet 上 B 空行已跳过不写库）。B 列 span：末尾 <strong>" +
          esc(String(bt.tail_percent)) +
          "%</strong> 为 <code class=\"gf-code\">pending_quote</code>；上部及尾段为 <code class=\"gf-code\">quote_no_customer_response</code>；<strong>P 列有给客价</strong>为 <code class=\"gf-code\">quoted</code>（本批 remainder：pending_quote <strong>" +
          esc(String(bt.pending_quote_row_count || 0)) +
          "</strong>，quoted <strong>" +
          esc(String(bt.quoted_p_row_count || 0)) +
          "</strong>）。" +
          ewMerge +
          bMerge +
          "</p>"
      );
      if (bt.last_b_may_be_truncated_by_quote_cap) {
        var capM =
          bt.quote_extend_fetch_max_total_rows != null
            ? esc(String(bt.quote_extend_fetch_max_total_rows))
            : "";
        parts.push(
          "<p class=\"gf-sync-err\">Quote 表<strong>连续拉取已达总上限</strong>" +
            (capM ? "（<code class=\"gf-code\">" + capM + "</code> 行）" : "") +
            "，末行 B 仍非空：以下可能仍有未拉数据。请在 <code class=\"gf-code\">ai_sheet_rules.yaml</code> 增大 <code class=\"gf-code\">quote_extend_fetch_max_total_rows</code>。</p>"
        );
      } else if (bt.last_b_may_be_truncated_by_max_rows) {
        parts.push(
          "<p class=\"gf-sync-err\">Quote 表本批已拉满 <code class=\"gf-code\">max_rows</code>（<strong>" +
            esc(String(bt.max_rows_request != null ? bt.max_rows_request : data.max_rows)) +
            "</strong>），且 <strong>B 列最后非空</strong>对应 quote 表内<strong>最后一行</strong>：以下可能仍有未拉数据。请增大 <code class=\"gf-code\">max_rows</code> 或检查 quote 连续拉取配置后重试。</p>"
        );
      }
    } else if (bt.reason === "empty_remainder") {
      parts.push(
        "<p class=\"muted\">合并阶段：quote remainder <strong>为空</strong>（可能本批 quote 无合规模型行，或未覆盖单号均在它表出现）。</p>"
      );
    } else if (bt.reason === "no_column_b_data") {
      parts.push(
        "<p class=\"muted\">合并阶段：quote remainder 内未找到 B 列非空（异常；合规行应在合并前已过滤）。</p>"
      );
    } else if (bt.reason === "tail_percent_disabled_or_empty") {
      parts.push("<p class=\"muted\">未启用 B 列末尾比例。</p>");
    }
    var prev = m.preview_rows || [];
    if (prev.length) {
      var maxShow = 50;
      var slice = prev.slice(0, maxShow);
      parts.push(
        "<div class=\"gf-table-wrap\"><table class=\"gf-table\"><thead><tr>"
      );
      parts.push(
        "<th>quote_no</th><th>status</th><th>customer_name</th><th>source_tabs</th></tr></thead><tbody>"
      );
      slice.forEach(function (row) {
        parts.push(
          "<tr><td>" +
            esc(row.quote_no) +
            "</td><td>" +
            esc(row.status) +
            "</td><td>" +
            esc(row.customer_name) +
            "</td><td>" +
            esc(row.source_tabs) +
            "</td></tr>"
        );
      });
      parts.push("</tbody></table></div>");
      if (prev.length > maxShow) {
        parts.push(
          "<p class=\"muted\">仅展示前 " + maxShow + " 行，共 " + prev.length + " 行。</p>"
        );
      }
    } else {
      parts.push("<p class=\"muted\">（合并结果为空）</p>");
    }
    out.innerHTML = parts.join("");
  }

  function postMerge(apply) {
    out.innerHTML = "";
    var useAi = !!(chkAi && chkAi.checked);
    var useOw = !!(chkOw && chkOw.checked);
    if (statusEl) statusEl.textContent = apply ? "写入中…" : "拉取合并预览…";
    if (btnPre) btnPre.disabled = true;
    if (btnApply) btnApply.disabled = true;
    startMergePageProgress(apply, useAi);
    var qs = new URLSearchParams();
    if (apply) qs.set("apply", "true");
    qs.set("ai", useAi ? "true" : "false");
    qs.set("ai_overwrite", useOw ? "true" : "false");
    var q = qs.toString();
    fetch("/api/core/sheet/sync-load?" + q, {
      method: "POST",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        var ct = r.headers.get("content-type") || "";
        if (ct.indexOf("application/json") >= 0) {
          return r.json().then(function (j) {
            return { ok: r.ok, status: r.status, body: j };
          });
        }
        return r.text().then(function (t) {
          return { ok: r.ok, status: r.status, body: t };
        });
      })
      .then(function (x) {
        if (!x.ok) {
          var d = x.body;
          var msg =
            typeof d === "object" && d && d.detail
              ? Array.isArray(d.detail)
                ? JSON.stringify(d.detail)
                : String(d.detail)
              : typeof d === "string"
                ? d
                : "HTTP " + x.status;
          showError(msg);
          return;
        }
        renderMerge(x.body);
      })
      .catch(function (e) {
        showError(e && e.message ? e.message : String(e));
      })
      .finally(function () {
        stopMergePageProgress();
        if (statusEl) statusEl.textContent = "";
        if (btnPre) btnPre.disabled = false;
        if (btnApply) btnApply.disabled = false;
      });
  }

  if (btnPre) btnPre.addEventListener("click", function () { postMerge(false); });
  if (btnApply) btnApply.addEventListener("click", function () { postMerge(true); });
})();
"""

_DEBUG_SHEET_AI_SCRIPT = r"""
(function () {
  var btn = document.getElementById("debug-sheet-ai-btn");
  var ewEl = document.getElementById("debug-sheet-ai-ew");
  var poEl = document.getElementById("debug-sheet-ai-prompt-only");
  var outPrompt = document.getElementById("debug-sheet-ai-prompt");
  var outAi = document.getElementById("debug-sheet-ai-response");
  var errEl = document.getElementById("debug-sheet-ai-err");
  var statusEl = document.getElementById("debug-sheet-ai-status");
  if (!btn || !ewEl || !outPrompt || !outAi) return;

  function esc(s) {
    s = s == null ? "" : String(s);
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  btn.addEventListener("click", function () {
    var ew = (ewEl.value || "").trim();
    outPrompt.textContent = "";
    outAi.textContent = "";
    if (errEl) errEl.innerHTML = "";
    if (!ew) {
      if (errEl)
        errEl.innerHTML =
          '<div class="gf-sync-err">请输入 EW 单号</div>';
      return;
    }
    var po = poEl && poEl.checked;
    if (statusEl) statusEl.textContent = "请求中…";
    btn.disabled = true;
    var q =
      "ew=" +
      encodeURIComponent(ew) +
      "&prompt_only=" +
      (po ? "true" : "false");
    fetch("/api/core/sheet/debug-row-ai?" + q, {
      method: "POST",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        var ct = r.headers.get("content-type") || "";
        if (ct.indexOf("application/json") >= 0) {
          return r.json().then(function (j) {
            return { ok: r.ok, status: r.status, body: j };
          });
        }
        return r.text().then(function (t) {
          return { ok: r.ok, status: r.status, body: t };
        });
      })
      .then(function (x) {
        if (!x.ok) {
          var d = x.body;
          var msg =
            typeof d === "object" && d && d.detail
              ? Array.isArray(d.detail)
                ? JSON.stringify(d.detail)
                : String(d.detail)
              : typeof d === "string"
                ? d
                : "HTTP " + x.status;
          if (errEl)
            errEl.innerHTML =
              '<div class="gf-sync-err">' + esc(msg) + "</div>";
          return;
        }
        var data = x.body;
        outPrompt.textContent = data.prompt || "(空)";
        var parts = [];
        if (data.model_text)
          parts.push("【model_text】\n" + data.model_text);
        if (data.merge_error)
          parts.push("【merge_error】\n" + String(data.merge_error));
        if (data.parsed_json !== undefined && data.parsed_json !== null) {
          parts.push(
            "【parsed_json】\n" +
              JSON.stringify(data.parsed_json, null, 2)
          );
        }
        if (data.gemini_raw)
          parts.push(
            "【gemini_raw】\n" +
              JSON.stringify(data.gemini_raw, null, 2)
          );
        if (data.load_after_ai)
          parts.push(
            "【load_after_ai】\n" +
              JSON.stringify(data.load_after_ai, null, 2)
          );
        outAi.textContent =
          parts.length > 0
            ? parts.join("\n\n---\n\n")
            : po
              ? "（已选「仅 prompt」，未调用模型）"
              : "（无模型输出）";
      })
      .catch(function (e) {
        if (errEl)
          errEl.innerHTML =
            '<div class="gf-sync-err">' +
            esc(e && e.message ? e.message : e) +
            "</div>";
      })
      .finally(function () {
        if (statusEl) statusEl.textContent = "";
        btn.disabled = false;
      });
  });
})();
"""

_SAM_SHEET_REFRESH_SCRIPT = r"""
(function () {
  var API_MERGE_REFRESH = "/api/core/sheet/merge-refresh";
  var API_PROGRESS = "/api/core/sheet/long-task-progress";
  /** Sam sheet：仅拉表合并写库，不调 Gemini（merge-refresh?ai=false）。 */
  var SAM_SHEET_USE_AI = false;

  var btn = document.getElementById("sam-sheet-refresh-btn");
  var out = document.getElementById("sam-sheet-merge-out");
  var statusEl = document.getElementById("sam-sheet-merge-status");
  var chkClear = document.getElementById("sam-sheet-clear-quote");
  var prog = document.getElementById("sam-sheet-long-progress");
  var progTimer = document.getElementById("sam-sheet-progress-timer");
  var progDetail = document.getElementById("sam-sheet-progress-detail");
  var progTitle = document.getElementById("sam-sheet-progress-title");
  var barFill = document.getElementById("sam-sheet-progress-bar-fill");
  var barLabel = document.getElementById("sam-sheet-progress-bar-label");
  if (!btn || !out) return;

  var tick = null;
  var pollTick = null;

  function pad2(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function esc(s) {
    s = s == null ? "" : String(s);
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function barPct(p) {
    if (!p || p.active === false) return 100;
    var ph = p.phase;
    if (ph === "sheet") return 6;
    if (ph === "merge") {
      var mt = p.merge_total;
      var mr = p.merge_rows || 0;
      if (mt != null && mt > 0) return 6 + Math.min(24, Math.floor((mr / mt) * 24));
      return 14;
    }
    if (ph === "validate") return 34;
    if (ph === "ai") {
      var at = p.ai_total || 0;
      var ad = p.ai_done || 0;
      if (at > 0) return 36 + Math.floor((ad / at) * 48);
      return 42;
    }
    if (ph === "persist") return 88;
    if (ph === "done") return 100;
    return 4;
  }

  function setBar(p) {
    if (!barFill) return;
    var pct = barPct(p);
    barFill.style.width = pct + "%";
    if (barFill.setAttribute) {
      barFill.setAttribute("aria-valuenow", String(pct));
    }
    if (barLabel) {
      if (p && p.phase === "ai" && (p.ai_total || 0) > 0) {
        barLabel.textContent =
          "进度约 " +
          pct +
          "%（AI 补缺 " +
          (p.ai_done || 0) +
          " / " +
          (p.ai_total || 0) +
          " 行，多线程分批）";
      } else if (p && p.active !== false && p.phase) {
        barLabel.textContent = "进度约 " + pct + "%（阶段：" + p.phase + "）";
      } else {
        barLabel.textContent = "";
      }
    }
  }

  function renderServerProgress(p) {
    if (progDetail) {
      if (!p || p.active === false) {
        progDetail.textContent = "";
      } else {
        var lines = [];
        if (p.phase === "sheet") lines.push("服务端：拉取 Google Sheet 四表…");
        else if (p.phase === "merge") {
          var m =
            "服务端：四表合并… 已纳入 " +
            (p.merge_rows || 0) +
            " 行";
          if (p.merge_total != null)
            m += "（本批合计 " + p.merge_total + " 行）";
          else m += "（合并进行中…）";
          lines.push(m);
        } else if (p.phase === "validate") {
          lines.push(
            "服务端：合并行校验完成，准备多线程 Gemini…（已合并 " +
              (p.merge_total != null ? p.merge_total : p.merge_rows || 0) +
              " 行）"
          );
        } else if (p.phase === "ai") {
          lines.push(
            "服务端：AI 格式化 / 补缺（并发分批）… " +
              (p.ai_done || 0) +
              " / " +
              (p.ai_total || 0) +
              " 行（每批返回后才 + 整批行数；等接口时常在某一数字停几分钟）"
          );
          var ewsS = p.ai_formatting_ews || [];
          if (ewsS.length) {
            lines.push(
              "当前请求中的 EW（至多 48 个；多线程下多批并行）：" +
                ewsS.map(function (q) { return esc(String(q)); }).join(", ")
            );
          }
          if ((p.ai_formatting_ews_more || 0) > 0) {
            lines.push(
              "… 另有 " + p.ai_formatting_ews_more + " 个 EW 本屏未列出"
            );
          }
        } else if (p.phase === "persist")
          lines.push("服务端：写入 SQLite（upsert）…");
        else if (p.phase === "done") lines.push("服务端：已完成");
        progDetail.textContent = lines.join("\n");
      }
    }
    setBar(p);
  }

  function startProgressPoll() {
    if (pollTick) clearInterval(pollTick);
    pollTick = setInterval(function () {
      fetch(API_PROGRESS, { headers: { Accept: "application/json" } })
        .then(function (r) {
          var ct = r.headers.get("content-type") || "";
          if (ct.indexOf("application/json") >= 0) {
            return r.json();
          }
          return r.text().then(function () {
            return {};
          });
        })
        .then(renderServerProgress)
        .catch(function () {});
    }, 450);
  }

  function stopProgressPoll() {
    if (pollTick) {
      clearInterval(pollTick);
      pollTick = null;
    }
    renderServerProgress({ active: false });
    setBar({ active: false });
  }

  function startRunProgress() {
    if (!prog || !progTimer) return;
    prog.hidden = false;
    if (progTitle)
      progTitle.textContent = SAM_SHEET_USE_AI
        ? "正在拉表、合并、AI 补缺并写库…"
        : "正在拉表、合并并写库（不调 Gemini）…";
    if (progDetail)
      progDetail.textContent = SAM_SHEET_USE_AI
        ? ""
        : "服务端处理中；未启用 AI 时无 long-task 细进度，请等待请求结束。";
    var t0 = Date.now();
    progTimer.textContent = "已等待 0:00";
    if (tick) clearInterval(tick);
    tick = setInterval(function () {
      var s = Math.floor((Date.now() - t0) / 1000);
      progTimer.textContent =
        "已等待 " + Math.floor(s / 60) + ":" + pad2(s % 60);
    }, 500);
    if (SAM_SHEET_USE_AI) {
      startProgressPoll();
      setBar({ active: true, phase: "sheet" });
    } else {
      if (barFill) {
        barFill.style.width = "100%";
        barFill.setAttribute("aria-valuenow", "100");
      }
      if (barLabel) barLabel.textContent = "进行中（无分阶段进度）";
    }
  }

  function stopRunProgress() {
    stopProgressPoll();
    if (tick) {
      clearInterval(tick);
      tick = null;
    }
    if (prog) prog.hidden = true;
  }

  function confirmLines() {
    var clearFirst = !!(chkClear && chkClear.checked);
    var lines = [
      "将执行：拉取四表 → 合并校验 → upsert 写入 V2_DB_PATH（不调 Gemini）。",
      "",
      clearFirst
        ? "已勾选：入库前先删除本 data_source 且 source_tabs 含 quote 的 load 行。"
        : "未勾选先删：仅按 quote_no upsert（有则更新、无则新增）。",
      "",
      "行数多时主要耗时在 Google Sheets 拉取与写库。",
      "",
      "是否继续？",
    ];
    return lines.join("\n");
  }

  function renderSuccess(data) {
    var m = data.merge || {};
    var st = data.merge_stats || m.stats || {};
    var total = typeof st.total === "number" ? st.total : null;
    var parts = [];
    parts.push(
      "<p class=\"gf-sync-meta\">完成时间：" + esc(new Date().toISOString()) + "</p>"
    );
    parts.push(
      "<p class=\"gf-sync-meta\"><strong>写入行数（upsert）：</strong>" +
        esc(String(data.rows_written != null ? data.rows_written : "—")) +
        "</p>"
    );
    if (data.deleted_quote_tab_load_rows) {
      parts.push(
        "<p class=\"muted\">入库前已删本来源 quote 行：<strong>" +
          esc(String(data.deleted_quote_tab_load_rows)) +
          "</strong> 条。</p>"
      );
    }
    if (total !== null) {
      parts.push(
        "<p class=\"gf-sync-meta\"><strong>合并后唯一 EW 条数：</strong>" +
          esc(String(total)) +
          "</p>"
      );
    }
    if (st && typeof st.total === "number") {
      parts.push(
        "<p class=\"muted\"><strong>合并后按阶段计数</strong>（cancel → complete → order → quote）：</p>"
      );
      parts.push("<ul class=\"gf-link-list\">");
      parts.push("<li>cancel：<strong>" + esc(String(st.cancel || 0)) + "</strong></li>");
      parts.push("<li>complete：<strong>" + esc(String(st.complete || 0)) + "</strong></li>");
      parts.push("<li>order：<strong>" + esc(String(st.order || 0)) + "</strong></li>");
      parts.push(
        "<li>quote（pending_quote）：<strong>" +
          esc(String(st.quote_pending_quote || 0)) +
          "</strong></li>"
      );
      parts.push(
        "<li>quote（quoted）：<strong>" +
          esc(String(st.quote_quoted || 0)) +
          "</strong></li>"
      );
      parts.push(
        "<li>quote（quote_no_customer_response）：<strong>" +
          esc(String(st.quote_no_customer_response || 0)) +
          "</strong></li>"
      );
      parts.push("<li>合计：<strong>" + esc(String(st.total || 0)) + "</strong></li>");
      parts.push("</ul>");
    }
    if (
      SAM_SHEET_USE_AI &&
      ((m.ai_enrich_calls || 0) > 0 ||
        (m.ai_enrich_failures || 0) > 0 ||
        ((m.ai_enrich_errors || []).length > 0))
    ) {
      parts.push(
        "<p class=\"muted\">AI：调用 <strong>" +
          esc(String(m.ai_enrich_calls || 0)) +
          "</strong> 次 · 失败 <strong>" +
          esc(String(m.ai_enrich_failures || 0)) +
          "</strong> · 并行批次数 workers=<strong>" +
          esc(String(m.ai_enrich_parallel_batch_workers || 0)) +
          "</strong></p>"
      );
      var aerr = m.ai_enrich_errors || [];
      if (aerr.length) {
        parts.push("<p class=\"muted\">AI 错误摘要（至多 30 条）：</p><ul class=\"gf-link-list\">");
        aerr.forEach(function (e) {
          parts.push("<li>" + esc(typeof e === "string" ? e : JSON.stringify(e)) + "</li>");
        });
        parts.push("</ul>");
      }
    }
    var errs = data.errors || [];
    if (errs.length) {
      parts.push("<p class=\"muted\">Sheet 警告：</p><ul class=\"gf-link-list\">");
      errs.forEach(function (e) {
        parts.push("<li>" + esc(e) + "</li>");
      });
      parts.push("</ul>");
    }
    out.innerHTML = parts.join("");
  }

  btn.addEventListener("click", function () {
    if (!confirm(confirmLines())) return;
    out.innerHTML = "";
    if (statusEl) statusEl.textContent = "";
    btn.disabled = true;
    startRunProgress();

    var clearFirst = !!(chkClear && chkClear.checked);
    var qs = new URLSearchParams();
    qs.set("clear_quote", clearFirst ? "true" : "false");
    qs.set("ai", SAM_SHEET_USE_AI ? "true" : "false");
    qs.set("ai_overwrite", "false");

    fetch(API_MERGE_REFRESH + "?" + qs.toString(), {
      method: "POST",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        var ct = r.headers.get("content-type") || "";
        if (ct.indexOf("application/json") >= 0) {
          return r.json().then(function (j) {
            return { ok: r.ok, status: r.status, body: j };
          });
        }
        return r.text().then(function (t) {
          return { ok: r.ok, status: r.status, body: t };
        });
      })
      .then(function (x) {
        if (!x.ok) {
          var d = x.body;
          var msg;
          if (typeof d === "object" && d && d.detail) {
            msg = Array.isArray(d.detail)
              ? JSON.stringify(d.detail)
              : String(d.detail);
          } else if (typeof d === "string") {
            msg = d.replace(/\\s+/g, " ").trim();
            if (msg.length > 500) msg = msg.slice(0, 500) + "…";
            if (!msg) msg = "HTTP " + x.status;
          } else {
            msg = "HTTP " + x.status;
          }
          var htmlErr = "<div class=\"gf-sync-err\">" + esc(msg) + "</div>";
          if (typeof d === "object" && d && d.traceback) {
            htmlErr +=
              '<p class="gf-debug-section-title">traceback</p>' +
              '<pre class="gf-debug-pre" style="max-height:28rem;overflow:auto;white-space:pre-wrap">' +
              esc(String(d.traceback)) +
              "</pre>";
          }
          out.innerHTML = htmlErr;
          return;
        }
        renderSuccess(x.body);
      })
      .catch(function (e) {
        out.innerHTML =
          "<div class=\"gf-sync-err\">" +
          esc(e && e.message ? e.message : String(e)) +
          "</div>";
      })
      .finally(function () {
        stopRunProgress();
        if (statusEl) statusEl.textContent = "";
        btn.disabled = false;
      });
  });
})();
"""


def _render_layout(title: str, body: str) -> HTMLResponse:
    nav = (
        '<nav class="gf-nav" aria-label="主导航">'
        '<a href="/">Home</a>'
        '<details class="gf-nav-load">'
        '<summary>load</summary>'
        '<div class="gf-nav-load-panel" role="group" aria-label="load">'
        '<a href="/tab/quote">quote</a>'
        '<a href="/tab/order">order</a>'
        '<a href="/tab/complete">complete</a>'
        '<a href="/tab/cancel">cancel</a>'
        "</div>"
        "</details>"
        '<details class="gf-nav-load">'
        '<summary>debug</summary>'
        '<div class="gf-nav-load-panel" role="group" aria-label="debug">'
        '<a href="/debug/sheet-ai">调试刷新 Sheet（AI）</a>'
        '<a href="/debug/sam-sheet">导入 Sam sheet</a>'
        '<a href="/debug/clear-load">清空全部 load</a>'
        "</div>"
        "</details>"
        '<a href="/blank">blank</a>'
        "</nav>"
    )
    page = f"""<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
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
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial,
        "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
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
    .gf-nav-load {{
      position: relative;
    }}
    .gf-nav-load > summary {{
      list-style: none;
      cursor: pointer;
      color: rgba(255,255,255,.95);
      font-size: 13px;
      font-weight: 500;
      padding: 4px 0;
      user-select: none;
    }}
    .gf-nav-load > summary::-webkit-details-marker {{ display: none; }}
    .gf-nav-load > summary::after {{
      content: " ▾";
      font-size: 10px;
      opacity: 0.85;
    }}
    .gf-nav-load[open] > summary::after {{
      content: " ▴";
    }}
    .gf-nav-load > summary:focus-visible {{
      outline: 2px solid #fff;
      outline-offset: 2px;
      border-radius: 4px;
    }}
    .gf-nav-load-panel {{
      position: absolute;
      top: 100%;
      left: 0;
      margin-top: 6px;
      min-width: 11rem;
      padding: 6px 0;
      background: var(--gf-surface);
      border-radius: var(--gf-radius);
      box-shadow: var(--gf-shadow);
      display: flex;
      flex-direction: column;
      z-index: 20;
    }}
    .gf-nav-load-panel a {{
      color: var(--gf-text);
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 500;
    }}
    .gf-nav-load-panel a:hover {{
      background: #f1f3f4;
      text-decoration: none;
      color: var(--gf-primary);
    }}
    .gf-nav-load-panel a:focus-visible {{
      outline: 2px solid var(--gf-primary);
      outline-offset: -2px;
    }}
    .gf-load-section-title {{
      font-size: 12px;
      font-weight: 500;
      color: var(--gf-muted);
      text-transform: lowercase;
      margin: 16px 0 6px;
      letter-spacing: 0.04em;
    }}
    .gf-load-section-title:first-of-type {{ margin-top: 0; }}
    .gf-link-list--nested {{ margin-top: 4px; }}
    .gf-main {{ padding: 24px 16px 48px; }}
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
    .muted {{ color: var(--gf-muted); font-size: 13px; }}
    .gf-code {{
      background: #f1f3f4;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.9em;
      font-family: ui-monospace, monospace;
    }}
    .gf-link {{
      color: var(--gf-primary);
      text-decoration: none;
      font-weight: 500;
    }}
    .gf-link:hover {{ text-decoration: underline; }}
    .gf-link-list {{ margin: 8px 0 0; padding-left: 20px; }}
    .gf-link-list li {{ margin: 8px 0; }}
    .gf-tab-sync-actions {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 16px 0; }}
    .gf-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 0 20px;
      font-family: inherit;
      font-size: 14px;
      font-weight: 500;
      border-radius: 4px;
      cursor: pointer;
      border: none;
      transition: background .15s;
    }}
    .gf-btn:disabled {{ opacity: 0.6; cursor: not-allowed; }}
    .gf-btn-primary {{
      background: var(--gf-primary);
      color: #fff;
      box-shadow: 0 1px 2px rgba(60,64,67,.3);
    }}
    .gf-btn-primary:hover:not(:disabled) {{ background: var(--gf-primary-hover); }}
    .gf-btn-secondary {{
      background: #3740a3;
      color: #fff;
      box-shadow: 0 1px 2px rgba(60,64,67,.3);
    }}
    .gf-btn-secondary:hover:not(:disabled) {{ background: #2c347f; }}
    .gf-btn:focus-visible {{ outline: 2px solid var(--gf-primary); outline-offset: 2px; }}
    .gf-sync-result {{ margin-top: 16px; font-size: 13px; }}
    .gf-sync-err {{
      border-left: 4px solid var(--gf-error);
      background: #fce8e6;
      padding: 12px 16px;
      border-radius: 0 var(--gf-radius) var(--gf-radius) 0;
      color: var(--gf-text);
      margin: 12px 0;
    }}
    .gf-sync-meta {{ margin: 8px 0; color: var(--gf-muted); }}
    .gf-b-last-panel {{
      margin: 16px 0;
      padding: 14px 16px;
      background: #f3e5f5;
      border: 1px solid #ce93d8;
      border-radius: var(--gf-radius);
    }}
    .gf-b-last-panel--muted {{
      background: #f8f9fa;
      border-color: var(--gf-border);
    }}
    .gf-b-last-panel__title {{
      margin: 0 0 10px;
      font-size: 15px;
      font-weight: 600;
      color: var(--gf-text);
    }}
    .gf-b-last-sub {{
      margin: 0 0 12px;
      font-size: 13px;
      line-height: 1.45;
    }}
    .gf-b-last-panel dl {{
      margin: 0;
      display: grid;
      grid-template-columns: 10rem 1fr;
      gap: 8px 12px;
      font-size: 13px;
      align-items: start;
    }}
    .gf-b-last-panel dt {{
      margin: 0;
      color: var(--gf-muted);
      font-weight: 500;
    }}
    .gf-b-last-panel dd {{
      margin: 0;
      word-break: break-word;
    }}
    .gf-b-last-warn {{
      margin: 12px 0 0;
      padding: 8px 10px;
      font-size: 13px;
      background: #fff8e1;
      border-left: 3px solid #f9ab00;
      border-radius: 0 var(--gf-radius) var(--gf-radius) 0;
      color: var(--gf-text);
    }}
    .gf-table-wrap {{
      overflow: auto;
      margin: 12px 0;
      border: 1px solid var(--gf-border);
      border-radius: var(--gf-radius);
    }}
    .gf-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .gf-table th, .gf-table td {{
      padding: 8px 12px;
      text-align: left;
      border-bottom: 1px solid var(--gf-border);
      vertical-align: top;
    }}
    .gf-table th {{
      background: #f8f9fa;
      font-weight: 500;
      color: var(--gf-muted);
    }}
    .gf-debug-pre {{
      margin: 12px 0 0;
      padding: 12px 14px;
      font-size: 12px;
      line-height: 1.45;
      font-family: ui-monospace, monospace;
      background: #f8f9fa;
      border: 1px solid var(--gf-border);
      border-radius: var(--gf-radius);
      overflow: auto;
      max-height: 420px;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .gf-debug-section-title {{
      margin: 20px 0 6px;
      font-size: 13px;
      font-weight: 600;
      color: var(--gf-muted);
    }}
    .gf-long-task-progress {{
      margin: 12px 0 16px;
      padding: 14px 16px;
      background: #e8f0fe;
      border: 1px solid #aecbfa;
      border-radius: var(--gf-radius);
      font-size: 13px;
      color: var(--gf-text);
    }}
    .gf-long-task-progress[hidden] {{
      display: none !important;
    }}
    .gf-long-task-progress__title {{
      font-weight: 600;
      margin: 0 0 6px;
    }}
    .gf-long-task-progress__timer {{
      font-family: ui-monospace, monospace;
      font-size: 14px;
      margin: 0 0 8px;
      color: var(--gf-primary);
    }}
    .gf-long-task-progress__hint {{
      margin: 0;
      color: var(--gf-muted);
      font-size: 12px;
      line-height: 1.45;
    }}
    .gf-long-task-progress__detail {{
      margin: 10px 0 0;
      padding-top: 8px;
      border-top: 1px solid rgba(103, 58, 183, 0.2);
      font-size: 12px;
      color: var(--gf-text);
      line-height: 1.5;
      white-space: pre-wrap;
      font-family: ui-monospace, monospace;
    }}
    .gf-progress-bar {{
      height: 10px;
      background: rgba(103, 58, 183, 0.12);
      border-radius: 5px;
      overflow: hidden;
      margin: 10px 0 4px;
    }}
    .gf-progress-bar__fill {{
      height: 100%;
      width: 0%;
      min-width: 0;
      background: linear-gradient(90deg, var(--gf-primary), #9575cd);
      border-radius: 5px;
      transition: width 0.25s ease;
    }}
    .gf-progress-bar__label {{
      font-size: 12px;
      color: var(--gf-muted);
      margin: 0 0 2px;
    }}
    .gf-quote-filter-headline {{
      margin: 16px 0 10px;
      padding: 14px 18px;
      background: #e8f0fe;
      border: 1px solid #aecbfa;
      border-radius: var(--gf-radius);
      font-size: 1.35rem;
      font-weight: 600;
      color: #1967d2;
      line-height: 1.35;
      letter-spacing: 0.02em;
    }}
    .gf-quote-filter-headline[hidden] {{
      display: none !important;
    }}
  </style>
</head>
<body class="gf-page">
  <header class="gf-header">
    <div class="gf-header__inner">
      <span class="gf-header__brand">{html.escape(_DEBUG_BRAND)}</span>
      {nav}
    </div>
  </header>
  <main class="gf-main">
    <article class="gf-card">
      <h1 class="gf-title">{html.escape(title)}</h1>
      {body}
    </article>
  </main>
</body>
</html>
"""
    return HTMLResponse(page, headers=dict(_NO_CACHE))


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await listeners.run_startup()
    yield
    await listeners.run_shutdown()


app = FastAPI(title=_DEBUG_BRAND, version="0.1.0", lifespan=_lifespan)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse | PlainTextResponse:
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)

    tb_str = "".join(traceback.format_exception(exc)).strip()
    detail = f"{type(exc).__name__}: {exc}"
    if str(request.url.path).startswith("/api/"):
        payload: dict[str, object] = {
            "detail": detail,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        if _expose_api_error_traceback():
            payload["traceback"] = tb_str[-12000:] if len(tb_str) > 12000 else tb_str
        return JSONResponse(status_code=500, content=payload)

    body = detail
    if _expose_api_error_traceback() and tb_str:
        body = detail + "\n\n" + (tb_str[-6000:] if len(tb_str) > 6000 else tb_str)
    return PlainTextResponse(
        body,
        status_code=500,
        media_type="text/plain; charset=utf-8",
    )


_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.is_dir():
    app.mount(
        "/static",
        StaticFiles(directory=str(_static_dir)),
        name="static",
    )
app.include_router(sheet_refresh_router)
app.include_router(sheet_sync_router)
app.include_router(load_routes_router)


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    links = (
        '<p class="muted">v3 壳页面；主导航与下列链接均为无查询参数的干净 URL。</p>'
        '<p class="gf-load-section-title">load</p>'
        '<ul class="gf-link-list gf-link-list--nested">'
        '<li><a class="gf-link" href="/tab/quote">quote</a></li>'
        '<li><a class="gf-link" href="/tab/order">order</a></li>'
        '<li><a class="gf-link" href="/tab/complete">complete</a></li>'
        '<li><a class="gf-link" href="/tab/cancel">cancel</a></li>'
        "</ul>"
        '<p class="gf-load-section-title">Core API</p>'
        '<ul class="gf-link-list gf-link-list--nested">'
        '<li><a class="gf-link" href="/api/core/load/tab-rows?tab=quote">GET /api/core/load/tab-rows</a>（只读 <code class="gf-code">load</code>，与 Sheet 无关；必填 <code class="gf-code">tab</code>）</li>'
        '<li><a class="gf-link" href="/debug/clear-load">清空全部 load</a>（调试页，勿用地址栏 GET；须 <code class="gf-code">POST</code> + <code class="gf-code">confirm=DELETE_ALL_LOAD</code>）</li>'
        '<li><a class="gf-link" href="/api/core/sheet/refresh">GET /api/core/sheet/refresh</a>（Sheet 刷新 JSON）</li>'
        '<li><a class="gf-link" href="/sheet/merge">四表合并</a>（预览 + 可选写入 <code class="gf-code">V2_DB_PATH</code>）</li>'
        '<li><a class="gf-link" href="/api/core/sheet/sync-load">POST /api/core/sheet/sync-load</a>（单 tab 预览；四表加 <code class="gf-code">apply=true</code> 写库）</li>'
        '<li>POST <code class="gf-code">/api/core/sheet/merge-refresh</code>（四表合并、可选 Gemini、upsert；可选 <code class="gf-code">clear_quote=true</code> 先删本来源 quote 行；见 <a class="gf-link" href="/docs">/docs</a>）</li>'
        '<li><a class="gf-link" href="/docs">OpenAPI /docs</a></li>'
        "</ul>"
        '<p class="gf-load-section-title">其它</p>'
        '<ul class="gf-link-list gf-link-list--nested">'
        '<li><a class="gf-link" href="/blank">blank</a></li>'
        "</ul>"
    )
    return _render_layout(_DEBUG_BRAND, links)


@app.get("/blank", response_class=HTMLResponse)
def blank_page() -> HTMLResponse:
    return _render_layout("Blank", "")


@app.get("/debug/sheet-ai", response_class=HTMLResponse)
def debug_sheet_ai_page() -> HTMLResponse:
    body = (
        '<p class="muted">每次查询会<strong>重新从 Google Sheet 拉取</strong>四表数据，按顺序 '
        "<strong>cancel → complete → order → quote</strong> 在 <strong>B 列非空</strong> 的行中匹配 "
        "<strong>C 列</strong> EW 号。quote 表的 <code class=\"gf-code\">status</code> 使用 "
        "<strong>P 列是否非空</strong> 规则，与「四表合并」中 B 尾批量切分状态<strong>可能不一致</strong>。</p>"
        '<p class="muted"><strong>仅 prompt</strong>：勾选后不调 Gemini，也不要求 '
        "<code class=\"gf-code\">V3_SHEET_ROW_AI_ENABLED</code>。</p>"
        '<div class="gf-tab-sync-actions" style="flex-wrap:wrap">'
        '<label class="muted" style="display:flex;align-items:center;gap:8px">'
        "EW 单号 "
        '<input type="text" id="debug-sheet-ai-ew" '
        'style="min-width:12rem;padding:8px 10px;border:1px solid var(--gf-border);border-radius:4px;font:inherit"'
        ' placeholder="如 ew12345" />'
        "</label>"
        '<label class="muted" style="display:flex;align-items:center;gap:6px">'
        '<input type="checkbox" id="debug-sheet-ai-prompt-only" /> 仅 prompt'
        "</label>"
        '<button type="button" class="gf-btn gf-btn-primary" id="debug-sheet-ai-btn">'
        "查询</button>"
        '<span id="debug-sheet-ai-status" class="muted"></span>'
        "</div>"
        '<div id="debug-sheet-ai-err"></div>'
        '<p class="gf-debug-section-title">给 AI 的 prompt</p>'
        '<pre id="debug-sheet-ai-prompt" class="gf-debug-pre" aria-live="polite"></pre>'
        '<p class="gf-debug-section-title">AI 返回与解析</p>'
        '<pre id="debug-sheet-ai-response" class="gf-debug-pre" aria-live="polite"></pre>'
        '<p><a class="gf-link" href="/">返回 Home</a></p>'
        f"<script>{_DEBUG_SHEET_AI_SCRIPT}</script>"
    )
    return _render_layout("调试刷新 Sheet（AI）", body)


@app.get("/debug/sam-sheet", response_class=HTMLResponse)
def debug_sam_sheet_page() -> HTMLResponse:
    body = (
        '<p class="muted">点击<strong>刷新</strong>：<strong>拉取四表</strong>（Sheets API）→ '
        "<strong>合并校验</strong> → <strong>upsert</strong> 写入 <code class=\"gf-code\">V2_DB_PATH</code>。"
        " <strong>不调 Gemini</strong>（<code class=\"gf-code\">merge-refresh?ai=false</code>）。"
        " Gemini 单行调试仍用「调试刷新 Sheet（AI）」。</p>"
        '<div class="gf-tab-sync-actions" style="flex-wrap:wrap;align-items:center;gap:10px">'
        '<button type="button" class="gf-btn gf-btn-primary" id="sam-sheet-refresh-btn">刷新</button>'
        '<label class="muted" style="display:flex;align-items:center;gap:6px">'
        '<input type="checkbox" id="sam-sheet-clear-quote" /> '
        "入库前先删本来源 quote 行"
        "</label>"
        '<span id="sam-sheet-merge-status" class="muted"></span>'
        "</div>"
        '<div id="sam-sheet-long-progress" class="gf-long-task-progress" hidden role="status" aria-live="polite">'
        '<div class="gf-long-task-progress__title" id="sam-sheet-progress-title">处理中…</div>'
        '<div class="gf-long-task-progress__timer" id="sam-sheet-progress-timer">已等待 0:00</div>'
        '<p id="sam-sheet-progress-bar-label" class="gf-progress-bar__label" aria-hidden="true"></p>'
        '<div class="gf-progress-bar" role="presentation">'
        '<div class="gf-progress-bar__fill" id="sam-sheet-progress-bar-fill" '
        'role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" '
        'style="width:0%"></div>'
        "</div>"
        '<p class="gf-long-task-progress__hint">未启用 AI 时服务端不更新 <code class=\"gf-code\">long-task-progress</code>；'
        " 仅显示已等待时间，请耐心等 POST 结束。</p>"
        '<div class="gf-long-task-progress__detail" id="sam-sheet-progress-detail"></div>'
        "</div>"
        '<div id="sam-sheet-merge-out" class="gf-sync-result" aria-live="polite"></div>'
        f"<script>{_SAM_SHEET_REFRESH_SCRIPT}</script>"
    )
    return _render_layout("导入 Sam sheet", body)


_CLEAR_LOAD_PAGE_SCRIPT = r"""
(function () {
  var btn = document.getElementById("clear-load-btn");
  var out = document.getElementById("clear-load-out");
  if (!btn || !out) return;
  btn.addEventListener("click", function () {
    if (
      !confirm(
        "将删除当前 V2_DB_PATH 内全部 load 行，并清空 load_validation_log、load_sync_log；不可恢复。确定？"
      )
    ) {
      return;
    }
    btn.disabled = true;
    out.textContent = "请求中…";
    fetch("/api/core/load/clear-all?confirm=DELETE_ALL_LOAD", {
      method: "POST",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        return r.json().then(function (j) {
          return { ok: r.ok, status: r.status, body: j };
        });
      })
      .then(function (x) {
        if (!x.ok) {
          var d = x.body;
          var msg =
            typeof d === "object" && d && d.detail
              ? String(d.detail)
              : "HTTP " + x.status;
          out.textContent = msg;
          return;
        }
        out.textContent = JSON.stringify(x.body, null, 2);
      })
      .catch(function (e) {
        out.textContent = e && e.message ? e.message : String(e);
      })
      .finally(function () {
        btn.disabled = false;
      });
  });
})();
"""


@app.get("/debug/clear-load", response_class=HTMLResponse)
def debug_clear_load_page() -> HTMLResponse:
    body = (
        '<p class="muted">本页用 <strong>POST</strong> 调用接口；仅在地址栏打开本 URL <strong>不会</strong>删数据。</p>'
        '<p class="muted">若此前用浏览器直接访问带参数链接：那是 <strong>GET</strong>，FastAPI 会 <strong>405 Method Not Allowed</strong>，属于正常现象。</p>'
        '<div class="gf-tab-sync-actions">'
        '<button type="button" class="gf-btn gf-btn-primary" id="clear-load-btn">'
        "清空全部 load（需确认）</button>"
        "</div>"
        '<pre id="clear-load-out" class="gf-debug-pre" aria-live="polite"></pre>'
        '<p><a class="gf-link" href="/">返回 Home</a></p>'
        f"<script>{_CLEAR_LOAD_PAGE_SCRIPT}</script>"
    )
    return _render_layout("清空全部 load", body)


@app.get("/sheet/merge", response_class=HTMLResponse)
def sheet_merge_page() -> HTMLResponse:
    body = (
        '<p class="muted">按顺序 <strong>cancel → complete → order → quote</strong> 合并；quote 仅在单号未出现在前三表时导入，并在剩余行上按 B 列 span 底部比例切分 '
        "<code class=\"gf-code\">pending_quote</code> / "
        "<code class=\"gf-code\">quote_no_customer_response</code>。"
        " 写入使用 v2 同名 SQLite（<code class=\"gf-code\">V2_DB_PATH</code>），并遵守与 Sheet 导入相同的运维字段防覆盖规则。"
        " 默认<strong>不调 Gemini</strong>：仅四表合并并统计唯一 EW 条数（预览不写库；写入只 upsert Sheet 形状字段）。"
        " 勾选「Gemini 补缺」后才会并发调用 Gemini（需 <code class=\"gf-code\">V3_SHEET_ROW_AI_ENABLED</code> 与 API Key）。</p>"
        '<div class="gf-tab-sync-actions" style="flex-wrap:wrap;align-items:flex-start;gap:12px">'
        '<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">'
        '<button type="button" class="gf-btn gf-btn-primary" id="sheet-merge-preview-btn">'
        "四表合并预览</button>"
        '<button type="button" class="gf-btn gf-btn-secondary" id="sheet-merge-apply-btn">'
        "写入数据库</button>"
        '<label class="muted" style="display:flex;align-items:center;gap:6px">'
        '<input type="checkbox" id="sheet-merge-ai" /> '
        "Gemini 补缺"
        "</label>"
        '<label class="muted" style="display:flex;align-items:center;gap:6px">'
        '<input type="checkbox" id="sheet-merge-ai-overwrite" /> '
        "AI 覆盖非空字段"
        "</label>"
        '<span id="sheet-merge-status" class="muted"></span>'
        "</div>"
        "</div>"
        '<div id="sheet-merge-long-progress" class="gf-long-task-progress" hidden role="status" aria-live="polite">'
        '<div class="gf-long-task-progress__title" id="sheet-merge-progress-title">正在处理…</div>'
        '<div class="gf-long-task-progress__timer" id="sheet-merge-long-progress-timer">已等待 0:00</div>'
        '<p class="gf-long-task-progress__hint">未勾选 Gemini 时：仅拉表与合并，预览不写库。'
        "勾选 Gemini 时：服务端会分批请求 API，行数多时可能需数分钟。"
        "长时间卡住时检查终端是否在 <code class=\"gf-code\">Reloading</code>（保存文件会打断请求）。</p>"
        '<div class="gf-long-task-progress__detail" id="sheet-merge-progress-detail"></div>'
        "</div>"
        '<div id="sheet-merge-result" class="gf-sync-result" aria-live="polite"></div>'
        '<p><a class="gf-link" href="/">返回 Home</a></p>'
        f"<script>{_merge_sync_client_script()}</script>"
    )
    return _render_layout("四表合并", body)


def _tab_db_readonly_section(tab_key: str) -> str:
    """各 load Tab 公用：SQLite load 只读列表（不访问 Sheet）。"""
    order_filter = ""
    if tab_key == "order":
        order_filter = (
            '<label class="muted" style="display:flex;align-items:center;gap:8px">'
            "order 状态 "
            '<select id="load-db-order-state" style="font:inherit;padding:6px 8px;border-radius:4px;border:1px solid var(--gf-border)">'
            '<option value="all">全部</option>'
            '<option value="waiting">waiting（ordered）</option>'
            '<option value="found">found（carrier_assigned）</option>'
            '<option value="transit">transit（picked）</option>'
            "</select>"
            "</label>"
        )
    t_esc = html.escape(tab_key)
    filter_row = ""
    if order_filter:
        filter_row = (
            '<div class="gf-tab-sync-actions" style="flex-wrap:wrap;align-items:center;gap:8px">'
            f"{order_filter}"
            "</div>"
        )
    return (
        '<p class="gf-debug-section-title">数据库（只读）</p>'
        f"{filter_row}"
        f'<div id="load-db-root" data-tab-key="{t_esc}"></div>'
        '<p id="load-db-meta" class="muted"></p>'
        '<div id="load-db-pager" class="gf-tab-sync-actions" style="flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:10px">'
        '<button type="button" class="gf-btn gf-btn-secondary" id="load-db-page-prev">上一页</button>'
        '<span id="load-db-page-info" class="muted"></span>'
        '<button type="button" class="gf-btn gf-btn-secondary" id="load-db-page-next">下一页</button>'
        '<button type="button" class="gf-btn gf-btn-primary" id="load-db-ai-page-btn" title="仅本页：对未打 AI 时间戳的行调 Gemini，可能较慢">'
        "本页 AI 补缺</button>"
        '<label class="muted" style="display:flex;align-items:center;gap:6px">每页'
        '<select id="load-db-page-size" style="font:inherit;padding:6px 8px;border-radius:4px;border:1px solid var(--gf-border)">'
        "<option value=\"20\" selected>20</option>"
        "<option value=\"50\">50</option>"
        "<option value=\"100\">100</option>"
        "<option value=\"200\">200</option>"
        "</select></label>"
        "</div>"
        '<div id="load-db-table-wrap" class="gf-table-wrap"></div>'
    )


def _tab_page_body(tab_key: str) -> str:
    """load Tab 页正文：SQLite 只读列表；非 quote 另有 merge-refresh。"""
    db_sec = _tab_db_readonly_section(tab_key)
    db_script = '<script src="/static/js/tab_db_rows.js" defer></script>'
    if tab_key == "quote":
        return db_sec + '<p><a class="gf-link" href="/">返回 Home</a></p>' + db_script
    return (
        db_sec
        + '<p class="gf-debug-section-title">Sheet → 数据库</p>'
        + f'<p class="muted">当前入口：<strong>{html.escape(tab_key)}</strong>。'
        + " 下方会<strong>拉取四张表</strong>、合并后 upsert（与导航名仅作分类）。</p>"
        + '<div class="gf-tab-sync-actions" style="flex-wrap:wrap;align-items:center;gap:12px">'
        + '<button type="button" class="gf-btn gf-btn-primary" id="sheet-db-merge-refresh-btn">'
        + "从 Sheet 刷新并入库</button>"
        + '<label class="muted" style="display:flex;align-items:center;gap:6px">'
        + '<input type="checkbox" id="sheet-db-merge-clear-quote" /> '
        + "入库前先删本来源 quote 行"
        + "</label>"
        + '<label class="muted" style="display:flex;align-items:center;gap:6px">'
        + '<input type="checkbox" id="sheet-db-merge-ai" checked /> '
        + "Gemini 补缺"
        + "</label>"
        + '<label class="muted" style="display:flex;align-items:center;gap:6px">'
        + '<input type="checkbox" id="sheet-db-merge-ai-overwrite" /> '
        + "AI 覆盖非空字段"
        + "</label>"
        + "</div>"
        + '<div id="sheet-db-merge-progress" class="gf-long-task-progress" hidden role="status" aria-live="polite">'
        + '<div class="gf-long-task-progress__title">正在处理…</div>'
        + '<div class="gf-long-task-progress__timer" id="sheet-db-merge-progress-timer">已等待 0:00</div>'
        + '<p class="gf-long-task-progress__hint">未勾选 Gemini 时服务端不更新细进度；仅显示等待时间。</p>'
        + '<div class="gf-long-task-progress__detail" id="sheet-db-merge-progress-detail"></div>'
        + "</div>"
        + '<p><a class="gf-link" href="/">返回 Home</a></p>'
        + db_script
        + '<script src="/static/js/tab_merge_refresh.js" defer></script>'
    )


@app.get("/tab/{tab_key}", response_class=HTMLResponse)
def tab_page(tab_key: str) -> HTMLResponse:
    if tab_key not in TAB_KEYS:
        body = (
            '<p class="muted">无效的 tab。</p>'
            '<p><a class="gf-link" href="/">返回 Home</a></p>'
        )
        return _render_layout("Tab 不存在", body)
    return _render_layout(f"Tab: {tab_key}", _tab_page_body(tab_key))
