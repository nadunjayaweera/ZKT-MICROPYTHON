"""MicroPython WiFiManager-like AP setup portal, no Arduino dependencies.
Connect phone to setup SSID; visit http://192.168.4.1/. Password printed
on USB serial, stored in setup_ap_password.txt for reuse.
"""
import socket
import time
try:
    import os
except ImportError:
    import uos as os
try:
    import network
except ImportError:
    network = None
import settings_store
import device_config

AP_PASSWORD_FILE = 'setup_ap_password.txt'


def _hex(b):
    return ''.join('%02x' % n for n in b)


def _ap_password():
    try:
        with open(AP_PASSWORD_FILE) as f:
            p = f.read().strip()
        if len(p) >= 8:
            return p
    except OSError:
        pass
    try:
        import os as _os
        raw = _os.urandom(9)
    except Exception:
        from machine import unique_id
        raw = unique_id()
    secret = _hex(raw)
    p = 'ZKT' + secret[:12]
    with open(AP_PASSWORD_FILE, 'w') as f:
        f.write(p)
    return p


def _unquote(value):
    raw = bytearray()
    i = 0
    while i < len(value):
        c = value[i]
        if c == 43:
            raw.append(32)
        elif c == 37 and i + 2 < len(value):
            try:
                raw.append(int(value[i + 1:i + 3], 16))
                i += 2
            except ValueError:
                raw.append(c)
        else:
            raw.append(c)
        i += 1
    return bytes(raw).decode('utf-8')


def _parse_form(data):
    out = {}
    for item in data.split(b'&'):
        key, sep, val = item.partition(b'=')
        if sep:
            out[_unquote(key)] = _unquote(val)
    return out


def _escape(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;'))


def _page(saved, message=''):
    saved = saved or {}
    fields = (
        ('wifi_ssid', 'Wi-Fi SSID', 'text', ''),
        ('wifi_password', 'Wi-Fi password', 'password', ''),
        ('device_ip', 'ZKT machine IP', 'text', '192.168.1.236'),
        ('device_port', 'ZKT port', 'number', '4370'),
        ('device_id', 'Device ID (stable)', 'text', 'zkt-001'),
        ('backend_base_url', 'Backend URL', 'url', 'http://192.168.1.38:3000'),
        ('backend_api_key', 'Backend API key', 'password', ''),
        ('page_limit', 'Requested records per page (positive integer)', 'number', '5'),
    )
    controls = []
    for key, title, kind, default in fields:
        # Never reflect a saved password or API key back to the browser.
        value = '' if kind == 'password' else saved.get(key, default)
        controls.append('<label>%s<input name="%s" type="%s" value="%s" required></label>' %
                        (_escape(title), key, kind, _escape(value)))
    return ('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>ZKT Setup</title><style>body{font:16px Arial;margin:0;background:#f5f6f8;color:#18212b}'
            'main{max-width:440px;margin:30px auto;padding:22px;background:white;border-radius:14px}'
            'input{box-sizing:border-box;width:100%%;padding:12px;border:1px solid #ccc;border-radius:8px;margin:6px 0 15px}'
            'label{display:block;font-size:14px;font-weight:bold}button{background:#196fe3;border:0;color:white;padding:14px;width:100%%;border-radius:8px;font-weight:bold}'
            '.msg{color:#116b35}</style></head><body><main><h2>ZKT Attendance Setup</h2>'
            '<p>Enter the local biometric device and backend connection details.</p>'
            '<p class="msg">%s</p><form action="/save" method="post">%s<button>Save and connect</button></form>'
            '<p>After saving, the ESP32 joins your Wi-Fi and starts syncing automatically.</p></main></body></html>' %
            (_escape(message), ''.join(controls)))


def _reply(client, status, body):
    data = body.encode('utf-8')
    header = ('HTTP/1.1 %s\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: %d\r\n'
              'Connection: close\r\nCache-Control: no-store\r\n\r\n' % (status, len(data))).encode()
    client.write(header)
    client.write(data)


def run(led, message=''):
    led.set('setup')
    sta = network.WLAN(network.STA_IF)
    sta.active(False)
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    password = _ap_password()
    try:
        from machine import unique_id
        suffix = _hex(unique_id())[-4:].upper()
    except Exception:
        suffix = 'ESP32'
    ssid = device_config.SETUP_AP_PREFIX + suffix
    ap.config(essid=ssid, password=password, authmode=3)
    try:
        ap.ifconfig((device_config.SETUP_AP_IP, '255.255.255.0', device_config.SETUP_AP_IP, device_config.SETUP_AP_IP))
    except Exception:
        pass
    print('SETUP MODE - Connect phone to Wi-Fi:', ssid)
    print('SETUP PASSWORD:', password)
    print('Open browser: http://' + ap.ifconfig()[0] + '/')
    if message:
        print('Setup reason:', message)
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 80))
    server.listen(2)
    server.settimeout(2)
    result = None
    try:
        while True:
            try:
                conn, addr = server.accept()
            except OSError:
                continue
            try:
                conn.settimeout(5)
                fp = conn.makefile('rb')
                start = fp.readline()
                parts = start.split()
                if len(parts) < 2:
                    continue
                method = parts[0]
                path = parts[1]
                length = 0
                while True:
                    line = fp.readline()
                    if line in (b'', b'\r\n', b'\n'):
                        break
                    k, _, v = line.partition(b':')
                    if k.strip().lower() == b'content-length':
                        length = int(v.strip())
                if method == b'POST' and path == b'/save':
                    if length < 1 or length > 4096:
                        _reply(conn, '413 Payload Too Large', '<p>Form too large.</p>')
                        continue
                    payload = fp.read(length)
                    if len(payload) != length:
                        _reply(conn, '400 Bad Request', '<p>Incomplete form.</p>')
                        continue
                    values = _parse_form(payload)
                    try:
                        result = settings_store.save(values)
                        _reply(conn, '200 OK', '<h2>Saved!</h2><p>ESP32 is connecting. Rejoin your normal Wi-Fi.</p>')
                        print('Settings saved; restarting sync')
                        break
                    except Exception as e:
                        _reply(conn, '400 Bad Request', _page(values, str(e)))
                else:
                    _reply(conn, '200 OK', _page(settings_store.load(), message))
            except Exception as exc:
                print('Setup client error:', exc)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    finally:
        server.close()
        ap.active(False)
    return result
