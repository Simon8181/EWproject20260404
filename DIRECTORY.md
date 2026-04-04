# EWproject 目录（从这里开始）

| 文件 / 目录 | 作用 |
|-------------|------|
| [COMPANY_RULES.md](COMPANY_RULES.md) | **公司基本规则与开发原则**（前四 Sheet 权限、经营指标、与 Sam 对齐的节奏等）。 |
| [EW_CATALOG.yaml](EW_CATALOG.yaml) | **总目录**：逻辑 id（如 `ew_quote_working`）、路由 `/F/read/...`、中英文别名、Google Sheet URL / `gid`、对应 `rules_file`。 |
| [docs/ORDER_MODULE.md](docs/ORDER_MODULE.md) | **Order 模块开发记录**（`/f/read/order` 专用页、列映射、地图交互；**当前暂停**）。 |
| [docs/WORK_PLAN_SAM_GATE.md](docs/WORK_PLAN_SAM_GATE.md) | **工作目标与 Sam 门槛**：订单账面汇总 + DAT 风网页，分阶段计划与配合项。 |
| [function/ew_service.py](function/ew_service.py) | **HTTP 服务**（FastAPI）：浏览器访问与目录一致的 `/f/read/...`，见下方 `uvicorn`。 |
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

### HTTP 服务（整库作为服务时）

**必须先在本机终端启动服务**，再在浏览器打开；关掉终端窗口即停止服务，页面会显示 “This site can’t be reached”。

若浏览器报 **Error -102**（`ERR_CONNECTION_REFUSED`）：表示 **8000 端口没有服务在跑**——请在本机重新执行 `./run_service.sh` 并保持该终端不关；另开一个终端执行 `curl -sS http://127.0.0.1:8000/health` 应看到 `{"status":"ok"}`。

```bash
./run_service.sh
# 或：uvicorn function.ew_service:app --host 127.0.0.1 --port 8000 --reload
```

- 主页：`http://127.0.0.1:8000/`（用 **http**，不要用 https）
- 示例：`http://127.0.0.1:8000/f/read/quote?fmt=html&limit=50`
- 健康检查：`http://127.0.0.1:8000/health`
