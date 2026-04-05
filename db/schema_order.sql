-- =============================================================================
-- Order domain — 与 function/sheet_sync/rules/EW_ORDER_RULES.yaml 列映射一致
-- 主键：ew_quote_no（Sheet C 列业务单号，全局唯一）
-- =============================================================================

-- -----------------------------------------------------------------------------
-- ew_orders —「下单 BOL need booking」Sheet 行级镜像
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ew_orders (
    ew_quote_no TEXT NOT NULL,
    quote_company TEXT,
    quote_bol_ref TEXT,
    dat_post_status TEXT,
    status_text TEXT,
    ctn_total TEXT,
    goods_description TEXT,
    ship_from TEXT,
    consignee_contact TEXT,
    consignee_address TEXT,
    ship_from_zip TEXT,
    ship_from_city TEXT,
    ship_from_state TEXT,
    consignee_zip TEXT,
    consignee_city TEXT,
    consignee_state TEXT,
    weight_lbs TEXT,
    dimensions_class TEXT,
    volume_m3 TEXT,
    cargo_value_note TEXT,
    quote_customer TEXT,
    route_miles_note TEXT,
    quote_driver TEXT,
    booking_broker TEXT,
    booking_rate TEXT,
    carrier_mc TEXT,
    a_cell_status TEXT,
    google_distance_miles DOUBLE PRECISION,
    google_distance_text TEXT,
    google_route_duration_text TEXT,
    origin_formatted_address TEXT,
    destination_formatted_address TEXT,
    origin_geocode_types TEXT,
    destination_geocode_types TEXT,
    origin_location_type TEXT,
    destination_location_type TEXT,
    origin_land_use TEXT,
    destination_land_use TEXT,
    maps_origin_geocode_status TEXT,
    maps_dest_geocode_status TEXT,
    maps_enriched_at TIMESTAMPTZ,
    maps_enrich_error TEXT,
    maps_origin_href TEXT,
    maps_dest_href TEXT,
    maps_directions_href TEXT,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ew_orders_pkey PRIMARY KEY (ew_quote_no)
);

