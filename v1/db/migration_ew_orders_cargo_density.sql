-- 货物密度 PCF（lb/ft³），由「格式化数据」根据 L/M/N 列计算写入。
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS cargo_density_pcf DOUBLE PRECISION;
COMMENT ON COLUMN ew_orders.cargo_density_pcf IS '货物密度 lb/ft³（由重量与体积/尺寸在格式化数据时计算）。';
