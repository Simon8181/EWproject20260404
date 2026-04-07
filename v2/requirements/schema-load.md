# 需求：数据模型与 SQLite 迁移

> 路径：`v2/requirements/schema-load.md`

## 目的

为 EW v2 提供单表 `load` 的持久化模型：承运单主数据、校验结果、运营扩展列与合法 `status` 枚举；旧库可自动迁移到新 CHECK 与列结构。

## 范围

- **在内**：`load` 表 DDL、`ALLOWED_STATUS`、CHECK 约束、`_migrate_load_status_if_needed` 链式迁移、日志/锁等附属表（`load_sync_log`、`import_lock`、`load_validation_log`、`debug_validation_job`）。
- **不在内**：Google Sheet 具体列含义（见 `sheet-import.md`）、HTTP 行为（见 `debug-web.md`）。

## 功能需求

1. **单列状态**：每笔 load 仅 `load.status` 表达业务/运输阶段（见 `text1` 附录 A）。
2. **枚举**：`status` 必须为下列之一：  
   `pending_quote`、`quoted`、`quote_no_customer_response`（Sheet 合并中「客户未回应报价」）、`not_ready`、`ordered`、`carrier_assigned`、`ready_to_pick`、`picked`、`unloaded`、`complete`、`cancel`。
3. **遗留值**：历史数据中 `quote` 在迁移时统一改为 `pending_quote`。
4. **迁移触发**：若当前 `load` 表 DDL 的 CHECK 中缺少本需求规定的任一状态关键字，则重建 `load` 表并复制数据（保留列集合与 `PRAGMA table_info` 顺序一致）。
5. **运营扩展列**（与网页真相源一致，可为空默认值）：  
   `pickup_eta`、`delivery_eta`、`pickup_tz`、`delivery_tz`、`carrier_note`、`cargo_ready`（0/1）、`operator_updated_by`、`operator_updated_at`。
6. **Sheet 备注派生列**（由导入根据 D/E/F 规则解析写入，默认空）：  
   `broker`、`actual_driver_rate_raw`（实际给司机价）、`carriers`（MC/3PL 等）；与 `note_d_raw` / `note_e_raw` / `note_f_raw` 并存，见 `sheet-import.md`。
7. **兼容**：新库 `CREATE TABLE IF NOT EXISTS` 含完整列；旧库通过 `ALTER` 补列后再按上条规则处理 CHECK。

## 非功能约束

- 使用 SQLite WAL；连接 `busy_timeout` 与超时策略由实现约定。
- 迁移失败应回滚事务，不留下半成品表名（如 `load__new` 残留需人工/运维处理，实现侧应尽量原子）。

## 实现参考

- 代码：`v2/app/db.py`
- 单测：`v2/tests/test_db_carrier_assigned.py`

## 验收要点

- `:memory:` 新库可插入全部合法 `status`。
- 模拟旧 CHECK / 旧 `quote` 行，执行 `ensure_schema` 后枚举合法且 `quote`→`pending_quote`。
- 运营列在迁移后仍然存在且可读写。
