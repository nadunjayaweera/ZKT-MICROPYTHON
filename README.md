# ZKT GET Attendance API – Laptop + ESP32

This uses your uploaded ZKT 40-byte attendance parser and CMD_DATA_RDY chunk reader.
No external dependencies on either platform.

## Laptop (Python 3)
1. Edit `config.py` (`DEVICE_IP`, `API_TOKEN`).
2. Connect laptop to same network as ZKT device (TCP 4370 must be reachable).
3. Run `python main.py` from project directory.
4. Request `GET http://127.0.0.1:8080/attendance?cursor=null&limit=10` with header `X-API-Key`.

Example in PowerShell:
```powershell
$headers = @{ "X-API-Key" = "YOUR_SECRET" }
Invoke-RestMethod -Uri "http://127.0.0.1:8080/attendance?cursor=null&limit=10" -Headers $headers
```

## ESP32 (MicroPython)
1. Flash MicroPython onto ESP32.
2. Configure SSID/password, DEVICE_IP and token in `config.py`.
3. Upload `main.py`, `config.py`, and `zklib/` to ESP32.
4. Reset board; find its local IP from serial console.
5. GET `http://ESP32_IP:8080/attendance?cursor=null&limit=10` with X-API-Key header.

## API
- `GET /health` requires the API key.
- `GET /attendance?cursor=null&limit=10` returns first 10 records.
- Next GET: copy exact `next_cursor` from prior response into `cursor`.
- Limit: 1 to 20 records per page.
- At end, save `next_cursor` and send it on a later polling cycle to get new appended records.
- When none added: `count: 0`, `has_more: false`, `next_cursor` unchanged.
- `409 CURSOR_STALE`: rescan/deduplicate; DO NOT silently skip missing records.

## Important limitations
- ZKT protocol is not a native 'since timestamp' query. Preparing the buffer anew may still cost work on the device, even when reading a small page.
- Firmware must allow arbitrary nonzero chunk offsets in a NEW buffer. Test the second page and a board restart before production use.
- Cursor is an index + exact prior 40-byte record hex (not a timestamp). It detects many shifts/changes, but not edits to unrelated earlier records.
- A cursor only works if device history remains ordered and retained; clearing/reordering logs invalidates this scheme.
- For reliable synchronization, store each page and its cursor atomically in your backend DB; use idempotent inserts/deduplication.
- Same physical ZKT device should not be queried concurrently from both laptop and ESP32; coordinate clients.
- HTTP endpoint is plaintext, intended only for trusted LAN/VPN. Do not forward this port to the public internet; change the API key.
- The ESP32 is only a gateway. No attendance.json file is generated and no attendance data is cleared from the biometric machine.
- `next_cursor` can be long (about 85 characters); URLs shown are safe for this cursor encoding.
