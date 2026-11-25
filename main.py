"""ESP32 provisioning + outbound paginated ZKT attendance sync.
CPython laptop mode also supported using settings.json + wired/Wi-Fi network.
"""
import gc
import time
import device_config
import settings_store
from led_status import StatusLED
from zklib import ZKLib
from http_client import request_json, HTTPError


def sleep_seconds(s):
    time.sleep(s)


def get_wlan():
    try:
        import network
        return network.WLAN(network.STA_IF)
    except ImportError:
        return None


def connect_wifi(cfg, led):
    wlan = get_wlan()
    if wlan is None:
        print('Laptop mode: using host network')
        led.set('ready')
        return True
    wlan.active(True)
    if wlan.isconnected():
        print('Wi-Fi IP:', wlan.ifconfig()[0])
        led.set('ready')
        return True
    led.set('wifi')
    print('Connecting Wi-Fi:', cfg['wifi_ssid'])
    try:
        wlan.disconnect()
    except Exception:
        pass
    wlan.connect(cfg['wifi_ssid'], cfg['wifi_password'])
    for _ in range(device_config.WIFI_CONNECT_SECONDS * 2):
        if wlan.isconnected():
            print('Wi-Fi IP:', wlan.ifconfig()[0])
            led.set('ready')
            return True
        sleep_seconds(0.5)
    print('Wi-Fi unavailable')
    return False


def backend_state(cfg):
    path = '/api/attendance/sync-state?device_id=' + cfg['device_id']
    status, state = request_json('GET', cfg['backend_base_url'], path,
                    cfg['backend_api_key'], timeout=device_config.REQUEST_TIMEOUT_SECONDS)
    if status != 200 or not state.get('success') or 'cursor' not in state:
        raise ValueError('Backend state response invalid')
    return state['cursor']


def read_page(cfg, cursor):
    zk = ZKLib(cfg['device_ip'], cfg['device_port'], device_config.DEVICE_TIMEOUT_MS)
    zk.create_socket()
    try:
        zk.connect()
        return zk.attendance_page(cursor=cursor, limit=cfg['page_limit'])
    finally:
        try:
            zk.disconnect()
        except Exception:
            pass


def push_until_acked(cfg, page, cursor, led):
    """Keep the identical batch until exact committed_cursor is acknowledged."""
    next_cursor = page['next_cursor']
    batch = {'device_id': cfg['device_id'], 'cursor': cursor,
             'next_cursor': next_cursor, 'records': page['records']}
    while True:
        try:
            led.set('sync')
            status, response = request_json('POST', cfg['backend_base_url'],
                    '/api/attendance/batches', cfg['backend_api_key'],
                    batch, timeout=device_config.REQUEST_TIMEOUT_SECONDS)
            if status == 200 and response.get('success') is True and response.get('committed_cursor') == next_cursor:
                print('ACK:', page['count'], 'records')
                led.set('success')
                return next_cursor
            raise ValueError('ACK cursor mismatch: ' + str(response)[:100])
        except HTTPError as exc:
            if exc.status == 409:
                print('Backend cursor conflict; refreshing committed state')
                return None
            print('Backend POST failed:', exc)
        except Exception as exc:
            print('Backend POST/ACK failed:', exc)
        led.set('error')
        print('Retrying SAME attendance page')
        gc.collect()
        sleep_seconds(device_config.RETRY_SECONDS)
        # Do not fetch a new page until ACK. Wi-Fi may reconnect meanwhile.
        wlan = get_wlan()
        if wlan is not None and not wlan.isconnected():
            connect_wifi(cfg, led)


def run_sync(cfg, led):
    cursor = backend_state(cfg)
    print('Starting backend cursor:', 'null' if cursor is None else cursor[:20] + '...')
    while True:
        led.set('sync')
        page = read_page(cfg, cursor)
        if not page.get('success') or not isinstance(page.get('records'), list):
            raise ValueError('Invalid device attendance page')
        if page['count'] == 0:
            print('No new attendance')
            led.set('ready')
            return
        next_cursor = push_until_acked(cfg, page, cursor, led)
        if next_cursor is None:
            led.set('ready')
            return
        cursor = next_cursor
        print('Synced page:', page['count'], 'remaining:',
              page['total_records'] - int(cursor.split('.')[0]))
        gc.collect()
        if not page['has_more']:
            print('Caught up with ZKT machine')
            led.set('ready')
            return


def run():
    led = StatusLED(device_config.LED_PIN, device_config.LED_ACTIVE_HIGH)
    cfg = settings_store.load()
    if cfg is not None:
        try:
            cfg = settings_store.validate(cfg)
        except Exception as exc:
            raise RuntimeError('Invalid settings.json: %s' % exc)
    try:
        while True:
            if cfg is None:
                if get_wlan() is None:
                    raise RuntimeError('Laptop: create settings.json; setup AP requires ESP32 MicroPython')
                import wifi_portal
                cfg = wifi_portal.run(led, 'First-time configuration')
                continue
            if not connect_wifi(cfg, led):
                import wifi_portal
                cfg = wifi_portal.run(led, 'Saved Wi-Fi network unavailable; update settings')
                continue
            try:
                if get_wlan() is not None:
                    import web_config
                    web_config.start()
                run_sync(cfg, led)
                led.set('ready')
                sleep_seconds(device_config.POLL_SECONDS)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                led.set('error')
                print('Sync cycle failed:', exc)
                try:
                    import sys
                    if hasattr(sys, 'print_exception'):
                        sys.print_exception(exc)
                    else:
                        import traceback
                        traceback.print_exc()
                except AttributeError:
                    import traceback
                    traceback.print_exc()
                gc.collect()
                sleep_seconds(device_config.RETRY_SECONDS)
    finally:
        led.close()


if __name__ == '__main__':
    run()
