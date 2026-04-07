/**
 * Tab 页「数据库（只读）」：GET /api/core/load/tab-rows
 * 翻页默认 ensure_ai=false（只读库，避免卡住）；「本页 AI 补缺」才 ensure_ai=true。
 */
(function () {
  "use strict";

  var API = "/api/core/load/tab-rows";
  var root = document.getElementById("load-db-root");
  var wrap = document.getElementById("load-db-table-wrap");
  var meta = document.getElementById("load-db-meta");
  var orderSel = document.getElementById("load-db-order-state");
  var btnPrev = document.getElementById("load-db-page-prev");
  var btnNext = document.getElementById("load-db-page-next");
  var btnAiPage = document.getElementById("load-db-ai-page-btn");
  var pageInfo = document.getElementById("load-db-page-info");
  var pageSizeSel = document.getElementById("load-db-page-size");
  if (!root || !wrap) return;

  var tabKey = (root.dataset.tabKey || "").trim();
  if (!tabKey) return;

  var currentPage = 1;
  var totalRows = 0;
  var loading = false;

  var COLS = [
    "quote_no",
    "status",
    "customer_name",
    "v3_sheet_ai_enriched_at",
    "source_tabs",
    "data_source",
    "updated_at",
    "validate_ok",
  ];

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function pageSize() {
    var n = parseInt(pageSizeSel && pageSizeSel.value, 10);
    return isFinite(n) && n > 0 ? n : 20;
  }

  function totalPages() {
    var ps = pageSize();
    return totalRows <= 0 ? 1 : Math.max(1, Math.ceil(totalRows / ps));
  }

  function setPagerDisabled(dis) {
    if (btnPrev) btnPrev.disabled = dis || currentPage <= 1;
    if (btnNext) btnNext.disabled = dis || currentPage >= totalPages();
    if (btnAiPage) btnAiPage.disabled = dis;
    if (pageSizeSel) pageSizeSel.disabled = dis;
    if (orderSel) orderSel.disabled = dis;
  }

  function syncPagerUi() {
    var tp = totalPages();
    if (currentPage > tp) currentPage = tp;
    if (currentPage < 1) currentPage = 1;
    if (pageInfo) {
      pageInfo.textContent =
        "第 " + currentPage + " / " + tp + " 页（共 " + totalRows + " 条）";
    }
    if (!loading) setPagerDisabled(false);
  }

  function renderTable(rows) {
    var th = COLS.map(function (c) {
      return "<th>" + esc(c) + "</th>";
    }).join("");
    var trs = rows
      .map(function (row) {
        var tds = COLS.map(function (c) {
          return "<td>" + esc(row[c]) + "</td>";
        }).join("");
        return "<tr>" + tds + "</tr>";
      })
      .join("");
    wrap.innerHTML =
      '<table class="gf-table"><thead><tr>' +
      th +
      "</tr></thead><tbody>" +
      (trs ||
        '<tr><td colspan="' +
          COLS.length +
          '" class="muted">无数据</td></tr>') +
      "</tbody></table>";
  }

  function loadRows(withEnsureAi) {
    var qs = new URLSearchParams();
    qs.set("tab", tabKey);
    qs.set("page", String(currentPage));
    qs.set("page_size", String(pageSize()));
    qs.set("ensure_ai", withEnsureAi ? "true" : "false");
    if (tabKey === "order" && orderSel) {
      var st = orderSel.value || "all";
      if (st !== "all") qs.set("load_state", st);
    }
    loading = true;
    setPagerDisabled(true);
    wrap.innerHTML = "";
    if (meta) {
      meta.textContent = withEnsureAi
        ? "加载中（本页 AI 可能需数十秒）…"
        : "加载中…";
    }

    fetch(API + "?" + qs.toString(), { headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.json().then(function (j) {
          return { ok: r.ok, status: r.status, body: j };
        });
      })
      .then(function (x) {
        loading = false;
        if (!x.ok) {
          var d = x.body;
          var msg =
            typeof d === "object" && d && d.detail
              ? String(d.detail)
              : "HTTP " + x.status;
          if (meta) meta.textContent = msg;
          totalRows = 0;
          syncPagerUi();
          return;
        }
        var data = x.body || {};
        var rows = data.rows || [];
        totalRows = typeof data.total === "number" ? data.total : rows.length;
        if (meta) {
          var em = "";
          var ea = data.ensure_ai;
          if (ea) {
            if (ea.ensure_ai_ran && (ea.ensure_ai_api_quote_nos || []).length) {
              em +=
                " Sheet 行 AI：本请求写回 " +
                ea.ensure_ai_api_quote_nos.length +
                " 条。";
            } else if (ea.ensure_ai_skipped === "ai_disabled") {
              em += " Sheet 行 AI：未启用环境变量。";
            } else if (
              (ea.ensure_ai_errors || []).length ||
              (ea.ensure_ai_sheet_note && String(ea.ensure_ai_sheet_note).trim())
            ) {
              em +=
                " Sheet-AI 提示：" +
                (ea.ensure_ai_sheet_note || "") +
                " " +
                (ea.ensure_ai_errors || []).join("; ");
            }
          }
          meta.textContent =
            "本页 " +
            rows.length +
            " 条；合计 " +
            totalRows +
            " 条。翻页仅读库；要补 AI 请点「本页 AI 补缺」（可能较慢）。库：" +
            (data.db_path || "") +
            em;
        }
        renderTable(rows);
        syncPagerUi();
      })
      .catch(function (e) {
        loading = false;
        if (meta) meta.textContent = e && e.message ? e.message : String(e);
        totalRows = 0;
        syncPagerUi();
      });
  }

  function goPage(p) {
    currentPage = p;
    loadRows(false);
  }

  if (orderSel) {
    orderSel.addEventListener("change", function () {
      currentPage = 1;
      loadRows(false);
    });
  }
  if (pageSizeSel) {
    pageSizeSel.addEventListener("change", function () {
      currentPage = 1;
      loadRows(false);
    });
  }
  if (btnPrev) {
    btnPrev.addEventListener("click", function () {
      if (currentPage > 1) goPage(currentPage - 1);
    });
  }
  if (btnNext) {
    btnNext.addEventListener("click", function () {
      if (currentPage < totalPages()) goPage(currentPage + 1);
    });
  }
  if (btnAiPage) {
    btnAiPage.addEventListener("click", function () {
      loadRows(true);
    });
  }

  loadRows(false);
})();
