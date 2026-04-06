# EW 项目目录（从这里开始）

## 顶层一览

| 路径 | 作用 |
|------|------|
| [COMPANY_RULES.md](COMPANY_RULES.md) | 公司基本规则与开发原则。 |
| [EW_CATALOG.yaml](EW_CATALOG.yaml) | 总目录：逻辑 id、`/F/read/...` 路由、Sheet URL / `gid`、`rules_file`。 |
| [requirements.txt](requirements.txt) | Python 依赖。 |
| [docker-compose.yml](docker-compose.yml) | 可选本地 Postgres（默认 5433→5432）。 |
| [run_service.sh](run_service.sh) | 启动 HTTP：`uvicorn function.ew_service:app`。 |
| [.env](.env) | 本机环境（不提交）；复制自 [.env.example](.env.example)。 |

## `config/` — 配置与密钥（示例可提交）

| 路径 | 作用 |
|------|------|
| `api.secrets.env.example` | 复制为 **`api.secrets.env`**（gitignore）：Maps、会话、管理员令牌等。 |
| `ew_users.example.yaml` | 复制为 **`ew_users.yaml`**：登录用户与密码哈希。 |
| `ew_settings.env` | 可选：由 `/config` 页写入的运行时项。 |

## `db/` — PostgreSQL 建表与示例

| 路径 | 作用 |
|------|------|
| **`schema_order.sql`** | **主入口**：下单域表 `ew_orders` 等（与 `EW_ORDER_RULES.yaml` 一致）。新库先执行：`psql … -f db/schema_order.sql` |
| `schema_ltl_*.sql` | 历史 / 兼容或补充脚本。 |
| `schema.example.sql` + `mapping.example.yaml` | 通用 Sheet 镜像表示例（非订单主路径）。 |

## `docs/` — 模块说明与计划

| 路径 | 作用 |
|------|------|
| [ORDER_MODULE.md](docs/ORDER_MODULE.md) | Order 页、`/f/read/order`、列映射与地图。 |
| [WORK_PLAN_SAM_GATE.md](docs/WORK_PLAN_SAM_GATE.md) | 工作目标与分阶段计划。 |

## `function/` — Python 包（服务入口在此）

| 路径 | 作用 |
|------|------|
| **`ew_service.py`** | **FastAPI 应用**：路由、`/login`、`/register`、`/f/read/...`。 |
| `api_config.py` | 加载 `.env` + `config/*.env`。 |
| `session_auth.py` | Cookie 会话签名。 |
| `auth_*.py`、`register_*.py`、`create_user.py` | 用户与注册策略。 |
| `*_page.py`、`dat_theme.py`、`web_nav.py` | 各页面 HTML 与主题。 |
| `order_view.py`、`ew_sort.py`、`maps_distance.py`、`address_display.py` | 下单页与地图。 |
| **`sheet_sync/`** | 读 Google Sheet、同步 Postgres、`python -m function.sheet_sync`。 |
| `sheet_sync/rules/*.yaml` | 各表列映射（如 `EW_ORDER_RULES.yaml`）。 |

## `scripts/` — 一次性工具

| 路径 | 作用 |
|------|------|
| `check_maps_env.py` | 检查 Maps API Key 是否被 `api_config` 加载。 |

## `temp/` — 本地临时文件（gitignore）

调试导出等，不纳入版本控制。

---

## 对话里怎么说

- **`/F/read/order`** 或 **下单 BOL** → `EW_CATALOG.yaml` 里对应条目的 `google` 与 `rules_file`。
- 稳定关键字：**`ew_quote_working`**（与 `sheets` 下的 key 一致）。

## 常用命令（仓库根目录）

```bash
python -m function.sheet_sync --sheet ew_quote_working
python -m function.sheet_sync --probe --sheet ew_quote_working
```

### HTTP 服务

**须先在本机启动服务**，再在浏览器打开；关掉终端即停止。

若 **ERR_CONNECTION_REFUSED**：8000 无进程——重新执行 `./run_service.sh` 并保持该终端不关；另开终端：`curl -sS http://127.0.0.1:8000/health` 应看到 `{"status":"ok"}`。

```bash
./run_service.sh
# 或：uvicorn function.ew_service:app --host 127.0.0.1 --port 8000 --reload
```

- 主页：`http://127.0.0.1:8000/`（**http**，勿用 https）
- 示例：`http://127.0.0.1:8000/f/read/quote?fmt=html&limit=50`
- 健康检查：`http://127.0.0.1:8000/health`
