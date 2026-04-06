-- 已有库：起运/目的 城市与州（格式化数据技能写入）
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS ship_from_city TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS ship_from_state TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS consignee_city TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS consignee_state TEXT;

COMMENT ON COLUMN ew_orders.ship_from_city IS '起运城市（Geocoding locality 等）。';
COMMENT ON COLUMN ew_orders.ship_from_state IS '起运州/省缩写（美国多为 2 字母）。';
COMMENT ON COLUMN ew_orders.consignee_city IS '目的城市。';
COMMENT ON COLUMN ew_orders.consignee_state IS '目的州/省缩写。';
