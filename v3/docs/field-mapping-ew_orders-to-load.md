# v1 `ew_orders` ↔ v2 `load` 列级映射

用于 **数据迁移、双写对账或报表对齐**。v1 定义见 [`v1/db/schema_order.sql`](../../v1/db/schema_order.sql) 及列注释；v2 定义见 [`v2/app/db.py`](../../v2/app/db.py) 中 `_load_create_table_ddl`。

**说明**：

- v1 注释中的 **Sheet 列字母** 以「下单 BOL」表为主；v2 多 tab 合并时 **同一 `quote_no` 多行会聚合成一行**，详见 [`v2/requirements/sheet-import.md`](../../v2/requirements/sheet-import.md)。
- v2 的 `broker` / `actual_driver_rate_raw` / `carriers` 主要由 **D/E/F 规则解析** 写入，与 v1 的 V/W/X **语义相近但不保证同源**；迁移时可用 V→broker、W→actual_driver_rate_raw、X→carriers 作 **种子**，再以 v2 规则重算覆盖。
- v2 的 `shipper_info` / `consignee_info` 多为 **地址校验后参与方抽取**，v1 无直接列；迁移时可留空或由脚本回填。

| v2 `load` | v1 `ew_orders` | 备注 |
|-----------|----------------|------|
| `quote_no` | `ew_quote_no` | 业务主键（C 列） |
| `status` | 无直接列 | v1 用 `a_cell_status` 文本 + Sheet 逻辑；v2 为枚举。迁移需 **规则表** 转换 |
| `is_trouble_case` | 无 | v2 专用 |
| `customer_name` | `quote_company` | B 列 |
| `note_d_raw` | `quote_bol_ref` | v1 注释：D BOL；v2 存 D 列原文 |
| `note_e_raw` | `dat_post_status` | v1：E |
| `note_f_raw` | `status_text` | v1：F |
| `broker` | `booking_broker` | v1：V；v2 亦可来自 D/E/F 解析 |
| `actual_driver_rate_raw` | `booking_rate` | v1：W；与 `driver_rate_raw`（U）区分 |
| `carriers` | `carrier_mc` | v1：X |
| `pieces_raw` | `ctn_total` | G |
| `commodity_desc` | `goods_description` | H |
| `ship_from_raw` | `ship_from` | I |
| `consignee_contact` | `consignee_contact` | J |
| `shipper_info` | — | v1 无；可空或由抽取生成 |
| `consignee_info` | — | v1 无；可空或由抽取生成 |
| `ship_to_raw` | `consignee_address` | K |
| `weight_raw` | `weight_lbs` | L |
| `dimension_raw` | `dimensions_class` | M |
| `volume_raw` | `volume_m3` | N |
| `cargo_value_raw` | `cargo_value_note` | O |
| `customer_quote_raw` | `quote_customer` | P |
| `driver_rate_raw` | `quote_driver` | U |
| `distance_miles` | `google_distance_miles` | 类型 v1 `DOUBLE PRECISION` → v2 `REAL` |
| `origin_land_use` | `origin_land_use` | |
| `dest_land_use` | `destination_land_use` | |
| `validate_ok` | 无 | v2 校验管线 |
| `validate_error` | `maps_enrich_error` 等 | **近似**：v1 多张地图错误列需合并策略 |
| `validated_at` | `maps_enriched_at` | 类型 v1 `TIMESTAMPTZ` → v2 ISO 文本 |
| `used_ai_retry` | 无 | v2 |
| `ai_confidence` | 无 | v2 |
| `origin_normalized` | `origin_formatted_address` | 语义接近 |
| `dest_normalized` | `destination_formatted_address` | |
| `ai_notes` | 无 | v2 |
| `pickup_eta` … `operator_updated_at` | 无 | v2 运营列；迁移默认空 |
| `source_tabs` | 无 | v2 聚合元数据 |
| `first_seen_at` / `last_seen_at` / `created_at` / `updated_at` | `synced_at` | v2 四分时间；可用 `synced_at` 填 `last_seen_at` / `updated_at` 初值 |

## v1 有、v2 `load` 未直接建模的列（迁移时处理）

| v1 列 | 建议 |
|-------|------|
| `route_miles_note`（Q） | v2 明确不导入 Q；可进扩展表或 `ai_notes` / JSON |
| `google_distance_text`, `google_route_duration_text` | 可拼入 `validate_error` 旁白或扩展列 |
| `origin_geocode_types`, `destination_geocode_types`, `origin_location_type`, `destination_location_type` | 扩展列或 JSON |
| `maps_*_geocode_status`, `maps_origin_href`, `maps_dest_href`, `maps_directions_href` | 扩展列或 JSON |
| `cargo_density_pcf`, `freight_class_nmfc` | 扩展列；v2 当前无 |
| `a_cell_status` | 用于推导 v2 `status` 的输入，不单列落 `load` |

## v1 附属表

| 表 | 与 `load` 关系 |
|----|----------------|
| `order_fee_addons` | 可按 `ew_quote_no` = `quote_no` 保留为 **独立表** 或未来并入 v3 扩展模型 |
