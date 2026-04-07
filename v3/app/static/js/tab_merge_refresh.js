/**
 * Tab 页「从 Sheet 刷新并入库」：调用 POST /api/core/sheet/merge-refresh，
 * 可选轮询 GET /api/core/sheet/long-task-progress（仅开启 Gemini 时服务端有进度）。
 *
 * 依赖 DOM：#sheet-db-merge-refresh-btn、#sheet-db-merge-clear-quote、#sheet-db-merge-ai、
 * #sheet-db-merge-ai-overwrite、
 * #sheet-db-merge-progress*（见 web.py tab_page）。不传 max_rows，服务端按表读全。
 */
(function () {
  "use strict";

  var API_MERGE_REFRESH = "/api/core/sheet/merge-refresh";
  var API_PROGRESS = "/api/core/sheet/long-task-progress";

  var btn = document.getElementById("sheet-db-merge-refresh-btn");
  var chkClear = document.getElementById("sheet-db-merge-clear-quote");
  var chkAi = document.getElementById("sheet-db-merge-ai");
  var chkOw = document.getElementById("sheet-db-merge-ai-overwrite");
  var prog = document.getElementById("sheet-db-merge-progress");
  var progTimer = document.getElementById("sheet-db-merge-progress-timer");
  var progDetail = document.getElementById("sheet-db-merge-progress-detail");
  if (!btn) return;

  var tick = null;
  var pollTick = null;

  function pad2(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function renderServerProgress(p) {
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
      else m += "（合并进行中，合计行数稍晚更新）";
      lines.push(m);
    } else if (p.phase === "validate") {
      lines.push(
        "服务端：合并行校验与统计已完成，准备多线程 Gemini…（已合并 " +
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
      var ews = p.ai_formatting_ews || [];
      if (ews.length) {
        lines.push(
          "当前请求中的 EW：" + ews.map(function (q) { return String(q); }).join(", ")
        );
      }
      if ((p.ai_formatting_ews_more || 0) > 0) {
        lines.push("… 另有 " + p.ai_formatting_ews_more + " 个未列出（并发多批）");
      }
    } else if (p.phase === "persist") lines.push("服务端：写入 SQLite…");
    else if (p.phase === "done") lines.push("服务端：已完成");
    progDetail.textContent = lines.join("\n");
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
  }

  function startDbMergeProgress(withPoll) {
    if (!prog || !progTimer) return;
    prog.hidden = false;
    var t0 = Date.now();
    progTimer.textContent = "已等待 0:00";
    if (tick) clearInterval(tick);
    tick = setInterval(function () {
      var s = Math.floor((Date.now() - t0) / 1000);
      progTimer.textContent =
        "已等待 " + Math.floor(s / 60) + ":" + pad2(s % 60);
    }, 500);
    if (withPoll) startProgressPoll();
    else if (progDetail) progDetail.textContent = "服务端处理中（未启用 AI 时无细进度）…";
  }

  function stopDbMergeProgress() {
    stopProgressPoll();
    if (tick) {
      clearInterval(tick);
      tick = null;
    }
    if (prog) prog.hidden = true;
  }

  function confirmLines() {
    var clearFirst = !!(chkClear && chkClear.checked);
    var useAi = chkAi && chkAi.checked;
    var useOw = chkOw && chkOw.checked;
    var lines = [
      "流程：从 Google Sheet 拉四表 → 合并与行级校验 →" +
        (useAi ? " 多线程 Gemini 补缺 →" : "") +
        " upsert 写入库（有则更新、无则新增）。每表按工作表读全；quote 连续拉取受 yaml 总上限约束。",
      "",
      clearFirst
        ? "将先删除数据库中：「来源含 quote」且「data_source」与当前 yaml 一致的 load 行，再写入。"
        : "不会先整批删除：仅按 quote_no upsert。若需「先清空本来源 quote 再全量重灌」，请勾选「入库前先删…」。",
      "",
      "参数：Gemini 补缺：" +
        (useAi ? "是" : "否") +
        (useAi && useOw ? "（允许覆盖已有非空字段）" : "") +
        "。",
    ];
    if (useAi) {
      lines.push(
        "",
        "补缺需 V3_SHEET_ROW_AI_ENABLED 与 GEMINI_API_KEY；耗时与费用随行数增加。"
      );
    }
    lines.push("", "是否继续？");
    return lines.join("\n");
  }

  btn.addEventListener("click", function () {
    if (!confirm(confirmLines())) return;

    var clearFirst = !!(chkClear && chkClear.checked);
    var useAi = !!(chkAi && chkAi.checked);
    var useOw = !!(chkOw && chkOw.checked);

    var qs = new URLSearchParams();
    qs.set("clear_quote", clearFirst ? "true" : "false");
    qs.set("ai", useAi ? "true" : "false");
    qs.set("ai_overwrite", useOw ? "true" : "false");

    btn.disabled = true;
    startDbMergeProgress(useAi);

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
            msg = d.replace(/\s+/g, " ").trim();
            if (msg.length > 500) msg = msg.slice(0, 500) + "…";
            if (!msg) msg = "HTTP " + x.status;
          } else {
            msg = "HTTP " + x.status;
          }
          alert(msg);
          return;
        }
        location.reload();
      })
      .catch(function (e) {
        alert(e && e.message ? e.message : String(e));
      })
      .finally(function () {
        stopDbMergeProgress();
        btn.disabled = false;
      });
  });
})();
