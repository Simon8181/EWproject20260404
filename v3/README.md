# EW v3

规划文档见下表；**Web 壳**已落地为 [`app/web.py`](app/web.py)（与 v2 Debug 同风格、干净 URL、含 **blank**）。业务实现仍以 [`v1/`](../v1/)、[`v2/`](../v2/) 为主。

## 启动 Web 壳

```bash
cd v3
pip install -r requirements.txt
# --reload-dir app：只监视 app/，减少无关目录触发的重载（略快）
uvicorn app.web:app --host 127.0.0.1 --port 8011 --reload --reload-dir app
```

- 首页：`http://127.0.0.1:8011/`
- Tab：`/tab/quote`、`/tab/order` 等；空白页：`/blank`
- **Core Sheet 刷新（JSON）**：`http://127.0.0.1:8011/api/core/sheet/refresh`  
  - 可选：`?tab=quote` 只拉一个 tab；`?max_rows=N` 限制每表数据行数（省略或 0 则读至表网格末尾，分页）；`N` 至多为 1_000_000  
  - 配置与表 ID 来自 [`core/ai_sheet_rules.yaml`](core/ai_sheet_rules.yaml)；凭证同 v2（`GOOGLE_APPLICATION_CREDENTIALS` 或 `v2/config/service_account.json`）
- **前四 tab → `load` 形状预览（不写库）**：`POST http://127.0.0.1:8011/api/core/sheet/sync-load`  
  - 返回每行 **ewId**（C 列）、`cells`（A–U）、`load`（将对应表字段）；`persisted: false`  
  - 可选：`?max_rows=N`（同上；省略则读全）
- OpenAPI：`http://127.0.0.1:8011/docs`

| 文档 | 说明 |
|------|------|
| [docs/ADR-001-v3-foundations.md](docs/ADR-001-v3-foundations.md) | v3 基础决策：主数据、存储、Sheet/Web 字段归属 |
| [docs/field-mapping-ew_orders-to-load.md](docs/field-mapping-ew_orders-to-load.md) | `v1.ew_orders` 与 `v2.load` 列级对应（迁移 / 双写参考） |
| [docs/product-path.md](docs/product-path.md) | 产品演进路径：扩 v2  vs 瘦 v1 + API |
| [docs/web-shell-scaffold.md](docs/web-shell-scaffold.md) | Web 壳设计与与 v2 对齐说明（实现以仓库内 `app/web.py` 为准） |
