"""LAN configuration service for ESP32 MicroPython.
Visit http://<ESP32-IP>:8080, sign in using a local admin password.
A dedicated thread keeps the portal reachable while attendance sync runs.
"""
import socket
import time
import gc
import settings_store

try:
    import _thread
    from machine import reset, unique_id
    import os
    import network
except ImportError:
    _thread = None

PORT = 8080
AUTH_FILE = 'web_admin_password.txt'
SESSION_FILE = None
MAX_BODY = 4096
_active = False
_password = None
_token = None
_login_fails = 0
_lockout_until = 0

def _hex(data):
    return ''.join('%02x' % n for n in data)

def _admin_password():
    try:
        with open(AUTH_FILE, 'r') as f:
            value = f.read().strip()
        if len(value) >= 12:
            return value
    except OSError:
        pass
    try:
        random_bytes = os.urandom(12)
    except Exception:
        random_bytes = unique_id()
    value = 'ZKT-' + _hex(random_bytes)
    with open(AUTH_FILE, 'w') as f:
        f.write(value)
    return value

def _url_decode(data):
    b = bytearray()
    i = 0
    while i < len(data):
        c = data[i]
        if c == 43:
            b.append(32)
        elif c == 37 and i + 2 < len(data):
            try:
                b.append(int(data[i+1:i+3], 16))
                i += 2
            except ValueError:
                b.append(c)
        else:
            b.append(c)
        i += 1
    return bytes(b).decode('utf-8')

def _form(raw):
    result = {}
    for part in raw.split(b'&'):
        k, sep, v = part.partition(b'=')
        if sep:
            result[_url_decode(k)] = _url_decode(v)
    return result

def _escape(s):
    return (str(s).replace('&','&amp;').replace('<','&lt;')
            .replace('>','&gt;').replace('"','&quot;').replace("'",'&#39;'))

def _html(content):
    return ('<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta charset="utf-8"><title>ZKT Device</title><style>'
            'body{font:16px Arial;background:#f2f5fa;color:#142235;margin:0}'
            'main{max-width:460px;margin:28px auto;padding:24px;background:#fff;border-radius:12px}'
            'input{display:block;box-sizing:border-box;width:100%;padding:11px;margin:5px 0 14px;border:1px solid #bac4d2;border-radius:6px}'
            'label{font-size:14px;font-weight:bold}button{background:#1769db;color:#fff;border:0;padding:13px 18px;border-radius:7px}'
            'p{line-height:1.5}small{color:#58677b}</style></head><body><main>' + content + '</main></body></html>')

def _login_page(message=''):
    return _html('<h2>ZKT ESP32 Admin</h2><p>Sign in to update Wi-Fi and device configuration.</p>'
                 '<p>%s</p><form method="post" action="/login">'
                 '<label>Admin password<input name="password" type="password" autocomplete="current-password" required></label>'
                 '<button>Sign in</button></form>' % _escape(message))

def _settings_page(message=''):
    saved = settings_store.load() or {}
    fields = (
        ('wifi_ssid','Wi-Fi SSID','text'),
        ('wifi_password','Wi-Fi password','password'),
        ('device_ip','ZKT machine IP','text'),
        ('device_port','ZKT port','number'),
        ('device_id','Device ID','text'),
        ('backend_base_url','Backend URL','text'),
        ('backend_api_key','Backend API key','password'),
        ('page_limit','Requested records per page (positive integer)','number'),
    )
    html = '<h2>ZKT Device Settings</h2><p>%s</p>' % _escape(message)
    html += '<p><small>Leave password/key fields empty to keep existing values.</small></p>'
    html += '<form action="/save" method="post">'
    for key, label, kind in fields:
        value = '' if kind == 'password' else str(saved.get(key,''))
        html += ('<label>%s<input name="%s" type="%s" value="%s" %s></label>' %
                 (_escape(label),key,kind,_escape(value),
                  '' if kind == 'password' else 'required'))
    html += '<button>Save &amp; restart ESP32</button></form>'
    html += '<p><a href="/logout">Log out</a></p>'
    return _html(html)

def _respond(client, status, content, cookie=None):
    body = content.encode('utf-8')
    head = ('HTTP/1.1 %s\r\nContent-Type: text/html; charset=utf-8\r\n'
            'Content-Length: %d\r\nCache-Control: no-store\r\n'
            'X-Content-Type-Options: nosniff\r\n'
            'X-Frame-Options: DENY\r\nConnection: close\r\n' % (status,len(body)))
    if cookie is not None:
        head += 'Set-Cookie: session=%s; HttpOnly; SameSite=Strict; Path=/\r\n' % cookie
    client.write((head+'\r\n').encode('utf-8'))
    client.write(body)

