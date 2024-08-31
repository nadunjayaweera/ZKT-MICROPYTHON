from zk_udp import ZKUDP
from zk_tcp import ZKTCP
from zk_commands import ZKCommands
from zk_error import ZKError

class ZKLib:
    def __init__(self, ip, port=4370, timeout=10, inport=4000):
        self.ip = ip  # Store IP in the class for reference
        self.tcp = ZKTCP(ip, port, timeout)
        self.udp = ZKUDP(ip, port, timeout)
        self.connection_type = None

    def connect(self):
        try:
            print("Attempting to connect via TCP...")
            if self.tcp.connect():
                self.connection_type = 'tcp'
                print("Connected via TCP.")
            else:
                print("TCP connection failed, attempting to connect via UDP...")
                if self.udp.connect():
                    self.connection_type = 'udp'
                    print("Connected via UDP.")
                else:
                    raise ZKError('Connection failed', 'CMD_CONNECT', self.ip)
        except ZKError as e:
            print(f"Connection error: {e.toast()}")

    def disconnect(self):
        if self.connection_type == 'tcp':
            self.tcp.disconnect()
        elif self.connection_type == 'udp':
            self.udp.disconnect()

    def get_users(self):
        if self.connection_type == 'tcp':
            data = self.tcp.get_users()
            if data:
                users = self.tcp.parse_user_data(data['payload'])
                return users
        elif self.connection_type == 'udp':
            data = self.udp.send_command(ZKCommands.CMD_USER_WRQ)
            if data:
                users = self.udp.parse_user_data(data['payload'])
                return users
        else:
            print("No active connection to retrieve users.")
            return None

    def get_attendances(self):
        if self.connection_type == 'tcp':
            data = self.tcp.get_attendances()
            if data:
                records = self.tcp.parse_attendance_data(data['payload'])
                return records
        elif self.connection_type == 'udp':
            data = self.udp.send_command(ZKCommands.CMD_ATTLOG_RRQ)
            if data:
                records = self.udp.parse_attendance_data(data['payload'])
                return records
        else:
            print("No active connection to retrieve attendances.")
            return None

# Example usage
zk = ZKLib('192.168.1.235')
zk.connect()
users = zk.get_users()
print(users)
zk.disconnect()
