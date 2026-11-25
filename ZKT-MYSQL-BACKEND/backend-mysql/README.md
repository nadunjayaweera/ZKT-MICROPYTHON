# ZKT Attendance Backend — MySQL

Replaces the uploaded JSON-lines Node.js backend with MySQL. The ESP32 HTTP endpoints, request validation, bearer token authentication, cursor format, and response shapes are preserved.

## Installation

1. Back up your existing `backend-json/data/attendance.jsonl` and `.env` before changing anything.
2. **Stop the old JSON backend and pause ESP32 sync** to prevent split cursor histories.
3. Run `schema.sql` in your existing MySQL database (`synera_v1_dev_db`). It creates only two new `zkt_` tables.
4. Copy `.env.example` to `.env`, then fill in your actual `DATABASE_URL` and `DEVICE_API_KEY` (the same API key already configured on ESP32). Do not commit `.env`.
5. In this folder run `npm install`, then `npm start`.
6. Open `http://YOUR-BACKEND-IP:3000/health`; expected `{"success":true,"storage":"ok","database":"mysql"}`.
7. Restart ESP32 sync. **No ESP32 code changes required** if the backend address, port, and API key remain the same.

## Existing JSON attendance data: migrate before restarting ESP32

If your old JSON backend already received attendance, **do not start the ESP32 against an empty MySQL cursor**. The ESP32 would begin again from the first device record. Instead:

1. Keep the old backend stopped and ESP32 sync paused.
2. Run the schema, configure `.env`, and install dependencies.
3. Run: `node import-json.js "../backend-json/data/attendance.jsonl"` (adjust path).
4. The import reads the journal sequentially, commits each batch transactionally, and restores the exact per-device cursor. It is restartable: already committed batches are acknowledged as replays.
5. Start the new backend and then resume the ESP32.

**Important:** Do not delete the original JSON file until you have verified the imported record counts and cursor values. A failed import due to cursor mismatch means the target MySQL database already contains divergent data; do not overwrite the cursor manually.

## MySQL schema

- `zkt_sync_devices`: one row per device, last committed cursor and total saved records.
- `zkt_attendance_records`: one row per attendance event, stable `record_index` per device, original record JSON and fields for querying.

The backend uses an InnoDB transaction and a row lock (`SELECT ... FOR UPDATE`) to atomically insert each batch and advance its cursor. A unique `(device_id, record_index)` key protects against duplicate insertion.

## Existing API endpoints (unchanged)

- `GET /health` (no authentication)
- `GET /api/attendance/sync-state?device_id=zkt-001`
- `POST /api/attendance/batches`
- `GET /api/attendance/records?device_id=zkt-001&offset=0&limit=20`

Attendance endpoints require `Authorization: Bearer YOUR_DEVICE_API_KEY`.

## Security

The database URL contains a password: store it only in `.env`. Rotate any password previously shared publicly or in chat. Prefer a dedicated MySQL account restricted to the backend server's IP, with privileges only on the two `zkt_` tables. Never expose MySQL port 3306 to the public internet. If MySQL is on a separate host, allow port 3306 only from the backend server and enable TLS when supported by your deployment.

The SQL tables store device-reported attendance timestamps as strings to preserve the source format. Interpret them in the correct local timezone when integrating with HRIS payroll or reporting.
