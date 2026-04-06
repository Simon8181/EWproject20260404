-- 清空在途订单数据库镜像（ew_orders）及网页追加费用（order_fee_addons）。
-- 不可恢复；执行前请确认。需已配置 DATABASE_URL 且已建表。
-- 用法：psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/delete_all_order_data.sql

BEGIN;

TRUNCATE TABLE order_fee_addons;
TRUNCATE TABLE ew_orders;

COMMIT;
