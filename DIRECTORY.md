# EWproject 目录（从这里开始）

| 文件 / 目录 | 作用 |
|-------------|------|
| [EW_CATALOG.yaml](EW_CATALOG.yaml) | **总目录**：逻辑 id（如 `ew_quote_working`）、路由 `/F/read/...`、中英文别名、Google Sheet URL / `gid`、对应 `rules_file`。 |
| [function/sheet_sync/](function/sheet_sync/) | 读 Google Sheet 的实现（`python -m function.sheet_sync`）。 |
| [function/sheet_sync/rules/](function/sheet_sync/rules/) | 各表的列映射与清洗规则（YAML）。 |

## 对话里怎么说

- 说 **`/F/read/order`** 或 **`下单 BOL need booking`** → 查 `EW_CATALOG.yaml` 里 `ew_quote_working` 的 `google` 与 `rules_file`。
- 稳定关键字：**`ew_quote_working`**（与 `sheets` 下的 key 一致）。

## 常用命令（仓库根目录）

```bash
python -m function.sheet_sync --sheet ew_quote_working
python -m function.sheet_sync --probe --sheet ew_quote_working
```
