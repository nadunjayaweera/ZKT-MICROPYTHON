ZKT attendance export — verified first-chunk alignment

The machine reported 2,314,244 bytes: 4-byte data header + 57,856 records * 40 bytes.
The first three records decoded correctly in the user's diagnostic.

Run main.py. It automatically requests 2048-byte chunks, skips the initial
4-byte data-size header, carries any partial 40-byte record between chunks,
and writes a temporary JSON file. The final attendance.json is renamed only
on successful completion and record-count validation.

IMPORTANT: This has not been tested through a full transfer on the physical
machine. A ~5MB or larger JSON export is likely to exceed ESP8266 flash
filesystem space. If storage is insufficient, stream parsed records to a
backend rather than saving a complete JSON file locally. No commands in
this export clear device attendance logs.
