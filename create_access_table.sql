-- SQL script to create new table for MS Access data
-- This table preserves all original MS Access fields

CREATE TABLE IF NOT EXISTS access_device_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    badge_number VARCHAR(50),        -- Corresponds to Badgenumber from Access
    check_time DATETIME,             -- Corresponds to checktime from Access
    check_type VARCHAR(10),          -- Corresponds to checktype from Access (O=Out, I=In)
    verify_code VARCHAR(10),         -- Corresponds to verifycode from Access
    sensor_id VARCHAR(50),           -- Corresponds to sensorid from Access
    work_code VARCHAR(50),           -- Corresponds to workcode from Access
    device_sn VARCHAR(50),           -- Corresponds to sn from Access
    raw_data TEXT,                   -- Full raw record from Access
    server_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When record was processed by server
    INDEX idx_badge_time (badge_number, check_time),
    INDEX idx_check_time (check_time),
    INDEX idx_device_sn (device_sn)
);

-- Optional: Insert a sample record to test the structure
-- INSERT INTO access_device_logs (badge_number, check_time, check_type, verify_code, sensor_id, work_code, device_sn, raw_data)
-- VALUES ('12345', '2026-01-16 10:30:00', 'I', '1', 'SENSOR001', 'WORK001', 'HIP_ACCESS_DB', 'Sample raw data');