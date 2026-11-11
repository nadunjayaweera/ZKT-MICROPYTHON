"""Same HTTP GET API on CPython laptop and MicroPython ESP32."""
import utils.session
import socket
import gc
try:
    import ujson as json
except ImportError:
    import json
from zklib import ZKLib
import config


def wifi_connect():
    try:
        import network
    except ImportError:
        print("Laptop mode: using existing network connection")
        return
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if not sta.isconnected():
        print("Connecting Wi-Fi...")
        sta.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        import time
        for _ in range(60):
            if sta.isconnected():
                break
            time.sleep_ms(500)
    if not sta.isconnected():
        raise RuntimeError("Wi-Fi connection failed")
    print("ESP32 IP:", sta.ifconfig()[0])


def _query_parts(path):
    if '?' not in path:
        return path, {}
    route, query = path.split('?', 1)
    params = {}
    for entry in query.split('&'):
        if '=' in entry:
            key, val = entry.split('=', 1)
            params[key] = val
    return route, params


def get_page(cursor, limit):
    zk = ZKLib(config.DEVICE_IP, config.DEVICE_PORT,
               timeout=config.DEVICE_TIMEOUT_MS)
    try:
        zk.create_socket()
        zk.connect()
        return zk.attendance_page(cursor=cursor, limit=limit)
    finally:
        try:
            zk.disconnect()
        except Exception:
            pass
        gc.collect()


def _send_json(client, status, data):
    payload = json.dumps(data).encode('utf-8')
    head = ('HTTP/1.0 ' + status + '\r\n'
            'Content-Type: application/json; charset=utf-8\r\n'
            'Content-Length: ' + str(len(payload)) + '\r\n'
            'Access-Control-Allow-Origin: *\r\n'
            'Connection: close\r\n\r\n').encode('ascii')
    client.sendall(head)
    client.sendall(payload)


def serve():
    wifi_connect()
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((config.HTTP_HOST, config.HTTP_PORT))
    listener.listen(2)
    print('HTTP GET /attendance?cursor=null&limit=10 on port', config.HTTP_PORT)
    while True:
        client, remote = listener.accept()
        try:
            client.settimeout(20)
            # Read HTTP request headers with a strict cap.
            request = b''
            while b'\r\n\r\n' not in request and len(request) < 2048:
                part = client.recv(min(512, 2048 - len(request)))
                if not part:
                    break
                request += part
            if b'\r\n\r\n' not in request:
                _send_json(client, '400 Bad Request', {'success': False, 'error': 'Invalid headers'})
                continue
            lines = request.decode('utf-8').split('\r\n')
            method, target, _ = lines[0].split(' ', 2)
            route, params = _query_parts(target)
            supplied_token = ''
            for line in lines[1:]:
                if line.lower().startswith('x-api-key:'):
                    supplied_token = line.split(':', 1)[1].strip()
            if supplied_token != config.API_TOKEN or config.API_TOKEN.startswith('CHANGE_ME'):
                _send_json(client, '401 Unauthorized', {'success': False, 'error': 'Unauthorized'})
            elif method != 'GET':
                _send_json(client, '405 Method Not Allowed', {'success': False, 'error': 'GET only'})
            elif route == '/health':
                _send_json(client, '200 OK', {'success': True, 'platform': 'ESP32 or laptop'})
            elif route == '/attendance':
                value = params.get('cursor')
                cursor = None if value in (None, '', 'null') else value
                try:
                    limit = int(params.get('limit', '10'))
                    if limit < 1 or limit > 20:
                        raise ValueError('limit must be 1..20')
                    result = get_page(cursor, limit)
                    _send_json(client, '200 OK', result)
                except ValueError as e:
                    msg = str(e)
                    status = '409 Conflict' if msg.startswith('CURSOR_STALE') else '400 Bad Request'
                    _send_json(client, status, {'success': False, 'error': msg})
                except Exception as e:
                    print('ZKT request failed:', e)
                    _send_json(client, '502 Bad Gateway', {'success': False, 'error': str(e)})
            else:
                _send_json(client, '404 Not Found', {'success': False, 'error': 'Not found'})
        except Exception as e:
            print('HTTP error:', e)
        finally:
            try:
                client.close()
            except Exception:
                pass
            gc.collect()

if __name__ == '__main__':
    serve()
