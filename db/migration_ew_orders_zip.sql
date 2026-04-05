-- 已有库执行一次：下单表增加起运/目的邮编（同步时从 I/K 等文本解析）
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS ship_from_zip TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS consignee_zip TEXT;

COMMENT ON COLUMN ew_orders.ship_from_zip IS '起运侧邮编（美国 5/9 位），Sheet 同步时从 ship_from 解析。';
COMMENT ON COLUMN ew_orders.consignee_zip IS '目的侧邮编，从 consignee_address / consignee_contact 解析。';
