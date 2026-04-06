# 需求：Google Sheet 导入与映射配置

> 路径：`v2/requirements/sheet-import.md`

## 目的

从只读 Google Sheet 多工作表汇总为本地 `load` 行，推导 `status` 与原始业务列；尊重 `text1` §2；支持 `text1` §4 的重导入不覆盖网页已维护的 `status`。

## 范围

- **在内**：`load_mapping.yaml` 解析、Sheets API 读数、A 列颜色、行合并优先级、`run_one_time_import`、导入锁、`load_sync_log`。
- **不在内**：入口复用（见 `import-once.md`、`debug-web.md`）。

## 功能需求

### 映射配置

1. **文件**：`v2/config/load_mapping.yaml`（路径可由 `settings` 指定）。
2. **字段**：每个 tab 含 `key`、`worksheet`、`data_start_row`、`key_column_letter`、`use_color_status`、`color_status_map`、`status`（fixed/keyword）、`trouble_case` 等（见 `mapping.py`）。
3. **spreadsheet_id**：支持完整 URL 或裸 ID，解析为 API 用 ID。

### 导入列

仅处理已约定列（如 A–U 中声明的子集），未声明列不写入 `load`（详见 README / 配置注释）。

### D/E/F 备注派生字段（规则解析）

列 **D、E、F** 仍写入 `note_d_raw`、`note_e_raw`、`note_f_raw`。每次导入在写库前由 [`note_def_extract.parse_def_notes`](../app/note_def_extract.py) **重算**下列派生列（与 Sheet 备注同步；非结构化文本时可能留空）：

| `load` 列 | 含义 |
|-----------|------|
| `broker` | 经纪 / Broker 名称等 |
| `actual_driver_rate_raw` | 实际给司机价格（与 U 列 `driver_rate_raw` 区分） |
| `carriers` | MC/DOT 编号、3PL 单号等承运侧标识（自由文本） |

解析策略：优先识别中英文标签（如 Broker/经纪、Rate/价格、MC、3PL/单号等）；无标签时在三格均非空情况下按金额 / MC 样貌 / 余下格略启发式补缺。详见实现与单测 `tests/test_note_def_extract.py`。

### 状态规则（须与 `text1` §2 一致）

1. **A 列红** → `ordered`；**A 列绿** → `carrier_assigned`（禁止绿映射到 `ready_to_pick`）。
2. **仅 quote tab、且无 A 列色**：`P` 与 `U` 皆空 → `pending_quote`；任一非空 → `quoted`。
3. **多 tab 同一 `quote_no`**：按 `STATUS_PRIORITY` 合并为更高阶段状态（含 `cancel` 等终态优先级）。

### 导入锁与重导

1. **首次导入**：默认写入 `import_lock.initial_load_done`；未完成前可重复导入语义由调用方控制。
2. **`force_reimport`**：允许跳过锁再次导入；**生产环境禁止**（由 `app_env` 判断）。
3. **`ON CONFLICT`**：若库中该行已被网页真相源维护（任一下列非空或非默认：`pickup_eta`、`delivery_eta`、`pickup_tz`、`delivery_tz`、`carrier_note`、`cargo_ready`、`operator_updated_at`、`operator_updated_by`），则**不**用本次 Sheet 推导结果覆盖 `status`；其余列按 SQL 更新。

## 可选：导入后 AI 补缺（Gemini）

> 实现：`sheet_import_ai.py`；在确定性映射与多 tab 合并**之后**、写库**之前**执行。

1. **总开关**：环境变量 `AI_SHEET_IMPORT_ENABLED=1`（默认关闭）；且需可用 `GEMINI_API_KEY`（或 `V2_GEMINI_API_KEY`）。模型与地址 AI 相同（`AI_ADDRESS_MODEL` / 默认 `gemini-2.5-flash`）。
2. **按 tab 配置**：在 [`load_mapping.yaml`](v2/config/load_mapping.yaml) 某 tab 下可增加可选块 `ai_import_parse`：
   - `enabled: true|false`
   - `rules_text:` 多行规则（自然语言，供模型遵循）
   - `rules_file:` 可选，相对 **YAML 文件所在目录** 的路径（如 `import_ai_rules/quote.md`），内容与 `rules_text` 拼接
   - `fields_allowlist:` 可选，仅允许 AI 建议的 `load` 列名（须为代码中安全子集，见 `mapping.DEFAULT_AI_IMPORT_ALLOWLIST`）；缺省即用该默认集合
   - `scope:` `aggregated`（默认，每 `quote_no` 调一次，携带该单在各 tab 的快照）或 `per_tab_row`（预留；当前与 `aggregated` 行为相同）
3. **合并策略**：只对 `source_tabs` 含该 tab、且该 tab 启用 AI 的行调用；多 tab 启用时规则字符串拼接、`fields_allowlist` 取并集。AI 返回值**仅填补当前仍为空的允许字段**，不覆盖已有确定性映射或运维列（运维列本不在 allowlist 内）。
4. **与确定性逻辑分工**：`status`、`is_trouble_case`、`quote_no`、`source_tabs` 仍由现有 Sheet 逻辑决定，**不由**导入 AI 修改。
5. **统计**：`ImportStats.ai_import_calls` / `ai_import_failures`；Debug 导入成功提示与 `import_once` 标准输出附计数（仅 `ai_import_calls>0` 时拼接提示亦含失败数）。

## 非功能约束

- 使用只读 OAuth scope；凭证由 `GOOGLE_APPLICATION_CREDENTIALS`（或设置项）指定。
- 大批量时需考虑 API 配额；颜色与值分行请求，实现以代码为准。启用 AI 导入时另计 Gemini 调用（每写库 `quote_no` 至多一次）。

## 实现参考

- 代码：`v2/app/sheet_import.py`、`v2/app/sheet_colors.py`、`v2/app/mapping.py`
- 配置：`v2/config/load_mapping.yaml`
- 单测：`v2/tests/test_sheet_import.py`

## 验收要点

- quote 无色 P/U 与有色行单测通过；绿→`carrier_assigned`。
- 同一 quote 多 tab 合并优先级符合预期。
- 库内已填运营列时重导入不改变 `status`（可构造集成用例或手工 SQL 验证）。
