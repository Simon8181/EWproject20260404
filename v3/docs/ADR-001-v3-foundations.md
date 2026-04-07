# ADR-001：v3 基础架构决策（草案）

**状态**：草案 — 实施 v3 前需拍板以下项。  
**上下文**：v1 为 PostgreSQL + `ew_orders` 全功能 Web + `sheet_sync`；v2 为 SQLite 单表 `load` + 只读 Sheet 导入 + Debug / 校验 / 可选 Gemini（见 [`v2/README.md`](../../v2/README.md)）。

---

## 决策 1：主数据模型

**问题**：v3 以哪套行级模型为权威？

| 选项 | 说明 |
|------|------|
| **A. 延续 v2 `load`** | 一笔业务一行 `quote_no`（C 列），多 tab 合并为 `source_tabs`；状态为枚举 `status`。 |
| **B. 回到 v1 多表** | 以 `ew_orders` 等为镜像，辅以 `order_fee_addons` 等扩展表。 |

**建议（默认 A）**：除非必须保留 v1 侧表与历史 SQL 报表，否则以 **`load` 为单一主实体** 更简单，与当前 [`v2/requirements/schema-load.md`](../../v2/requirements/schema-load.md) 一致。若选 B，需定义 **`load` 与 `ew_orders` 的同步方向**（见 [field-mapping-ew_orders-to-load.md](field-mapping-ew_orders-to-load.md)）。

**后果**：选 A 时，v1 独有表（如费用追加）要么迁成 `load` 的 JSON/扩展列，要么保留为 **附属表** 仅挂 `quote_no` FK。

---

## 决策 2：存储与部署

**问题**：默认数据库是 SQLite 还是 PostgreSQL？

| 选项 | 适用 |
|------|------|
| **SQLite（如 v2）** | 单机工具、内网单实例、CI/开发零依赖。 |
| **PostgreSQL（如 v1）** | 多实例写、连接池、与现有运维/备份一致。 |

**建议**：开发阶段可继续 SQLite；**若 v3 目标为线上多用户写**，默认 Postgres，并把 [`v2/app/db.py`](../../v2/app/db.py) 中的 DDL / `ensure_schema` 思路 **抽象为可切换后端**（同一列语义，不同方言与迁移工具），避免维护两套业务逻辑。

**非目标（本 ADR）**：不在此决定云厂商或 K8s；仅决定 **逻辑模型落库形态**。

---

## 决策 3：Google Sheet 与 Web 的字段归属

**原则（继承 v2）**：

- Sheet **只读导入**；`quote_no` 与 Sheet 行对齐。
- **重导入**时，若行上已有运营维护内容，**不得用 Sheet 覆盖**受保护字段（与 `text1` 附录 B 及 [`v2/requirements/sheet-import.md`](../../v2/requirements/sheet-import.md) 一致），尤其是 `status`（在满足条件时）、ETA/时区/承运备注/审计等。

**v3 应显式维护一张「字段来源表」**（可在本仓库 `v3/docs/` 或 `v2/requirements/` 下迭代），每列标注：

- `sheet_only`：仅来自导入，Web 只读展示。
- `web_ops`：运营在 Debug / 未来主站写入；导入时按规则 **保留或合并**。
- `derived`：由规则或 AI 从多列推导（如 `broker` / `actual_driver_rate_raw` / `carriers` 来自 D/E/F）。

**建议**：新列必须先标来源再实现导入或 UI，避免第三套「隐式双写」。

---

## 决策 4：Debug 与「正式后台」

**问题**：v3 是否仍以 Debug 页为唯一运营入口？

**建议**：短期可延续 v2 Debug；**中长期**将「列表 + 筛选 + 受控编辑」迁到 **独立运营 UI**（可逐步从 Debug 抽路由与权限），Debug 保留为技术诊断。具体路线见 [product-path.md](product-path.md)。

---

## 验收（ADR 完成度）

- [ ] 主数据：A 或 B 已书面选定。  
- [ ] 存储：默认 SQLite / Postgres 已选定，且迁移策略有负责人。  
- [ ] 字段来源表已起稿并与 `load` 列清单对齐。  
- [ ] Debug 与正式后台边界已写入产品路径文档。
