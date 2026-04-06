# Order 模块开发记录（暂停）

**状态：暂停** — 当前实现已保存，后续可在此文件续写。

## 范围

- **数据源**：`EW_CATALOG.yaml` 路由 `/f/read/order` → `ew_quote_working` → `function/sheet_sync/rules/EW_ORDER_RULES.yaml`（Google Sheet「下单 BOL need booking」tab）。
- **HTTP**：`function/ew_service.py` 中当 `name == "order"` 且 `fmt=html` 时，不使用通用表格页，而走专用 **`function/order_view.py`**。
- **分页**：`?page=1&per_page=20`（默认每页 20）；旧参数 `limit` 仍可作为每页条数。HTML 底栏可点 **每页 10 / 20 / 50 / 100**（切换后回到第 1 页）。JSON 返回 `{ items, total, page, per_page, total_pages }`。

## 已实现

### 列映射（`EW_ORDER_RULES.yaml`）

- **A 列**：不看文字，看**单元格填充色**（Sheets API）——红→`a_cell_status`=`待找车`，绿→`已经安排`；其它/浅色/无法识别则为空。
- 与表头对齐：G=ctn、H=品名、**I=SHIP FROM（起运）**、J/K=收货、L=lbs、M=尺寸、N=体积、O=货值、**P=给客户报价** `quote_customer`、**Q=mil** `route_miles_note`、**U=给司机报价** `quote_driver`。
- **其他费用**：不在 Sheet，由**网页追加**；库表 **`order_fee_addons`**（`ew_quote_no` + 金额/备注），与 `WORK_PLAN_SAM_GATE.md` 一致。
- 曾修正：起运须在 **I 列**，勿误用 H。

### 系统展示规范（起始地 vs 目的）

- **起始地**：卡片与地图尽量输出 **`City, ST 12345`**（或中文城市+州+邮编）。入口 **`function.address_display.resolve_origin_for_order`**：优先从 **`ship_from`** 解析；若 I 列多为货描、无邮编，则回退 **`consignee_contact`** 中带「提货地址 / 发货地址」等标签的段落。地图链接使用解析时采用的**原文**，避免搜「地板」等货名。
- **单字段**：仅对 `ship_from` 字符串做规范化时可用 **`format_ship_from_for_display`**（不含提货回退）。
- **目的**：**`consignee_address` / `consignee_contact` 不做上述起始地解析**，卡片为原文拼接；地图用完整目的文案。

### 页面（`order_view.py`）

- 多订单、**紧凑布局**，全页 **移动端适配**（`viewport-fit`、安全区、`100dvh` 等）。
- **EW 号降序**：`function/ew_sort.py` + `ew_service` 在 order 的 JSON/HTML 中排序。
- **里程**：Q 列解析数字，**只显示 mi**（`function/route_metrics.py`）。
- **报价区（DAT 风橙色块）**：展示 **P 客户**、**U 司机**；其他费用为「网页追加」占位说明。
- **地图交互**：
  - 点击 **起运** 文案 → Google 地图搜索起点；
  - 点击 **目的** 文案 → 搜索终点；
  - **中间「路线」按钮** → `maps/dir` 起点→终点。
- 下方「里程」块仅保留 Mi；货物/尺寸 chips。

### 数据库

- **`db/schema_order.sql`**：主表 **`ew_orders`**（与 `EW_ORDER_RULES.yaml` 的 `postgres.table` 一致），`order_fee_addons` 按 `ew_quote_no` 关联。旧名 `ltl_working_quotes` 见 `db/schema_ltl_working.sql` 中的迁移说明。

### 格式化数据（规范化邮编）批量补全（非 Sheet 同步）

- **不在「从 Sheet 刷新」时调用 Maps**。Sheet 同步只写表内列 + 邮编解析（`ship_from_zip` / `consignee_zip`）。
- **触发**：订单页开发者技能 **「格式化数据（规范化邮编）」**（原 Google Map）→ `POST /f/read/order/google-maps`，逻辑在 **`function/order_maps_enrich.py`** 的 **`batch_enrich_all_ew_orders_maps`**：对 `ew_orders` **全表**排序与列表一致，逐条若缺距离 / Geocode types / 三向地图链接则调 **`fetch_route_insight`** 并 **UPDATE**（含邮编规范化写入 `ship_from_zip` / `consignee_zip`）。
- **规则**：起运 **`resolve_origin_for_order`**；Geocode 候选 **`pick_line_for_geocode`**；与 **`/api/route`** 同源。
- **落库**：距离、formatted 地址、types、Land use、跳转链接；并 **回写** 与 Sheet 对齐的四列：**`ship_from`**、**`ship_from_zip`**、**`consignee_address`**、**`consignee_zip`**（Google Geocoding 标准地址 + `postal_code` / 文本解析邮编）。下次「从 Sheet 刷新」会按 Sheet 再次覆盖。
- **页面**：**`order_view.py`** 仅读库展示，不发起在线 Maps；缺项订单 **`maps_row_needs_attention`** 时整卡高亮并显示「待解决」横幅。
- **环境**：`GOOGLE_MAPS_API_KEY`；`EW_ORDER_MAPS_BATCH_DELAY_MS` 可选节流。

### 其它页面

- **主页** `home_page.py`、**通用 HTML 表** `render_html.py`：移动端与横向滚动表。

## 常用命令

```bash
# 本地读表校验
python -m function.sheet_sync --sheet ew_quote_working --preview 5

# 服务（order 卡片页）
uvicorn function.ew_service:app --host 127.0.0.1 --port 8000
# 浏览器：http://127.0.0.1:8000/f/read/order?fmt=html&limit=50
```

## 暂停时未做 / 可续

- `--sync` 写库与 order 专用逻辑的一致性回归。
- 地图链接对**极短/无效地址**的容错与提示文案。
- 业务规则见仓库根目录 **`COMPANY_RULES.md`**（报价、权限等）。

---

*暂停记录日期以本文件提交时间为准；恢复开发时请先读本节与 `EW_ORDER_RULES.yaml` 注释。*
