# Update ESP32 configuration over Wi-Fi (no Thonny after first upload)

## New feature
While the ESP32 is connected to your normal Wi-Fi, open `http://ESP32-IP:8080` from a phone or computer on the same reachable LAN. Sign in with the **LAN WEB ADMIN PASSWORD** printed in the Thonny Shell on the first boot. The password is also saved on the ESP32 in `web_admin_password.txt`. The portal lets you edit Wi-Fi SSID/password, ZKT IP/port, device ID, backend URL/API key, and page limit. Leave password fields empty to keep the existing value. After Save, the ESP32 reboots and uses the new settings.

## Files to upload to ESP32 with Thonny (one-time upgrade)
**New:** `web_config.py`
**Updated:** `main.py`
Upload both to `/` on the ESP32. Keep your existing `settings.json`, `settings_store.py`, `wifi_portal.py`, `device_config.py`, `led_status.py`, `http_client.py`, and `zklib/` files. You do **not** need to upload `backend-json/`, `README.md`, or desktop scripts. The Node.js backend needs no changes.

If installing on a fresh ESP32, upload all six standard root `.py` files plus `web_config.py` and the entire `zklib/` folder.

## Step-by-step
1. Connect ESP32 to Thonny **once** to upload the two files above.
2. Restart with Ctrl+D and wait for the Wi-Fi IP address in the Shell.
3. Find the line `LAN WEB ADMIN PASSWORD: ...` and **save that password privately**.
4. From your phone connected to the same LAN, visit `http://ESP32-IP:8080`, for example `http://192.168.1.63:8080`.
5. Sign in, edit configuration, click **Save & restart ESP32**.
6. If you changed Wi-Fi, reconnect your phone to the new network and use the ESP32's new DHCP IP address. For convenience, configure a DHCP reservation on your router so its IP remains stable.

## Security
This is an HTTP admin interface on the trusted local network, not HTTPS. **Never port-forward port 8080 or expose it to the public internet.** Anyone who obtains the admin password and can access your LAN can change the ESP32 configuration. Use a trusted private Wi-Fi, isolate the device from untrusted guests, and change the generated password by replacing `web_admin_password.txt` through Thonny if compromised. The portal uses a password login, session cookie, basic lockout, and does not display saved Wi-Fi/API secrets. It is intended for local administration, not hostile networks.

If the saved Wi-Fi becomes unreachable after an update, the existing `wifi_portal.py` setup AP is still used; connect to `ZKT-Setup-XXXX` and visit `http://192.168.4.1/`. You do not need Thonny for that recovery, provided you know the setup AP password.

## Important hardware note
The web server runs in a MicroPython `_thread` while attendance sync continues. This requires an ESP32 MicroPython build with `_thread` support and enough free memory. Test the portal during a full sync cycle on your actual board. It has been syntax-checked but not hardware-tested here.
