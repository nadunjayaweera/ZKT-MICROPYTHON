import socket
import struct
from time import sleep
from zk_commands import COMMANDS, REQUEST_DATA, MAX_CHUNK
from zk_util import create_tcp_header, remove_tcp_header, decode_user_data_72, decode_record_data_40, decode_record_real_time_log_52, decode_tcp_header, check_not_event_tcp

class JTCP:
    def __init__(self, ip, port, timeout=10):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.session_id = 0
        self.reply_id = 0
        self.socket = None

    def create_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip, self.port))
            return True
        except socket.error as e:
            print("Socket error:", e)
            return False

    def connect(self):
        try:
            reply = self.execute_cmd(COMMANDS['CMD_CONNECT'], b'')
            if reply:
                return True
            else:
                raise Exception('NO_REPLY_ON_CMD_CONNECT')
        except Exception as e:
            print("Connection error:", e)
            return False

    def close_socket(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def write_message(self, msg, connect=False):
        try:
            self.socket.send(msg)
            data = self.socket.recv(1024)
            return data
        except socket.timeout:
            print("Timeout on writing message.")
            return None

    def request_data(self, msg):
        try:
            self.socket.send(msg)
            data = self.socket.recv(1024)
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

        buf = create_tcp_header(command, self.session_id, self.reply_id, data)
        reply = self.write_message(buf, command == COMMANDS['CMD_CONNECT'] or command == COMMANDS['CMD_EXIT'])

        if reply:
            r_reply = remove_tcp_header(reply)
            if r_reply and len(r_reply) > 0:
                if command == COMMANDS['CMD_CONNECT']:
                    self.session_id = struct.unpack('<H', r_reply[4:6])[0]
                return r_reply
        return None

    def send_chunk_request(self, start, size):
        self.reply_id += 1
        req_data = struct.pack('<II', start, size)
        buf = create_tcp_header(COMMANDS['CMD_DATA_RDY'], self.session_id, self.reply_id, req_data)
        self.socket.send(buf)

    def read_with_buffer(self, req_data, cb=None):
        self.reply_id += 1
        buf = create_tcp_header(COMMANDS['CMD_DATA_WRRQ'], self.session_id, self.reply_id, req_data)
        reply = self.request_data(buf)

        if reply:
            header = decode_tcp_header(reply[:16])
            if header['command_id'] == COMMANDS['CMD_DATA']:
                return {'data': reply[16:], 'mode': 8}
            elif header['command_id'] in [COMMANDS['CMD_ACK_OK'], COMMANDS['CMD_PREPARE_DATA']]:
                size = struct.unpack('<I', reply[17:21])[0]

                total_packets = (size + MAX_CHUNK - 1) // MAX_CHUNK
                reply_data = b''

                for i in range(total_packets):
                    start = i * MAX_CHUNK
                    chunk_size = min(MAX_CHUNK, size - start)
                    self.send_chunk_request(start, chunk_size)
                    chunk_reply = self.request_data(buf)
                    reply_data += chunk_reply[16:]

                return {'data': reply_data, 'err': None}
        return None

    def get_users(self):
        self.free_data()
        data = self.read_with_buffer(REQUEST_DATA['GET_USERS'])
        self.free_data()

        users = []
        user_data = data['data'][4:]  # Skip the first 4 bytes of the data

        while len(user_data) >= 72:
            try:
                # Ensure we have exactly 72 bytes for each user record
                user = decode_user_data_72(user_data[:72])
                users.append(user)
            except Exception as e:
                print(f"Error decoding user data: {e}")
            finally:
                # Move to the next user record in the data
                user_data = user_data[72:]

        return {'data': users}


    def get_attendances(self, cb=None):
        self.free_data()
        data = self.read_with_buffer(REQUEST_DATA['GET_ATTENDANCE_LOGS'], cb)
        self.free_data()

        records = []
        record_data = data['data'][4:]
        while len(record_data) >= 40:
            record = decode_record_data_40(record_data[:40])
            records.append(record)
            record_data = record_data[40:]

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

    def get_info(self):
        data = self.execute_cmd(COMMANDS['CMD_GET_FREE_SIZES'], b'')
        return {
            'userCounts': struct.unpack('<I', data[24:28])[0],
            'logCounts': struct.unpack('<I', data[40:44])[0],
            'logCapacity': struct.unpack('<I', data[72:76])[0]
        }

    # Additional methods like getSerialNumber, getDeviceVersion, etc., follow a similar pattern
