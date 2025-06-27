# micropython_zklib/main.py
from zklib import ZKLib
try:
    import ujson as json
except ImportError:
    import json

def test():
    zk = ZKLib("192.168.1.230", 4370)
    try:
        zk.create_socket()
        zk.connect()
        attendances = zk.get_attendances()
        with open("attendance.json", "w") as f:
            f.write(json.dumps(attendances, indent=4))
        print("Attendance data saved to attendance.json")
        zk.disconnect()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()