ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS maps_origin_href TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS maps_dest_href TEXT;
ALTER TABLE ew_orders ADD COLUMN IF NOT EXISTS maps_directions_href TEXT;
