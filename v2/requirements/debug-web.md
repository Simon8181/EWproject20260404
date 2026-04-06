# 需求：Debug 调试 Web（FastAPI）

> 路径：`v2/requirements/debug-web.md`

## 目的

为开发与运维提供本地 HTTP 入口：查看各 Sheet 对应的 `load` 子集、触发导入与地址验证、查看导入日志与校验任务进度；不要求对外网开放生产级安全模型（默认本机调试）。

## 范围

- **在内**：`GET /debug`、`GET /debug/tab/{tab_key}`、总览统计、操作按钮（清空 load、触发导入、全量/按 tab 验证）、验证进度页与 JSON API。
- **不在内**：正式业务前端、鉴权会话（当前无登录）；运营表单若关闭见 `ops-fields.md`。

## 功能需求

1. **导航**：
   - Debug 首页链到 `quote` / `order` / `complete` / `cancel` 四个 tab 页路径与 `text1` 流程一致。
   - 「**AI 收集报价数据**」链到 `GET /quote`（见 `quote-ai-collect.md`），**新标签**打开，当前 Debug 页保留。
2. **总览**：展示 load 行数、导入锁开关、环境名、最近导入日志列表；可选轮询 `GET /debug/api/status` 刷新数字。
3. **清空 load**：`POST /debug/actions/clear-load` 清空 `load` 并解除导入锁（逻辑以 `db.clear_load_only` 为准）。
4. **导入**：`POST /debug/actions/import` 调用 `run_one_time_import`（遵守锁与 prod 约束）。
5. **地址验证**：
   - 全量：`POST /debug/actions/validate-address`，异步任务，跳转进度页。
   - 按 tab：`POST /debug/actions/validate-address-tab`，可带 `load_state`（与 order 筛选配合，见 `order-filters.md`）。
6. **任务进度**：`GET /debug/validation/{job_id}` HTML；`GET /debug/api/validation-job/{job_id}` JSON；任务并发互斥（已有 running 则拒绝）。
7. **Tab 列表（quote / order / complete / cancel）**：
   - **quote tab 清空**：`POST /debug/actions/clear-load-quote-tab`，仅删除 `source_tabs` 含 `quote` 的 `load` 行（同 `db.clear_load_quote_only`），成功后回到 `/debug/tab/quote` 并提示条数。
   - **折叠行**：每条 load 默认一行；表头为「展开列 + **单号 · 起止（City, ST ZIP）**」。收起时第二格为**同一行**文字：`单号 · 起点 → 终点`；起点/终点各为 **`City, ST ZIP`**（美国常见地址 best-effort 从 `origin_normalized`/`dest_normalized` 解析，缺省回退 `ship_from_raw`/`ship_to_raw`）。解析不到则仅显示单号。
   - **展开**：点击摘要行（或键盘 Enter/空格）展开下一行，以 **定义列表（dl）**展示完整字段（原宽表明细：地址、校验、AI、运营列等）。
   - **提货 ETA 已过**：仍未 `picked` 等终态时，摘要行保持浅橙高亮（与 `text1` / 附录 C 列表提示一致）。
   - **实现提示**：`_city_zip_state_from_address`、`_route_summary_collapsed`、`_load_tab_detail_dl`、`_load_table_interaction_script()` 均在 `debug_web.py`。

## 非功能约束

- 响应头建议 `no-store`，避免调试数据缓存混淆。
- 端口与 host 由启动命令指定（README 默认 `127.0.0.1:8010`）。

## 实现参考

- 代码：`v2/app/debug_web.py`、`v2/app/validation_runner.py`、`v2/app/settings.py`

## 验收要点

- 四 tab 可打开；order 筛选与 SQL 行为见 `order-filters.md`。
- 导入/清空/验证按钮在默认环境下可完成闭环（依赖 Maps/AI 密钥时按环境而定）。
- 列表收起时单号与「City, ST ZIP → City, ST ZIP」同列单行可见；展开后可见全部键值。
