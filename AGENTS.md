# Agent 说明（EW 仓库）

## `v1/`、`v2/` 只读（仅供参考）

**不要**在 `v1/`、`v2/` 下改代码、配置或文档；这两版仅作历史与行为对照。新逻辑一律落在 **`v3/` 及之后的大版本**。若要对齐旧实现，在 v3+ 里实现或迁移，而非回改 v1/v2。

---

## 按大版本读 `core`

本仓库用顶层目录 `v3/`、`v4/`、`v5/` … 区分大版本。处理**某一版本目录**下的任务时，若存在 `vN/core/`，请先阅读：

- `vN/core/README.md`
- `vN/core/ai_sheet_rules.yaml` — Sheet 变更→AI→`load` 必要字段、禁止输出、模型配置

`vN/core/rules.yaml` **仅说明性**，应用**不加载**。

若与上述 YAML 冲突，以**该版本**下 `ai_sheet_rules.yaml` 与 `README.md` 为准。

跨版本改动时，分别阅读各版本自己的 `core`。

## 新开版本

从上一版复制 `vN/core/`（含 `ai_sheet_rules.yaml`、`config_paths.py`、README 等），并更新本说明。

## Cursor

项目规则 `.cursor/rules/version-core-context.mdc`（`alwaysApply: true`）会提示上述路径。
