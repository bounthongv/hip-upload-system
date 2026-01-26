-- Script to remove duplicate records from access_device_logs table
-- This identifies duplicates based on badge_number, check_time, and device_sn
-- and keeps only the record with the lowest ID for each group of duplicates

DELETE t1 FROM access_device_logs t1
INNER JOIN access_device_logs t2
WHERE t1.id > t2.id
AND t1.badge_number = t2.badge_number
AND t1.check_time = t2.check_time
AND t1.device_sn = t2.device_sn;