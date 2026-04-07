# v3 产品演进路径

在 **主数据** 与 **存储** 选定（见 [ADR-001-v3-foundations.md](ADR-001-v3-foundations.md)）的前提下，v3「可部署产品」有两条主路径；**应避免第三条并行全栈**（同时大改 v1 与 v2 且无统一模型）。

---

## 路径 A：在 v2 底座上补全（推荐默认）

**做法**：保留 [`v2/app/sheet_import.py`](../../v2/app/sheet_import.py)、[`db.py`](../../v2/app/db.py)、校验与导入规则；按需增加：

- **认证与权限**（可参考 v1 [`session_auth.py`](../../v1/function/session_auth.py)、[`auth_roles.py`](../../v1/function/auth_roles.py) 的行为，不必复制实现）。
- **主列表 / 订单视图**：从 Debug 的只读+少量操作，演进为 **运营主界面**（筛选、分页、受控 patch）。
- **地图与距离**：复用 v2 校验结果列；若需 v1 级链接与 href，将 [field-mapping](field-mapping-ew_orders-to-load.md) 中的「仅 v1 有」列纳入 **扩展 JSON 或附属表**。

**优点**：单一数据模型、测试与需求文档已在 v2 对齐。  
**缺点**：需重写或移植 v1 的 HTML/UX 投资；PostgreSQL 若必选，要做 **DB 适配层**。

**适合**：希望「Sheet + load」继续为真相源、团队已熟悉 v2 的同学。

---

## 路径 B：从 v1 瘦身，API 对齐 `load` 语义

**做法**：保留 v1 部署与 Postgres、`ew_service` 路由习惯；逐步让 **写入/读取订单详情** 走一层 **与 v2 `load` 列语义一致** 的 API（内部可把 `ew_orders` 映射为 load DTO，或迁移表结构）。

**优点**：用户与 URL 习惯、PG 运维可延续。  
**缺点**：映射与双写复杂度高；`sheet_sync` 与 v2 `sheet_import` **长期并存** 易产生漂移，必须用 [field-mapping](field-mapping-ew_orders-to-load.md) 做回归校验。

**适合**：短期内不能下线 v1 站点，但必须引入 v2 的规则（状态保护、校验管线等）。

---

## 选择标准（简表）

| 若… | 更倾向 |
|------|--------|
| 团队开发与测试主要在 v2 | **路径 A** |
| 生产仍以 v1 为主且大量依赖 `ew_orders` SQL | **路径 B**（过渡） |
| 需要多实例写、审计 | 两条路径都应在 ADR 中 **选定 Postgres** |
| 仅内部工具、单人 | **路径 A** + SQLite 可维持更久 |

---

## 明确不推荐的路线

- **并行维护三套**：v1 全站 + v2 Debug + 新 v3 独立 schema 且无映射文档 — 会导致单号、状态、地址三套真相源。

拍板后，应在 ADR 或本文件顶部记录 **选定路径 + 日期 + 负责人**，并在迭代中更新。