def _new_token():
    try:
        return _hex(os.urandom(20))
    except Exception:
        return _hex(unique_id()) + str(time.ticks_ms())

def _handle(conn):
    global _token, _login_fails, _lockout_until
    conn.settimeout(5)
    fp = conn.makefile('rb')
    line = fp.readline()
    parts = line.split()
    if len(parts) < 2:
        return
    method, path = parts[0], parts[1].split(b'?')[0]
    length = 0
    cookies = ''
    origin = ''
    host = ''
    for _ in range(50):
        line = fp.readline()
        if line in (b'',b'\r\n',b'\n'):
            break
        k,_,v = line.partition(b':')
        k=k.strip().lower()
        if k==b'content-length':
            length=int(v.strip())
        elif k==b'cookie':
            cookies=v.decode('utf-8').strip()
        elif k==b'origin':
            origin=v.decode('utf-8').strip()
        elif k==b'host':
            host=v.decode('utf-8').strip()
    if length < 0 or length > MAX_BODY:
        _respond(conn,'413 Payload Too Large',_html('<p>Request too large.</p>'))
        return
    if method==b'POST' and origin and host and origin != 'http://' + host:
        _respond(conn,'403 Forbidden',_html('<p>Invalid request origin.</p>'))
        return
    body=fp.read(length) if method==b'POST' and length else b''
    if len(body)!=length and method==b'POST':
        _respond(conn,'400 Bad Request',_html('<p>Incomplete request.</p>'))
        return
    fields=_form(body)
    authorized = _token is not None and ('session='+_token) in (';'.join(
        p.strip() for p in cookies.split(';')))
    if path==b'/login' and method==b'POST':
        now=time.ticks_ms()
        if time.ticks_diff(_lockout_until,now)>0:
            _respond(conn,'429 Too Many Requests',_login_page('Too many attempts. Try again later.'))
        elif fields.get('password','')==_password:
            _login_fails=0
            _token=_new_token()
            _respond(conn,'200 OK',_settings_page('Signed in.'),_token)
        else:
            _login_fails+=1
            if _login_fails>=5:
                _lockout_until=time.ticks_add(now,60000)
                _login_fails=0
            _respond(conn,'401 Unauthorized',_login_page('Incorrect password.'))
        return
    if path==b'/logout':
        _token=None
        _respond(conn,'200 OK',_login_page('Logged out.'),'deleted; Max-Age=0')
        return
    if not authorized:
        _respond(conn,'200 OK',_login_page())
        return
    if path==b'/save' and method==b'POST':
        current=settings_store.load() or {}
        values={}
        for key in settings_store.KEYS:
            value=fields.get(key,'')
            if key in ('wifi_password','backend_api_key') and not value:
                value=current.get(key,'')
            values[key]=value
        try:
            settings_store.save(values)
        except Exception as exc:
            _respond(conn,'400 Bad Request',_settings_page('Save failed: '+str(exc)))
            return
        _respond(conn,'200 OK',_html('<h2>Settings saved</h2><p>ESP32 is restarting. '
                 'Reconnect to the new Wi-Fi if you changed its SSID or password.</p>'))
        print('Web settings saved; restarting ESP32')
        time.sleep(1)
        reset()
        return
    _respond(conn,'200 OK',_settings_page())

def _serve():
    global _active
    server=None
    try:
        server=socket.socket()
        server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        server.bind(('0.0.0.0',PORT))
        server.listen(2)
        server.settimeout(2)
        print('LAN settings portal: http://<ESP32-IP>:%d' % PORT)
        while True:
            try:
                conn, addr=server.accept()
            except OSError:
                continue
            try:
                _handle(conn)
            except Exception as exc:
                print('Web config request error:',exc)
            finally:
                try: conn.close()
                except Exception: pass
            gc.collect()
    except Exception as exc:
        print('Web config server stopped:',exc)
    finally:
        _active=False
        if server:
            server.close()

def start():
    global _active,_password
    if _active:
        return
    if _thread is None:
        print('Web configuration requires MicroPython _thread support')
        return
    _password=_admin_password()
    print('LAN WEB ADMIN PASSWORD:',_password)
    _active=True
    try:
        _thread.start_new_thread(_serve,())
    except Exception:
        _active=False
        raise
