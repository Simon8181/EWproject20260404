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
