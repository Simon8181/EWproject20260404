-- NMFC 等级（密度法，与 cargo_density_pcf 同时由「格式化数据」写入）
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS freight_class_nmfc DOUBLE PRECISION;
COMMENT ON COLUMN ew_orders.freight_class_nmfc IS 'NMFC 货运等级（密度法估算；正式评级以 NMFTA/承运人为准）。';
