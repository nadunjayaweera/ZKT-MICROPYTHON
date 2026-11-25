# Terminal record recovery

The device sometimes reports a final 40-byte record containing user_sn=0, empty ID, and the ZKT zero timestamp. The ESP32 now detects this exact terminal signature, excludes it from upload, and leaves the cursor at the last valid record. On subsequent polls the device is re-read and the position is retried. Any invalid nonterminal record stops that page without committing it.

This fix is conservative and intentionally does not treat arbitrary malformed trailing data as harmless. If the terminal signature changes, diagnose it rather than advancing the cursor.

## Repair the previously committed invalid row

Stop ESP32 sync, back up MySQL tables, and inspect `REPAIR-TRAILING-RECORD-57860.sql`. It is specific to the supplied record indices. Confirm row 57859 is valid and row 57860 is invalid. The SQL defaults to no COMMIT so you can review the result first. Never edit only committed_cursor while leaving later rows in the records table.

## Install

Upload `zklib/tcp.py` to the ESP32 under `/zklib/` and restart. No backend code or database schema changes required. The existing invalid record will not be deleted automatically.

## Limitations

This does not prove whether the trailing bytes are firmware metadata, transfer artifact, or a genuine damaged attendance record. It avoids cursor advancement over the exact suspicious signature. A corrupt middle record will halt sync and require investigation. No physical ZKT hardware test was performed.
