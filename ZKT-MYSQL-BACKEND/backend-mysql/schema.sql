-- Execute in synera_v1_dev_db (or the database selected in DATABASE_URL).
-- These tables are isolated from existing HRIS attendance tables.
CREATE TABLE IF NOT EXISTS zkt_sync_devices (
  device_id VARCHAR(64) NOT NULL PRIMARY KEY,
  committed_cursor VARCHAR(128) NULL,
  total_saved BIGINT UNSIGNED NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS zkt_attendance_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  device_id VARCHAR(64) NOT NULL,
  record_index BIGINT UNSIGNED NOT NULL,
  user_sn BIGINT UNSIGNED NOT NULL,
  device_user_id VARCHAR(64) NOT NULL,
  record_time VARCHAR(32) NOT NULL,
  device_ip VARCHAR(100) NULL,
  raw_record JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_zkt_device_record_index (device_id, record_index),
  KEY idx_zkt_device_time (device_id, record_time),
  CONSTRAINT fk_zkt_records_device FOREIGN KEY (device_id) REFERENCES zkt_sync_devices(device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
