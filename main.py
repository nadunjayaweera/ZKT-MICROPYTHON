from zklib import ZKLib

# Update to your ZKT machine address.
DEVICE_IP = "192.168.1.236"

def main():
    zk = ZKLib(DEVICE_IP, 4370, timeout=30000)
    try:
        zk.create_socket()
        zk.connect()
        # Read small chunks; write complete attendance records as JSON.
        # The device records are never cleared by this export.
        count = zk.save_attendances_json("attendance.json", chunk_size=2048)
        print("Export completed: %d records" % count)
    except OSError as e:
        print("Storage or network error:", e)
        print("ESP8266 may not have enough flash space for 57,856 JSON records.")
    except Exception as e:
        print("Error:", e)
    finally:
        try:
            zk.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    main()
