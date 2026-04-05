-- 已有库：为 ew_orders 增加 Google Maps 同步缓存列（距离、Geocode 标准地址、types、Land use）。
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS google_distance_miles DOUBLE PRECISION;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS google_distance_text TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS google_route_duration_text TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS origin_formatted_address TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS destination_formatted_address TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS origin_geocode_types TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS destination_geocode_types TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS origin_location_type TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS destination_location_type TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS origin_land_use TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS destination_land_use TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS maps_origin_geocode_status TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS maps_dest_geocode_status TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS maps_enriched_at TIMESTAMPTZ;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS maps_enrich_error TEXT;
