import socket
import struct
import time
from zk_util import create_tcp_header, parse_response, calculate_checksum
from zk_commands import ZKCommands

class ZKTCP:
    def __init__(self, ip, port, timeout=10):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.session_id = 0
        self.reply_id = 0
        self.socket = None

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip, self.port))
            
            # Send connection command
            packet = create_tcp_header(ZKCommands.CMD_CONNECT, self.session_id, self.reply_id)
            print(f"Sending packet: {packet.hex()}")
            self.socket.send(packet)
            
            # Wait for the response
            data = self.socket.recv(1024)
            print(f"Received data: {data.hex()}")
            response = parse_response(data)
            
            # Check if connection is successful
            if response and response['command'] == ZKCommands.CMD_ACK_OK:
                self.session_id = response['session_id']
                self.reply_id = response['reply_id']
                return True
        except socket.timeout:
            print("TCP connection timed out")
        except Exception as e:
            print(f"TCP connection failed: {e}")
        return False

    def send_command(self, command, data=b''):
        self.reply_id += 1
        packet = create_tcp_header(command, self.session_id, self.reply_id, data)
        print(f"Sending packet: {packet.hex()}")
        self.socket.send(packet)
        try:
            data = self.socket.recv(1024)
            print(f"Received data: {data.hex()}")
            return parse_response(data)
        except socket.timeout:
            print("Socket timed out")
            return None

    def send_chunk_request(self, start, size):
        self.reply_id += 1
        req_data = struct.pack('<II', start, size)
        packet = create_tcp_header(ZKCommands.CMD_DATA_RDY, self.session_id, self.reply_id, req_data)
        self.socket.send(packet)
        print(f"Sent chunk request: {packet.hex()}")

    def read_with_buffer(self, req_data, callback=None):
        self.reply_id += 1
        packet = create_tcp_header(ZKCommands.CMD_DATA_WRRQ, self.session_id, self.reply_id, req_data)
        self.socket.send(packet)
        
        total_buffer = b''
        real_total_buffer = b''
        try:
            while True:
                data = self.socket.recv(1024)
                total_buffer += data
                
                # Process data to extract records
                header = parse_response(total_buffer)
                if header and header['command'] == ZKCommands.CMD_DATA:
                    real_total_buffer += total_buffer[8:]
                    if callback:
                        callback(len(real_total_buffer))
                    break
        except socket.timeout:
            print("Socket timed out while reading buffer")

        return real_total_buffer

    def disconnect(self):
        packet = create_tcp_header(ZKCommands.CMD_EXIT, self.session_id, self.reply_id)
        self.socket.send(packet)
        self.socket.close()

    def get_users(self):
        # Send command to get users
        data = self.read_with_buffer(create_tcp_header(ZKCommands.CMD_USER_WRQ, self.session_id, self.reply_id))
        if data:
            return self.parse_user_data(data)
        return None

    def parse_user_data(self, data):
        # Assuming each user data block is 72 bytes
        USER_PACKET_SIZE = 72
        users = []
        while len(data) >= USER_PACKET_SIZE:
            user = struct.unpack('<HBB8s24sI9s', data[:USER_PACKET_SIZE])
            users.append(user)
            data = data[USER_PACKET_SIZE:]
        return users

    def get_attendances(self):
        # Send command to get attendance logs
        data = self.read_with_buffer(create_tcp_header(ZKCommands.CMD_ATTLOG_RRQ, self.session_id, self.reply_id))
        if data:
            return self.parse_attendance_data(data)
        return None

    def parse_attendance_data(self, data):
        # Assuming each attendance data block is 40 bytes
        RECORD_PACKET_SIZE = 40
        records = []
        while len(data) >= RECORD_PACKET_SIZE:
            record = struct.unpack('<H9sI', data[:RECORD_PACKET_SIZE])
            records.append(record)
            data = data[RECORD_PACKET_SIZE:]
        return records
