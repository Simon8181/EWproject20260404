-- Matches function/sheet_sync/rules/EW_ORDER_RULES.yaml → postgres.table / columns
-- 若表已存在且缺列，执行下方 ALTER。

CREATE TABLE IF NOT EXISTS ltl_working_quotes (
    ew_quote_no TEXT PRIMARY KEY,
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
    a_cell_status TEXT,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE ltl_working_quotes ADD COLUMN IF NOT EXISTS ctn_total TEXT;
ALTER TABLE ltl_working_quotes ADD COLUMN IF NOT EXISTS dimensions_class TEXT;
ALTER TABLE ltl_working_quotes ADD COLUMN IF NOT EXISTS route_miles_note TEXT;
ALTER TABLE ltl_working_quotes ADD COLUMN IF NOT EXISTS quote_customer TEXT;
ALTER TABLE ltl_working_quotes ADD COLUMN IF NOT EXISTS quote_driver TEXT;
ALTER TABLE ltl_working_quotes ADD COLUMN IF NOT EXISTS a_cell_status TEXT;

-- 其他费用：网页追加录入，不与 Sheet 列一一对应（按 ew_quote_no 关联）
CREATE TABLE IF NOT EXISTS order_fee_addons (
    ew_quote_no TEXT PRIMARY KEY,
    amount_text TEXT,
    note TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
