-- IMPORTANT: Run only after verifying that record 57859 is the last valid
-- record on the same physical ZKT device, and AFTER backing up both tables.
-- This is a ONE-TIME repair for the specific data shown in the conversation.
-- Stop the ESP32 sync process before executing this script.
-- Inspect first:
SELECT record_index, user_sn, device_user_id, record_time,
       JSON_UNQUOTE(JSON_EXTRACT(raw_record, '$.raw_hex')) AS raw_hex
FROM zkt_attendance_records
WHERE device_id = 'zkt-001' AND record_index BETWEEN 57855 AND 57860
ORDER BY record_index;

-- Backup BEFORE any deletion (run once; choose unique backup names):
CREATE TABLE zkt_attendance_records_backup_20261123 LIKE zkt_attendance_records;
INSERT INTO zkt_attendance_records_backup_20261123
SELECT * FROM zkt_attendance_records WHERE device_id = 'zkt-001';
CREATE TABLE zkt_sync_devices_backup_20261123 LIKE zkt_sync_devices;
INSERT INTO zkt_sync_devices_backup_20261123
SELECT * FROM zkt_sync_devices WHERE device_id = 'zkt-001';

-- Confirm the backup exists and has the expected rows before continuing.
-- The following repair retains valid records through 57859 and removes only
-- record 57860 onward. It derives the cursor from the actual saved raw_hex.
START TRANSACTION;
SELECT committed_cursor, total_saved FROM zkt_sync_devices
WHERE device_id='zkt-001' FOR UPDATE;
-- STOP if the live database has progressed beyond 57860 since your snapshot.
DELETE FROM zkt_attendance_records
WHERE device_id='zkt-001' AND record_index >= 57860;
UPDATE zkt_sync_devices
SET committed_cursor = (
  SELECT CONCAT(record_index, '.', JSON_UNQUOTE(JSON_EXTRACT(raw_record, '$.raw_hex')))
  FROM zkt_attendance_records
  WHERE device_id='zkt-001' AND record_index=57859
),
 total_saved = (
  SELECT COUNT(*) FROM zkt_attendance_records WHERE device_id='zkt-001'
)
WHERE device_id='zkt-001';
SELECT committed_cursor, total_saved FROM zkt_sync_devices
WHERE device_id='zkt-001';
-- Review the SELECT output. COMMIT only if correct, otherwise ROLLBACK.
-- COMMIT;
-- ROLLBACK;
