# 「从 Sheet 刷新并入库」按钮 — 开发说明

面向维护 v3 Debug Tab 页上**一键从 Google Sheet 同步到 SQLite** 的前后端实现。

## 用户可见行为

四个 **`/tab/{quote|order|complete|cancel}`** 页顶格均为 **「数据库（只读）」**：分页列表来自 `GET /api/core/load/tab-rows`（SQLite `load`，与 Sheet 无关）。**仅非 quote** 的 Tab 在下方另有「**从 Sheet 刷新并入库**」→ `merge-refresh`。

1. **入口**：例如 `/tab/order`：先只读列表，再 Sheet 入库区；`/tab/quote` 仅有只读列表与返回 Home。
2. **控件（Sheet → 数据库，非 quote）**
   - **从 Sheet 刷新并入库**：主按钮。**不设 max_rows**：服务端对每表按工作表网格读全（分页）；quote 连续拉取仍受 `ai_sheet_rules.yaml` 总上限约束。
   - **Gemini 补缺**：默认勾选；关闭则 `ai=false`，不写库前不调 Gemini（仍执行删行、拉表、四表合并与写库）。
   - **AI 覆盖非空字段**：对应 `ai_overwrite=true`；默认关闭时仅填补空字段。
3. **确认框**：文案随当前选项变化（数据源删除规则、参数、API Key 提示）。
4. **长任务**：仅当勾选 Gemini 时，轮询 [`GET /api/core/sheet/long-task-progress`](../app/sheet_sync.py) 显示阶段（sheet / merge / ai / persist）。未启用 AI 时进度区仍显示等待计时与一句「无细进度」提示。
5. **成功**：整页 `location.reload()` 刷新列表。
6. **失败**：`alert` 展示 FastAPI 返回的 `detail` 或网络错误。

## 前端实现

| 资源 | 说明 |
|------|------|
| [`v3/app/static/js/tab_merge_refresh.js`](../app/static/js/tab_merge_refresh.js) | 独立 IIFE：事件绑定、Query 拼装、进度轮询、确认文案。 |
| [`v3/app/web.py`](../app/web.py) 中 `tab_page` | 各 Tab 挂载 `tab_db_rows.js`（只读列表）；非 quote 另挂 `tab_merge_refresh.js` 与入库控件、`.gf-long-task-progress`。 |
| FastAPI | `app.mount("/static", StaticFiles(...))` 指向 [`v3/app/static/`](../app/static/)。 |

修改交互时优先改 JS；若增加新查询参数，需同时改本文件、`tab_page` HTML（若有新控件）与后端 [`api_sheet_merge_refresh`](../app/sheet_sync.py)。

## 后端链路（与按钮对应）

`POST /api/core/sheet/merge-refresh?max_rows=&ai=&ai_overwrite=` → [`merge_refresh_clear_quote_then_apply`](../app/sheet_sync.py)：

1. 读 [`ai_sheet_rules.yaml`](../core/ai_sheet_rules.yaml) 中 `sheet.data_source`。
2. [`clear_load_quote_for_data_source`](../../v2/app/db.py)：`data_source` 非空则只删**本来源**且 `source_tabs` 含 `quote` 的 `load` 行；否则等同删全部 quote 来源行。
3. [`build_sync_load_preview`](../app/sheet_sync.py)`(apply=True, ...)`：拉四表 → 按 cancel→complete→order→quote 合并 → 可选并发 Gemini → [`_persist_merge_items`](../app/sheet_sync.py) 写入 `V2_DB_PATH` 对应库，并记 `load_sync_log`。

环境变量与规则详见 `ai_sheet_rules.yaml` 与 `sheet_row_ai`（`V3_SHEET_ROW_AI_ENABLED`、`GEMINI_API_KEY` 等）。

## 与「四表合并」页面的区别

- [`/sheet/merge`](../app/web.py) 使用另一段内联脚本（[`_merge_sync_client_script`](../app/web.py)），调用 `sync-load` 预览/写入，**不**执行「先删本来源 quote 行」。
- Tab 页按钮专门走 `merge-refresh`，**先删再全量合并写回**，与当前 Sheet 配置的数据来源严格对齐。

## 本地验证建议

1. 启动：`cd v3 && ./run_web.sh`（长任务可临时去掉 `--reload` 避免中断）。
2. 打开 `/tab/quote` 或非 quote Tab 的刷新并入库，跑通链路（需 Google Sheet 凭证与库路径）。
3. 开 AI 时观察进度轮询与终端日志；限流时可降低 `ai.refresh_context.parallel_batch_workers`。

## 修订记录

- 将原内联 ` _tab_merge_refresh_script()` 抽离为 `/static/js/tab_merge_refresh.js`；前端不再传 `max_rows`（默认读全表）；仍可在 API 上显式传 `max_rows` 做上限。
