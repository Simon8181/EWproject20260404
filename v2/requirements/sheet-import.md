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

### 状态规则（须与 `text1` §2 一致）

1. **A 列红** → `ordered`；**A 列绿** → `carrier_assigned`（禁止绿映射到 `ready_to_pick`）。
2. **仅 quote tab、且无 A 列色**：`P` 与 `U` 皆空 → `pending_quote`；任一非空 → `quoted`。
3. **多 tab 同一 `quote_no`**：按 `STATUS_PRIORITY` 合并为更高阶段状态（含 `cancel` 等终态优先级）。

### 导入锁与重导

1. **首次导入**：默认写入 `import_lock.initial_load_done`；未完成前可重复导入语义由调用方控制。
2. **`force_reimport`**：允许跳过锁再次导入；**生产环境禁止**（由 `app_env` 判断）。
3. **`ON CONFLICT`**：若库中该行已被网页真相源维护（任一下列非空或非默认：`pickup_eta`、`delivery_eta`、`pickup_tz`、`delivery_tz`、`carrier_note`、`cargo_ready`、`operator_updated_at`、`operator_updated_by`），则**不**用本次 Sheet 推导结果覆盖 `status`；其余列按 SQL 更新。

## 非功能约束

- 使用只读 OAuth scope；凭证由 `GOOGLE_APPLICATION_CREDENTIALS`（或设置项）指定。
- 大批量时需考虑 API 配额；颜色与值分行请求，实现以代码为准。

## 实现参考

- 代码：`v2/app/sheet_import.py`、`v2/app/sheet_colors.py`、`v2/app/mapping.py`
- 配置：`v2/config/load_mapping.yaml`
- 单测：`v2/tests/test_sheet_import.py`

## 验收要点

- quote 无色 P/U 与有色行单测通过；绿→`carrier_assigned`。
- 同一 quote 多 tab 合并优先级符合预期。
- 库内已填运营列时重导入不改变 `status`（可构造集成用例或手工 SQL 验证）。
