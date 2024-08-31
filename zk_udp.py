import socket
import struct
from time import sleep
from zk_commands import COMMANDS, REQUEST_DATA, MAX_CHUNK
from zk_util import create_udp_header, decode_user_data_28, decode_record_data_16, decode_record_real_time_log_18, decode_udp_header, check_not_event_udp

class JUDP:
    def __init__(self, ip, port, timeout=10, inport=0):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.inport = inport
        self.socket = None
        self.session_id = 0
        self.reply_id = 0

    def create_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('', self.inport))
            return True
        except OSError as e:
            print("Socket error:", e)
            return False

    def connect(self):
        try:
            reply = self.execute_cmd(COMMANDS['CMD_CONNECT'], b'')
            if reply:
                return True
            else:
                print("No reply on CMD_CONNECT")
                return False
        except Exception as e:
            print("Connection error:", e)
            return False

    def close_socket(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def write_message(self, msg):
        try:
            self.socket.sendto(msg, (self.ip, self.port))
            self.socket.settimeout(self.timeout)
            data, _ = self.socket.recvfrom(1024)
            return data
        except socket.timeout:
            print("Timeout on writing message.")
            return None

    def request_data(self, msg):
        try:
            self.socket.sendto(msg, (self.ip, self.port))
            self.socket.settimeout(self.timeout)
            data, _ = self.socket.recvfrom(1024)
            return data
        except socket.timeout:
            print("Timeout on receiving data.")
            return None

    def execute_cmd(self, command, data):
        if command == COMMANDS['CMD_CONNECT']:
            self.session_id = 0
            self.reply_id = 0
        else:
            self.reply_id += 1

        buf = create_udp_header(command, self.session_id, self.reply_id, data)
        reply = self.write_message(buf)

        if reply and len(reply) > 0:
            if command == COMMANDS['CMD_CONNECT']:
                self.session_id = struct.unpack('<H', reply[4:6])[0]
            return reply
        return None

    def send_chunk_request(self, start, size):
        self.reply_id += 1
        req_data = struct.pack('<II', start, size)
        buf = create_udp_header(COMMANDS['CMD_DATA_RDY'], self.session_id, self.reply_id, req_data)
        self.socket.sendto(buf, (self.ip, self.port))

    def read_with_buffer(self, req_data, cb=None):
        self.reply_id += 1
        buf = create_udp_header(COMMANDS['CMD_DATA_WRRQ'], self.session_id, self.reply_id, req_data)
        reply = self.request_data(buf)

        if reply:
            header = decode_udp_header(reply[:8])
            if header['command_id'] == COMMANDS['CMD_DATA']:
                return {'data': reply[8:], 'mode': 8}
            elif header['command_id'] in [COMMANDS['CMD_ACK_OK'], COMMANDS['CMD_PREPARE_DATA']]:
                size = struct.unpack('<I', reply[9:13])[0]
                total_buffer = b''

                for i in range(0, size, MAX_CHUNK):
                    self.send_chunk_request(i, min(MAX_CHUNK, size - i))
                    chunk_reply = self.request_data(buf)
                    total_buffer += chunk_reply[8:]

                return {'data': total_buffer, 'err': None}
        return None

    def get_users(self):
        self.free_data()
        data = self.read_with_buffer(REQUEST_DATA['GET_USERS'])
        self.free_data()

        users = []
        user_data = data['data'][4:]
        while len(user_data) >= 28:
            user = decode_user_data_28(user_data[:28])
            users.append(user)
            user_data = user_data[28:]

        return {'data': users}

    def get_attendances(self, cb=None):
        self.free_data()
        data = self.read_with_buffer(REQUEST_DATA['GET_ATTENDANCE_LOGS'], cb)
        self.free_data()

        records = []
        record_data = data['data'][4:]
        while len(record_data) >= 16:
            record = decode_record_data_16(record_data[:16])
            records.append(record)
            record_data = record_data[16:]

        return {'data': records}

    def free_data(self):
        self.execute_cmd(COMMANDS['CMD_FREE_DATA'], b'')

    def disable_device(self):
        self.execute_cmd(COMMANDS['CMD_DISABLEDEVICE'], REQUEST_DATA['DISABLE_DEVICE'])

    def enable_device(self):
        self.execute_cmd(COMMANDS['CMD_ENABLEDEVICE'], b'')

    def disconnect(self):
        self.execute_cmd(COMMANDS['CMD_EXIT'], b'')
        self.close_socket()

    def get_time(self):
        try:
            t = self.execute_cmd(COMMANDS['CMD_GET_TIME'], b'')
            return struct.unpack('<I', t[8:12])[0]
        except Exception as e:
            print("Error getting time:", e)
            return None

    def clear_attendance_log(self):
        return self.execute_cmd(COMMANDS['CMD_CLEAR_ATTLOG'], b'')

    def get_real_time_logs(self, cb=None):
        self.reply_id += 1
        buf = create_udp_header(COMMANDS['CMD_REG_EVENT'], self.session_id, self.reply_id, REQUEST_DATA['GET_REAL_TIME_EVENT'])
        self.socket.sendto(buf, (self.ip, self.port))

        while True:
            data, _ = self.socket.recvfrom(1024)
            if not check_not_event_udp(data):
                continue
            if len(data) == 18:
                cb(decode_record_real_time_log_18(data))

    def get_info(self):
        try:
            data = self.execute_cmd(COMMANDS['CMD_GET_FREE_SIZES'], b'')
            if data:
                return {
                    'userCounts': struct.unpack('<I', data[24:28])[0],
                    'logCounts': struct.unpack('<I', data[40:44])[0],
                    'logCapacity': struct.unpack('<I', data[72:76])[0]
                }
        except Exception as err:
            print(f"Error getting info: {err}")
            return None
