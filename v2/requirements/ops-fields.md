# 需求：运营字段存储、写入 API 与导入保护

> 路径：`v2/requirements/ops-fields.md`

## 目的

支撑 `text1` §4：网页（或等价渠道）为提货/送达时间、时区、承运备注、货 ready 与轻量审计的**真相源**；Sheet 重导入时不得用表格推导状态覆盖已有人工维护痕迹。

## 范围

- **在内**：`load` 表运营列、条件 `ON CONFLICT` 保护 `status`、`POST /debug/actions/patch-load`（表单 UI 可按产品暂时下线，仅保留 HTTP 能力）。
- **不在内**：Google 时区自动解析 UI（产品层可后续补）；正式运营 Portal。

## 功能需求

### 存储字段

- `pickup_eta`、`delivery_eta`：建议 ISO8601 文本（含偏移或 Z）。
- `pickup_tz`、`delivery_tz`：IANA 时区名（如 `America/Chicago`）。
- `carrier_note`：自由文本。
- `cargo_ready`：0/1。
- `operator_updated_by`、`operator_updated_at`：轻量审计。

### 写入 API（Debug，`POST /debug/actions/patch-load`）

1. 按 `quote_no` 更新；行必须已存在。
2. **ETA + 时区**：若结果集中 `pickup_eta` 非空，则必须有非空 `pickup_tz`；`delivery_eta` / `delivery_tz` 同理。
3. **部分更新**：空字符串的 ETA 表示「不改动库内原值」；`status` 空表示不改状态；`cargo_ready` 空选择表示不改；备注为空且未意图清空时行为以实现为准（当前实现：空保留原备注）。
4. 更新时刷新 `updated_at` 与操作者审计字段。

### 导入保护

当任一侧**网页真相源列**已有有效痕迹时，`sheet_import` 在 `ON CONFLICT` **不得**用 Sheet 推导的 `status` 覆盖当前行（条件表达式与 `text1` 附录 B 一致）。

## 实现参考

- 代码：`v2/app/db.py`、`v2/app/sheet_import.py`（`_LOAD_WEB_TOUCHED_SQL`）、`v2/app/debug_web.py`（`action_patch_load`）
- 说明：`v2/text1` 附录 A、B；`v2/README.md`

## 验收要点

- 手工写入运营列后执行 Sheet 重导，`status` 不变；其它 Sheet 列仍可更新。
- `patch-load` 在缺少时区时拒写对应 ETA。
