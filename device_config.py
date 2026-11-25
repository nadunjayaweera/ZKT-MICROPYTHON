"""Non-secret hardware defaults. Credentials live in settings.json on device."""
LED_PIN = 2                 # Typical classic ESP32 onboard LED; board-dependent
LED_ACTIVE_HIGH = True      # Set False if LED is active-low
SETUP_AP_PREFIX = 'ZKT-Setup-'
SETUP_AP_IP = '192.168.4.1'
WIFI_CONNECT_SECONDS = 20
PAGE_LIMIT = 30
POLL_SECONDS = 60
RETRY_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 25
DEVICE_TIMEOUT_MS = 15000
