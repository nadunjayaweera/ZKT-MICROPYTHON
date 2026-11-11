# micropython_zklib/zklib/__init__.py
from .tcp import ZKLibTCP
from .errors import ZKError

class ZKLib:
    def __init__(self, ip, port, timeout=4000):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.zklib_tcp = ZKLibTCP(self.ip, self.port, self.timeout)

    def create_socket(self):
        self.zklib_tcp.create_socket()

    def connect(self):
        return self.zklib_tcp.connect()

    def disconnect(self):
        return self.zklib_tcp.disconnect()

    def get_attendances(self):
        return self.zklib_tcp.get_attendances()

    def save_attendances_json(self, filename="attendance.json", chunk_size=2048):
        return self.zklib_tcp.save_attendances_json(filename, chunk_size)

    def diagnose_attendance(self, chunk_size=2048):
        return self.zklib_tcp.diagnose_attendance(chunk_size)

    def attendance_page(self, cursor=None, limit=10):
        return self.zklib_tcp.attendance_page(cursor, limit)
