import socket 
from zk_util import create_udp_header, parse_response
from zk_commands import ZKCommands

class ZKUDP:
    def __init__(self, ip, port, timeout=10):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.session_id = 0
        self.reply_id = 0
        self.socket = None

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(self.timeout)
        packet = create_udp_header(ZKCommands.CMD_CONNECT, self.session_id, self.reply_id)
        print(f"Sending UDP packet: {packet.hex()} to {self.ip}:{self.port}")  # Debugging: Print packet details
        self.socket.sendto(packet, (self.ip, self.port))
        try:
            data, _ = self.socket.recvfrom(1024)
            print(f"Received UDP data: {data.hex()}")  # Debugging: Print received data
            response = parse_response(data)
            if response and response['command'] == ZKCommands.CMD_ACK_OK:
                self.session_id = response['session_id']
                self.reply_id = response['reply_id']
                return True
            else:
                print("Unexpected response or no response from the device.")  # Debugging
            return False
        except socket.timeout:
            print("UDP connection timed out")  # Debugging: Timeout information
            return False

    def send_command(self, command, data=b''):
        self.reply_id += 1
        packet = create_udp_header(command, self.session_id, self.reply_id, data)
        print(f"Sending packet: {packet.hex()}")  # Debugging: Print the packet being sent
        self.socket.send(packet)
        try:
            data = self.socket.recv(1024)
            print(f"Received data: {data.hex()}")  # Debugging: Print the received data
            return parse_response(data)
        except socket.timeout:
            print("Socket timed out")  # Debugging: Timeout information
            return None

    def disconnect(self):
        packet = create_udp_header(ZKCommands.CMD_EXIT, self.session_id, self.reply_id)
        self.socket.sendto(packet, (self.ip, self.port))
        self.socket.close()
