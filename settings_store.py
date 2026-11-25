"""Small persistent JSON configuration with atomic replacement."""
import json
try:
    import os
except ImportError:
    import uos as os

SETTINGS_FILE = 'settings.json'

KEYS = ('wifi_ssid', 'wifi_password', 'device_ip', 'device_port',
        'device_id', 'backend_base_url', 'backend_api_key', 'page_limit')

def load():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            values = json.load(f)
        return values if isinstance(values, dict) else None
    except (OSError, ValueError):
        return None

def validate(values):
    if not isinstance(values, dict):
        raise ValueError('Invalid settings format')
    for field in ('device_ip', 'device_id', 'backend_base_url', 'backend_api_key'):
        if not isinstance(values.get(field), str) or not values[field].strip():
            raise ValueError('Missing: ' + field)
    # Wi-Fi credentials are optional when running on a Windows/Linux laptop.
    # ESP32 Wi-Fi connection is handled separately by connect_wifi().
    for field in ('wifi_ssid', 'wifi_password'):
        if not isinstance(values.get(field, ''), str):
            raise ValueError('Invalid: ' + field)
    for field in ('wifi_ssid', 'device_ip', 'device_id', 'backend_base_url'):
        if len(values[field]) > 160:
            raise ValueError('Field too long: ' + field)
    if len(values.get('wifi_password', '')) > 63 or len(values['backend_api_key']) > 200:
        raise ValueError('Password/key too long')
    # MicroPython builds may not implement str.isalnum(); validate explicitly.
    device_id = values['device_id']
    if not device_id:
        raise ValueError('Device ID must be alphanumeric, - or _')
    for ch in device_id:
        if not (('0' <= ch <= '9') or ('A' <= ch <= 'Z') or
                ('a' <= ch <= 'z') or ch == '-' or ch == '_'):
            raise ValueError('Device ID must be alphanumeric, - or _')
    if not (values['backend_base_url'].startswith('http://') or
            values['backend_base_url'].startswith('https://')):
        raise ValueError('Backend URL must use http:// or https://')
    if values['backend_base_url'].endswith('/'):
        values['backend_base_url'] = values['backend_base_url'].rstrip('/')
    if '@' in values['backend_base_url'] or '?' in values['backend_base_url']:
        raise ValueError('Invalid backend URL')
    try:
        values['device_port'] = int(values.get('device_port', 4370))
        values['page_limit'] = int(values.get('page_limit', 5))
    except (ValueError, TypeError):
        raise ValueError('Invalid numeric fields')
    if not 1 <= values['device_port'] <= 65535 or values['page_limit'] < 1:
        raise ValueError('Device port must be 1..65535 and page limit must be positive')
    return values

def save(values):
    values = validate(values)
    temp = SETTINGS_FILE + '.tmp'
    with open(temp, 'w') as f:
        json.dump({k: values[k] for k in KEYS if k in values}, f)
        f.flush()
    # MicroPython os.rename() overwrite behavior varies, so remove old file first.
    # If power is lost between remove and rename, .tmp may remain for recovery.
    try:
        os.remove(SETTINGS_FILE)
    except OSError:
        pass
    os.rename(temp, SETTINGS_FILE)
    return values
