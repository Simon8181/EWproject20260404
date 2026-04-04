-- Matches EW_SHEET_RULES.yaml → postgres.table / columns

CREATE TABLE IF NOT EXISTS ltl_working_quotes (
    ew_quote_no TEXT PRIMARY KEY,
    quote_company TEXT,
    quote_bol_ref TEXT,
    dat_post_status TEXT,
    status_text TEXT,
    goods_description TEXT,
    ship_from TEXT,
    consignee_contact TEXT,
    consignee_address TEXT,
    weight_lbs TEXT,
    volume_m3 TEXT,
    cargo_value_note TEXT,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);
