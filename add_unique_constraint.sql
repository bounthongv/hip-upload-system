-- Add unique constraint to prevent duplicate records based on badge number, check time, and device SN
-- This will allow us to use ON DUPLICATE KEY UPDATE to handle potential duplicates

ALTER TABLE access_device_logs 
ADD CONSTRAINT unique_badge_time_sn UNIQUE (badge_number, check_time, device_sn);