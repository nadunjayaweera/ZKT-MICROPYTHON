-- Read-only review of records with suspicious values, including historical rows.
SELECT device_id, record_index, device_user_id, record_time,
       JSON_UNQUOTE(JSON_EXTRACT(raw_record, '$.validation_status')) AS validation_status,
       JSON_UNQUOTE(JSON_EXTRACT(raw_record, '$.validation_reason')) AS validation_reason,
       raw_record
FROM zkt_attendance_records
WHERE JSON_UNQUOTE(JSON_EXTRACT(raw_record, '$.validation_status')) = 'INVALID'
   OR TRIM(device_user_id) = ''
   OR CAST(SUBSTRING_INDEX(record_time, '-', 1) AS UNSIGNED) > 2035
ORDER BY device_id, record_index DESC;
