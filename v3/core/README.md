# v3/core

**一份配置** [`ai_sheet_rules.yaml`](ai_sheet_rules.yaml)：

- **`sheet`**：表 ID、tab 名、可选 `watch_column_letters`（哪几列变更才触发 AI，**不是**列→字段映射）
- **`table_load.categories`**：按表头语义分类；**表头每次从 Sheet 现读第一行**，不在 YAML 里配行号；每类含 `header_hints` 与 `fields`
- **`table_load.forbidden_output`**：禁止模型输出的列（系统/运营侧）
- **`ai`**：模型与生成参数（`instructions`、`model`、`generation`、`env_key` 默认 `GEMINI_API_KEY`、`refresh_context.max_changed_rows_per_call` 控制每请求最多行数）

路径：[`config_paths.py`](config_paths.py) 的 `ai_sheet_rules_yaml()`；环境变量优先 **`V3_AI_SHEET_RULES_PATH`**，并兼容 `V3_AI_RULES_PATH` 等旧名。

## Sheet 行 AI 补缺（合并 / 预览）

在 **`V3_SHEET_ROW_AI_ENABLED=1`**（或 `true`/`yes`/`on`）且配置好 Gemini（默认读 `GEMINI_API_KEY`，可由 `ai.env_key` 覆盖）时，可在接口上打开 **`ai=true`**，在构建 `load` 后、`preview_to_import` / 写库 之前，按批调用模型补缺字段。

- **默认策略**：只向当前为空的字段写入；需要覆盖已有格子内容时传 **`ai_overwrite=true`**。
- **不会交给模型改的键**：`quote_no`、`status`、`source_tabs` 及 `table_load.forbidden_output` 中的字段。
- **响应**：四表合并时 `merge` 内包含 `ai_enrich_enabled`、`ai_enrich_calls`、`ai_enrich_rows`、`ai_enrich_failures`、`ai_enrich_errors`；单 tab 预览时同名统计挂在对应 tab 对象上。
- **`/api/core/sheet/merge-refresh`**：同样支持 `ai` / `ai_overwrite`；响应中除 `merge_stats` 外增加完整 **`merge`**（含上述 AI 统计）。

[`rules.yaml`](rules.yaml) **不被应用加载**。

## 版本迭代

新开 v4、v5 时复制 `ai_sheet_rules.yaml` 与 `config_paths.py`，并同步 [`AGENTS.md`](../../AGENTS.md)、[`.cursor/rules/version-core-context.mdc`](../../.cursor/rules/version-core-context.mdc)。
