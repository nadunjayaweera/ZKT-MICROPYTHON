# ZKT ESP32 Attendance Sync

## Complete installation and user guide (Thonny + MicroPython)

This project reads attendance records from a ZKT biometric machine using an ESP32, then sends them to a Node.js backend. The ESP32 connects to Wi-Fi and initiates all communication. It does not require the backend to connect directly to the ESP32.

The project includes:

- A Wi-Fi setup page hosted by the ESP32 (WiFiManager-style setup).
- Persistent Wi-Fi, ZKT machine, and backend settings.
- Chunked attendance reading to avoid loading the full attendance log into ESP32 memory.
- Reliable page upload and retry. The ESP32 only advances after receiving the matching backend acknowledgement.
- LED status indications (subject to the board's LED hardware).
- A Node.js JSON-file backend example. No database is required for this example backend.

---

# 1. What you need

1. ESP32 development board.
2. USB data cable.
3. ZKT biometric attendance machine connected to the same reachable network as the ESP32.
4. Windows laptop/PC with [Thonny](https://thonny.org/) installed.
5. MicroPython firmware installed on the ESP32.
6. Node.js 18 or newer on the computer/server that will run the backend.
7. Wi-Fi network details and the ZKT machine's IP address.

**Network requirement:** the ESP32 must be able to reach both the ZKT machine (normally TCP port `4370`) and the backend URL. The PC and ESP32 should be on a network that allows devices to communicate with each other. Guest Wi-Fi or router client isolation can block this.

# 2. Project folder structure

After extracting the ZIP file, you should see a folder similar to this:

```text
ZKT-ESP32-WIFI-SETUP-LED-SYNC/
|
|-- main.py                 Main ESP32 application
|-- device_config.py        Hardware and timing defaults
|-- settings_store.py       Reads and saves settings.json
|-- wifi_portal.py          ESP32 Wi-Fi setup web page
|-- led_status.py           LED status patterns
|-- http_client.py          HTTP client used by the sync process
|-- settings.example.json   Example configuration for laptop mode
|-- test_sync.py            Test/helper file (not needed on ESP32)
|-- MICROPYTHON-FIX-NOTES.md
|
|-- zklib/
|   |-- __init__.py
|   |-- constants.py
|   |-- errors.py
|   |-- helpers.py
|   `-- tcp.py
|
`-- backend-json/
    |-- server.js
    |-- package.json
    |-- .env.example
    `-- README.md
```

Do not upload the `backend-json` folder to the ESP32. It runs separately on your PC or server.

# 3. Install MicroPython on the ESP32 (first-time setup only)

If MicroPython is already installed and Thonny can communicate with the ESP32, skip to section 4.

1. Connect the ESP32 to your PC using a USB data cable.
2. Open Thonny.
3. Select **Tools → Options → Interpreter**.
4. Select **MicroPython (ESP32)** as the interpreter.
5. Select the correct serial port (for example, `COM6` on Windows).
6. If Thonny reports that MicroPython is not installed, use the firmware installation option in the Interpreter settings.
7. Select the correct ESP32 firmware/device target and install the firmware.
8. After installation, click **OK**. The Thonny Shell should show the MicroPython prompt:

```text
>>>
```

If the board is not detected, try another USB cable, another USB port, or install the USB-to-serial driver required by your board.

# 4. Upload the ESP32 files using Thonny

This is the most important installation section.

## 4.1 Connect Thonny to the ESP32

1. Connect the ESP32 to the PC.
2. Open Thonny.
3. Go to **Tools → Options → Interpreter**.
4. Choose **MicroPython (ESP32)**.
5. Choose the ESP32 COM port.
6. Click **OK**.
7. Press the red **Stop** button or `Ctrl+C` once if a previous program is running.

## 4.2 Show the file browser

1. In Thonny, open **View → Files**.
2. The Files panel normally shows two locations:
   - **This computer** — files on your PC.
   - **MicroPython device** — files stored on the ESP32.
3. In the computer panel, browse to the extracted project folder:
   `ZKT-ESP32-WIFI-SETUP-LED-SYNC`.

## 4.3 Upload the Python files

Upload these files to the ESP32 root directory (`/`):

```text
main.py
device_config.py
settings_store.py
wifi_portal.py
led_status.py
http_client.py
```

For each file, right-click it in the **This computer** panel and select **Upload to /**. Depending on your Thonny version, you may also drag the file to the device panel.

## 4.4 Upload the zklib folder

The `zklib` folder is required. Upload the complete folder and preserve its name and structure.

The ESP32 should contain:

```text
/
|-- main.py
|-- device_config.py
|-- settings_store.py
|-- wifi_portal.py
|-- led_status.py
|-- http_client.py
`-- zklib/
    |-- __init__.py
    |-- constants.py
    |-- errors.py
    |-- helpers.py
    `-- tcp.py
```

To upload it, right-click the local `zklib` folder and choose **Upload to /** if your Thonny version supports folder upload. Otherwise, create a `zklib` folder on the device and upload each `.py` file into that folder.

**Important:** do not rename `zklib`, and do not put its Python files directly in the root directory.

## 4.5 Files you should not upload

These are not required on the ESP32:

- `backend-json/`
- `test_sync.py`
- `settings.example.json`
- `README.md`
- `MICROPYTHON-FIX-NOTES.md`

The backend folder runs on your computer/server, not on the ESP32.

## 4.6 Check the device files

In Thonny's MicroPython device panel, confirm that all six root Python files and the complete `zklib` folder are present.

If you are upgrading from an earlier version, stop the old program first. Replace the application files with the new ones. Keep your existing `settings.json` if you want to retain the saved configuration. Do not delete it unless you intentionally want to configure the device again.

# 5. Configure and start the Node.js backend

The backend receives attendance pages and stores them in a JSON Lines file. It is separate from the ESP32.

If you already have a compatible backend running, you can skip to section 6. Otherwise:

## 5.1 Install Node.js

Install Node.js version 18 or newer on the PC/server that will host the backend.

## 5.2 Configure the backend

1. Open the extracted project folder on your PC.
2. Open the `backend-json` folder.
3. Make a copy of `.env.example` and name the copy `.env`.
   - In Windows File Explorer, enable **View → Show → File name extensions** if needed.
   - Ensure the filename is exactly `.env`, not `.env.txt`.
4. Open `.env` and set a long secret value for `DEVICE_API_KEY`.

Example:

```env
PORT=3000
DEVICE_API_KEY=replace-this-with-a-long-random-secret
DATA_DIR=./data
```

Remember the API key. You must enter exactly the same key in the ESP32 setup page.

## 5.3 Start the backend

Open Command Prompt or PowerShell in the `backend-json` folder and run:

```bash
npm start
```

The backend should report that it is listening on port `3000`.

The server is configured to listen on `0.0.0.0`, so devices on the permitted local network can reach it. Allow inbound TCP port `3000` through Windows Firewall for a trusted Private network if required.

## 5.4 Find the PC's LAN IPv4 address

On Windows:

1. Open Command Prompt.
2. Run:

```bat
ipconfig
```

3. Find the **IPv4 Address** under the Wi-Fi adapter connected to the same network as the ESP32.

For example:

```text
192.168.1.38
```

Use that address in the ESP32 setup page:

```text
http://192.168.1.38:3000
```

Replace the example IP with your actual PC/server LAN IP.

**Do not use** `localhost`, `127.0.0.1`, or a `169.254.x.x` link-local adapter address as the backend address on the ESP32. Those addresses will generally not point to the PC from the ESP32.

## 5.5 Check the backend

On the PC, open:

```text
http://localhost:3000/health
```

You should receive a successful health response. You can also test from a phone or another device on the same Wi-Fi by opening:

```text
http://YOUR-PC-LAN-IP:3000/health
```

If the PC works locally but another device cannot open it, check Windows Firewall, confirm the Wi-Fi network is Private, and check that router AP/client isolation is disabled.

# 6. First boot: configure the ESP32 from your phone

After uploading the files:

1. In Thonny, press **Ctrl+D** to soft-reboot the ESP32. You can also press the board's reset button.
2. Keep the Thonny Shell open.
3. If no valid settings are saved, the ESP32 starts its setup access point.
4. The Thonny Shell prints the setup Wi-Fi name and password. Example:

```text
SETUP MODE - Connect phone to Wi-Fi: ZKT-Setup-A12B
SETUP PASSWORD: ********
Open browser: http://192.168.4.1/
```

The actual SSID and password will be generated by your device. Use the values printed in your Shell.

5. On your phone, open Wi-Fi settings and connect to the network beginning with `ZKT-Setup-`.
6. If your phone says **No internet**, choose to stay connected. Temporarily turn off mobile data if your phone switches away from the ESP32 network.
7. Open a browser and manually enter:

```text
http://192.168.4.1/
```

The setup page may not open automatically; entering the address manually is expected.

## 6.1 Fill in the setup form

| Field            | What to enter                                  | Example                    |
| ---------------- | ---------------------------------------------- | -------------------------- |
| Wi-Fi SSID       | Name of your normal Wi-Fi network              | `Office-WiFi`              |
| Wi-Fi password   | Password of that Wi-Fi network                 | Your Wi-Fi password        |
| ZKT machine IP   | LAN IP address of the biometric machine        | `192.168.1.236`            |
| ZKT port         | ZKT communication port (usually 4370)          | `4370`                     |
| Device ID        | Unique, stable ID for this attendance machine  | `zkt-001`                  |
| Backend URL      | PC/server address and backend port             | `http://192.168.1.38:3000` |
| Backend API key  | Exact `DEVICE_API_KEY` from backend `.env`     | Same secret                |
| Records per page | Number of records sent per batch, from 1 to 20 | `5`                        |

Use a unique Device ID for each physical ZKT machine. Keep the same Device ID after rebooting or changing Wi-Fi. Changing it makes the backend treat it as a different device with a separate sync cursor.

For the first test, use a small page size such as `5`. You can increase it later if the system is stable.

8. Tap **Save and connect**.
9. The ESP32 saves the settings to its flash storage and attempts to join your normal Wi-Fi.
10. Your phone can now reconnect to the normal Wi-Fi. Keep the ESP32 powered on.

# 7. Normal operation

After setup, the ESP32 runs automatically whenever it restarts:

1. Connects to the saved Wi-Fi.
2. Requests the last committed cursor for its Device ID from the backend.
3. Connects to the ZKT machine and reads the next attendance page.
4. Sends that page to the backend.
5. Waits for a successful response containing the exact expected committed cursor.
6. Advances to the next page only after the matching acknowledgement.
7. Repeats until it has caught up with the ZKT machine.
8. Waits for the next polling cycle and checks again for new records.

The default polling interval is 60 seconds. Retry delay and network timeouts are defined in `device_config.py`.

## Reliability behaviour

- If an upload fails or its response is lost, the ESP32 retries the same page.
- It does not move to the next page until the backend confirms the expected cursor.
- The backend stores the records and cursor before returning the successful acknowledgement.
- Replaying a previously committed page is handled by the backend without inserting duplicate records.
- If the backend reports a cursor conflict, the ESP32 refreshes its state on the next cycle.

The ZKT attendance log should remain in its original append-only order. If device logs are manually cleared, reordered, or deleted, the saved cursor may no longer represent the same log position. Do not clear the machine's logs during a sync without planning a resynchronization.

# 8. LED status indications

The default LED configuration is in `device_config.py`:

```python
LED_PIN = 2
LED_ACTIVE_HIGH = True
```

| LED pattern  | Meaning                                |
| ------------ | -------------------------------------- |
| Slow blink   | ESP32 setup hotspot is active          |
| Fast blink   | Connecting to saved Wi-Fi              |
| Solid on     | Wi-Fi connected / idle                 |
| Double pulse | Reading attendance or uploading a page |
| Short flash  | A page was acknowledged by the backend |
| Triple pulse | Sync or network error; retrying        |

**Hardware note:** GPIO2 is common on some classic ESP32 boards, but it is not universal. Some ESP32-S3 boards use an addressable RGB (WS2812/NeoPixel) LED instead of a simple GPIO LED. This project's default GPIO LED driver will not necessarily control that RGB LED. If your board has no controllable GPIO2 LED, use a suitable external LED and current-limiting resistor, or adapt the LED driver for your board. Never connect an LED directly to a GPIO without a resistor.

If the LED is wired active-low, change `LED_ACTIVE_HIGH` to `False`. If you change `device_config.py`, upload the updated file to the ESP32 and reboot.

# 9. Change Wi-Fi or backend settings later

If the saved Wi-Fi network is unavailable, the ESP32 waits for the configured connection timeout and then opens the setup hotspot again. Connect to it and update the form.

To force setup mode manually:

1. Stop the program in Thonny using `Ctrl+C`.
2. Open **View → Files**.
3. In the MicroPython device panel, delete `settings.json`.
4. Press **Ctrl+D** or reset the ESP32.
5. Connect to the new `ZKT-Setup-XXXX` network and configure it again.

Keep `setup_ap_password.txt` if you want the setup hotspot password to remain stable. Do not delete it unless you intend to rotate that password.

# 10. Where the attendance data is stored

With the included JSON backend, attendance data is stored in:

```text
backend-json/data/attendance.jsonl
```

This file is created automatically when the backend receives records. It contains one committed page per line, including the page's records and cursor information.

Important:

- Back up `attendance.jsonl` regularly.
- Do not manually edit, truncate, or delete it while synchronization is running.
- If you deploy the backend in Docker or another hosted environment, persist the `data` directory using a persistent volume.
- Run only one backend process against the same JSON data file.
- Protect the backend with HTTPS when used outside a trusted local test network.

# 11. Useful backend API endpoints

All attendance endpoints require the matching Bearer API key.

| Method | Endpoint                                                      | Purpose                               |
| ------ | ------------------------------------------------------------- | ------------------------------------- |
| GET    | `/health`                                                     | Check backend health                  |
| GET    | `/api/attendance/sync-state?device_id=zkt-001`                | Read the saved cursor for a device    |
| POST   | `/api/attendance/batches`                                     | Receive and commit an attendance page |
| GET    | `/api/attendance/records?device_id=zkt-001&offset=0&limit=20` | View stored records                   |

Replace `zkt-001` with the Device ID configured on the ESP32.

# 12. Troubleshooting

## ESP32 does not appear in Thonny

- Check the USB cable; some cables are charge-only.
- Try another USB port.
- Select the correct COM port under **Tools → Options → Interpreter**.
- Install the USB-to-serial driver required by your board.
- Press the ESP32 BOOT button while connecting or installing firmware if your board requires it.

## Setup Wi-Fi does not appear

- Keep Thonny Shell open and press `Ctrl+D`.
- Look for `SETUP MODE` and the generated SSID/password in the Shell.
- Check that the device has the new `main.py`, `wifi_portal.py`, and `settings_store.py`.
- If the ESP32 already has valid settings, it will try the saved Wi-Fi first. Delete `settings.json` to force first-time setup.

## Phone connects to setup Wi-Fi but page does not open

- Enter `http://192.168.4.1/` manually.
- Do not use `https://`.
- Choose to stay connected even if the phone reports no internet.
- Temporarily disable mobile data or automatic Wi-Fi switching.

## ESP32 cannot connect to normal Wi-Fi

- Check the SSID and password (case-sensitive).
- Ensure the Wi-Fi network is 2.4 GHz; many ESP32 boards do not support 5 GHz Wi-Fi.
- Move the ESP32 closer to the access point.
- Re-enter the settings through the setup hotspot.

## Backend works on the PC but ESP32 cannot reach it

- Use the PC's Wi-Fi/LAN IPv4 address, not `localhost` or `127.0.0.1`.
- Confirm the backend listens on `0.0.0.0` and port `3000`.
- Allow inbound TCP port `3000` in Windows Firewall on a trusted Private network.
- Make sure the PC and ESP32 are on the same reachable network.
- Disable guest-network/client/AP isolation if enabled on the router.
- Do not use a `169.254.x.x` link-local adapter IP.

## ESP32 cannot reach the ZKT machine

- Confirm the ZKT machine's IP address has not changed.
- Confirm the ZKT machine and ESP32 are on reachable network segments.
- Check that TCP port `4370` is enabled and accessible.
- Check router/VLAN/firewall rules and device network settings.
- Try pinging the machine from a PC on the same network (not all ZKT devices respond to ping).

## Backend returns unauthorized / API key error

- Confirm `DEVICE_API_KEY` is set in the backend `.env`.
- Confirm the ESP32 setup page has exactly the same key.
- Restart the Node.js backend after changing `.env`.

## LED does not light

- GPIO2 may not control an LED on your board.
- Check the board pinout and onboard LED type.
- Some ESP32-S3 boards use a WS2812 RGB LED and need a NeoPixel driver.
- Check `LED_PIN` and `LED_ACTIVE_HIGH` in `device_config.py`.
- Test with an external LED and resistor if needed.

## Thonny shows a Python exception

- Keep the Thonny Shell open and copy the full traceback, including the file name and line number.
- Check that all required files are uploaded and `zklib` has the correct folder structure.
- Confirm you are running MicroPython firmware, not CircuitPython.
- Upload the latest versions of the project files, then reboot.

# 13. Laptop / PC test mode (optional)

The same sync application can also run in normal desktop Python mode, but the Wi-Fi setup portal is only for ESP32 MicroPython.

1. Install Python 3 on the PC.
2. Copy `settings.example.json` to `settings.json`.
3. Edit `settings.json` with the Wi-Fi/LAN details, ZKT IP, backend URL, Device ID, API key, and page limit.
4. Install any Python packages required by your desktop environment if prompted.
5. Run from the project directory:

```bash
python main.py
```

Use the PC's reachable backend URL and ensure the PC can reach the ZKT machine.

# 14. Security and deployment notes

- The setup access point is password-protected. Its generated password is printed in Thonny Shell and saved in `/setup_ap_password.txt`. Treat it as a credential.
- Wi-Fi and API credentials are stored as plain text in `/settings.json` on ESP32 flash. Anyone with physical access and suitable tools may be able to retrieve them.
- The setup form uses plain HTTP on the temporary ESP32 access point. It is intended for local provisioning, not public networks.
- Use HTTPS for attendance data outside a trusted local test network. Confirm TLS certificate verification behaviour on your MicroPython firmware before production use.
- Use a long, unique backend API key. Do not publish it in source control, screenshots, or support messages.
- Restrict access to the backend and back up the attendance data.
- This sample backend is a simple single-process JSON-file receiver. For high-volume or multi-server production deployments, use a properly managed database and deployment architecture.

---

## Quick installation checklist

- [ ] MicroPython installed and Thonny connected to the ESP32.
- [ ] Six root `.py` files uploaded to `/`.
- [ ] Complete `zklib/` folder uploaded to `/zklib/`.
- [ ] Node.js backend configured and running (or another compatible backend is available).
- [ ] PC/server LAN IP used in the backend URL.
- [ ] ESP32 setup hotspot opened and configured.
- [ ] Wi-Fi, ZKT IP/port, Device ID, backend URL, and API key saved.
- [ ] ESP32 connected to normal Wi-Fi.
- [ ] Attendance page received and acknowledged by backend.
- [ ] `attendance.jsonl` is being created and backed up.

**End of guide.**
