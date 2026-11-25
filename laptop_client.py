"""Example GET-based pagination client for laptop (Python 3)."""
import json
from urllib.request import Request, urlopen
from urllib.parse import quote

BASE_URL = "http://127.0.0.1:8080"  # Or http://ESP32_IP:8080
API_TOKEN = "1234567890"

# Store next_cursor in YOUR backend database only AFTER saving the records.
cursor = None
while True:
    value = 'null' if cursor is None else quote(cursor, safe='.')
    req = Request(BASE_URL + '/attendance?cursor=' + value + '&limit=10',
                  headers={'X-API-Key': API_TOKEN})
    with urlopen(req, timeout=30) as response:
        page = json.load(response)
    print('Received:', page['count'], 'total:', page['total_records'])
    # TODO: insert page['records'] into database transaction here.
    # TODO: commit page['next_cursor'] in the SAME transaction.
    cursor = page['next_cursor']
    if not page['has_more']:
        print('Sync complete; persist this cursor:', cursor)
        break