COMMENT ON TABLE ew_orders IS 'EW 在途下单 Sheet 镜像；列字母与含义见 EW_ORDER_RULES.yaml。';
COMMENT ON COLUMN ew_orders.ew_quote_no IS 'C 列报价/订单号（主键）。';
COMMENT ON COLUMN ew_orders.quote_company IS 'B 公司。';
COMMENT ON COLUMN ew_orders.quote_bol_ref IS 'D BOL 参考。';
COMMENT ON COLUMN ew_orders.dat_post_status IS 'E DAT/柜等。';
COMMENT ON COLUMN ew_orders.status_text IS 'F 状态说明。';
COMMENT ON COLUMN ew_orders.ctn_total IS 'G 件数等。';
COMMENT ON COLUMN ew_orders.goods_description IS 'H 品名。';
COMMENT ON COLUMN ew_orders.ship_from IS 'I 起运。';
COMMENT ON COLUMN ew_orders.consignee_contact IS 'J 收货联系人/电话块。';
COMMENT ON COLUMN ew_orders.consignee_address IS 'K 收货地址。';
COMMENT ON COLUMN ew_orders.ship_from_zip IS '起运邮编（美国 5 位），同步或格式化数据写入。';
COMMENT ON COLUMN ew_orders.ship_from_city IS '起运城市（格式化数据 Geocoding）。';
COMMENT ON COLUMN ew_orders.ship_from_state IS '起运州缩写（美国多为 2 字母）。';
COMMENT ON COLUMN ew_orders.consignee_zip IS '目的邮编，从 K/J 文本解析或格式化数据。';
COMMENT ON COLUMN ew_orders.consignee_city IS '目的城市（格式化数据 Geocoding）。';
COMMENT ON COLUMN ew_orders.consignee_state IS '目的州缩写。';
COMMENT ON COLUMN ew_orders.weight_lbs IS 'L 重量。';
COMMENT ON COLUMN ew_orders.dimensions_class IS 'M 尺寸/等级。';
COMMENT ON COLUMN ew_orders.volume_m3 IS 'N 体积。';
COMMENT ON COLUMN ew_orders.cargo_value_note IS 'O 货值备注。';
COMMENT ON COLUMN ew_orders.quote_customer IS 'P 客户报价。';
COMMENT ON COLUMN ew_orders.route_miles_note IS 'Q 里程备注。';
COMMENT ON COLUMN ew_orders.quote_driver IS 'U 司机侧报价。';
COMMENT ON COLUMN ew_orders.booking_broker IS 'V Broker（接单）。';
COMMENT ON COLUMN ew_orders.booking_rate IS 'W Rate。';
COMMENT ON COLUMN ew_orders.carrier_mc IS 'X Carriers / MC#。';
COMMENT ON COLUMN ew_orders.a_cell_status IS 'A 列填色解析：待找车 | 已经安排 | 空。';
COMMENT ON COLUMN ew_orders.google_distance_miles IS 'Google Distance Matrix 驾车距离（英里），「格式化数据」技能批量补全写入。';
COMMENT ON COLUMN ew_orders.google_distance_text IS 'Matrix 返回的距离文案（如 123 mi）。';
COMMENT ON COLUMN ew_orders.google_route_duration_text IS 'Matrix 返回的预计行车时间文案。';
COMMENT ON COLUMN ew_orders.origin_formatted_address IS '起点 Geocoding formatted_address。';
COMMENT ON COLUMN ew_orders.destination_formatted_address IS '终点 Geocoding formatted_address。';
COMMENT ON COLUMN ew_orders.origin_geocode_types IS '起点 types，分号拼接。';
COMMENT ON COLUMN ew_orders.destination_geocode_types IS '终点 types，分号拼接。';
COMMENT ON COLUMN ew_orders.origin_location_type IS '起点 geometry.location_type。';
COMMENT ON COLUMN ew_orders.destination_location_type IS '终点 geometry.location_type。';
COMMENT ON COLUMN ew_orders.origin_land_use IS '起点 Land use（warehouse|commercial|residential|unknown）。';
COMMENT ON COLUMN ew_orders.destination_land_use IS '终点 Land use。';
COMMENT ON COLUMN ew_orders.maps_origin_geocode_status IS '起点 Geocoding API status。';
COMMENT ON COLUMN ew_orders.maps_dest_geocode_status IS '终点 Geocoding API status。';
COMMENT ON COLUMN ew_orders.maps_enriched_at IS '最近一次「格式化数据（规范化邮编）」技能补全的时间。';
COMMENT ON COLUMN ew_orders.maps_enrich_error IS 'Maps 补全失败简述；成功可为空。';
COMMENT ON COLUMN ew_orders.maps_origin_href IS '起点 Google 地图打开链接（maps/search）。';
COMMENT ON COLUMN ew_orders.maps_dest_href IS '终点 Google 地图打开链接。';
COMMENT ON COLUMN ew_orders.maps_directions_href IS '起点→终点驾车路线链接（maps/dir）。';
COMMENT ON COLUMN ew_orders.synced_at IS '最近一次从 Sheet 写入的时间。';

CREATE INDEX IF NOT EXISTS idx_ew_orders_a_cell ON ew_orders (a_cell_status);
CREATE INDEX IF NOT EXISTS idx_ew_orders_synced ON ew_orders (synced_at DESC);
CREATE INDEX IF NOT EXISTS idx_ew_orders_company ON ew_orders (quote_company);

-- -----------------------------------------------------------------------------
-- order_fee_addons — 网页追加费用（非 Sheet 列，按 ew_quote_no 1:1）
-- 不设 FK：允许先录费用再同步 Sheet 行；需要强一致时可自行加 FK（见文末）。
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_fee_addons (
    ew_quote_no TEXT NOT NULL,
    amount_text TEXT,
    note TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT order_fee_addons_pkey PRIMARY KEY (ew_quote_no)
);

COMMENT ON TABLE order_fee_addons IS '订单附加费用（仅网页录入）；ew_quote_no 应对应 ew_orders。';

-- -----------------------------------------------------------------------------
-- 自旧表名迁移（仅已有库执行一次；新建库可忽略）
-- -----------------------------------------------------------------------------
-- ALTER TABLE IF EXISTS ltl_working_quotes RENAME TO ew_orders;
--
-- 可选：为 order_fee_addons 增加外键（需无孤儿行）
-- ALTER TABLE order_fee_addons DROP CONSTRAINT IF EXISTS order_fee_addons_ew_quote_no_fkey;
-- ALTER TABLE order_fee_addons ADD CONSTRAINT order_fee_addons_ew_fk
--   FOREIGN KEY (ew_quote_no) REFERENCES ew_orders (ew_quote_no) ON DELETE CASCADE;
