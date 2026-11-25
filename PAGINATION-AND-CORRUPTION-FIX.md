# ZKT attendance: unrestricted requested pagination and invalid-record quarantine

## What changed
- Removed the old 20-record validation in `settings_store.py`, `zklib/tcp.py`, `wifi_portal.py`, `web_config.py` and the MySQL `server.js` batch validator.
- A positive requested page limit can now be 50, 100, 500, 1000, etc.
- **Actual ESP32 transport pages are deliberately smaller**, based on available heap and the existing 12 KB HTTP client request limit. This is required for reliable ESP32 operation; requesting 1000 does not mean loading 1000 records into RAM or sending a single giant HTTP request. The ESP32 automatically sends multiple batches until caught up.
- ZKT device reads are limited to 40 records (1600 bytes) per chunk, with multiple reads as needed.
- Every new record includes `raw_hex` and `validation_status`. Suspicious records are marked `INVALID` and `validation_reason` is supplied. They are still stored in MySQL as quarantined raw evidence so record positions and cursors remain continuous.
- Invalid records should be **excluded from payroll/HR attendance processing**. They are not repaired or converted into a guessed timestamp.
- `inspect-corrupt-records.sql` is a read-only query for both flagged new records and suspicious historical rows.

## Files to upload to ESP32 in Thonny
Replace these files on the MicroPython device:
- `/settings_store.py`
- `/wifi_portal.py`
- `/web_config.py`
- `/zklib/tcp.py`
- `/zklib/helpers.py`

Do not delete `/settings.json` or the `zklib` directory. `main.py` does not need to change.

## Backend update
Replace `ZKT-MYSQL-BACKEND/backend-mysql/server.js` in your existing Node.js backend, preserving your local `.env`, and restart `npm start`. The existing MySQL schema is compatible and requires **no ALTER TABLE**. New status and raw bytes are stored in the existing `raw_record` JSON column.

## Setting pagination
Open `http://ESP32-IP:8080`, sign in, enter any positive number (e.g. `1000`) for Requested records per page, and save/restart. The effective transport page size will be lower on memory-constrained boards; this is intentional.

## Previously committed suspicious record 57857
The previous row was already committed to MySQL. Uploading this fix **will not automatically rewrite or re-fetch** that historical row. Run `inspect-corrupt-records.sql` to locate it. Treat its 2103 timestamp and empty user ID as invalid; do not use it in payroll.
Do not edit the saved cursor or delete rows without a planned, backed-up replay.
If no additional ZKT records exist, the ESP32 correctly reports no new attendance.

## Important
This is a conservative quarantine and validation fix, not proof of the cause of the corrupt bytes. A faulty device buffer or wrong decoder offset can still create invalid data. To diagnose the root cause, capture the `raw_hex` for suspicious records and compare with the device's own attendance export.
The web server and sync running concurrently may reduce free heap, which further lowers the effective transport page size.
