-- Matches function/sheet_sync/rules/EW_CANCEL_RULES.yaml → postgres.table / columns

CREATE TABLE IF NOT EXISTS ltl_cancelled_orders (
    ew_quote_no TEXT PRIMARY KEY,
    cancel_date TEXT,
    quote_company TEXT,
    quote_ref TEXT,
    mark TEXT,
    cancel_reason TEXT,
    ctn_total TEXT,
    goods_description TEXT,
    ship_from TEXT,
    consignee_contact TEXT,
    consignee_address TEXT,
    weight_lbs TEXT,
    dimensions_class TEXT,
    volume_m3 TEXT,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);
