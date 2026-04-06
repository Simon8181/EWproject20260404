# 需求：import_once 命令行一次性导入

> 路径：`v2/requirements/import-once.md`

## 目的

在无 Debug UI 或自动化脚本场景下，从命令行触发与 Debug「导入数据」相同的 `run_one_time_import` 流程，并支持测试用的 reset / force 选项。

## 范围

- **在内**：`python -m app.import_once` 参数解析、环境读取、`ensure_schema`、导入锁语义、`force_reimport` / `reset` 与 prod 禁止规则。
- **不在内**：Sheet 列规则细节（见 `sheet-import.md`）。

## 功能需求

1. **默认行为**：打开 `settings` 指定 DB，读取 `load_mapping.yaml`，调用 `run_one_time_import`；若已导入锁且无 `force_reimport`，可快速 noop（以 `sheet_import` 实现为准）。
2. **`--force-reimport`**：忽略导入锁再次导入；**`APP_ENV=prod` 时禁止**。
3. **`--reset`**：清空 `load` 与导入锁后再导入；**prod 禁止**。
4. **`--trigger`**：写入 `load_sync_log` 的标签字符串，便于区分 initial/manual/cli。
5. **输出**：打印 `rows_read` / `rows_written` / `rows_skipped` 及 `import_ai_calls` / `import_ai_failures`（见 `sheet-import.md` AI 导入补缺）。

## 非功能约束

- 依赖本机或服务账号 JSON 可读；网络可达 Google API。

## 实现参考

- 代码：`v2/app/import_once.py`
- README：`v2/README.md`「一次性导入」

## 验收要点

- 在测试环境 `--reset --force-reimport` 可重复灌库；prod 下触发应明确报错或拒绝。
