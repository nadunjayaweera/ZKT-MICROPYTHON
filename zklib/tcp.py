# micropython_zklib/zklib/tcp.py
import socket
import struct
import time
from .constants import *
from .helpers import *
from .errors import *

class ZKLibTCP:
    def __init__(self, ip, port, timeout):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.session_id = None
        self.reply_id = 0
        self.socket = None

    def _recv_all(self, size):
        data = b''
        while len(data) < size:
            packet = self.socket.recv(size - len(data))
            if not packet:
                raise ZKDisconnectedError("Socket connection broken")
            data += packet
        return data

    def create_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout / 1000) # Convert ms to seconds
            self.socket.connect((self.ip, self.port))
        except socket.error as e:
            raise ZKConnectionError(f"Connection failed: {e}")

    def connect(self):
        try:
            reply = self.execute_cmd(CMD_CONNECT, b'')
            if reply:
                return True
            else:
                raise ZKConnectionError("No reply on CMD_CONNECT")
        except Exception as e:
            raise ZKConnectionError(f"Connection failed: {e}")

    def write_message(self, msg, connect=False):
        try:
            self.socket.sendall(msg)
            # Receive the full ZKLib packet
            buffer = b''
            start_time = time.time()
            while True:
                chunk = self.socket.recv(1024)
                if not chunk:
                    raise ZKDisconnectedError("Socket connection broken during write_message")
                buffer += chunk

                if len(buffer) >= 8:
                    inner_buffer_length = struct.unpack('<H', buffer[4:6])[0]
                    total_packet_length = 8 + inner_buffer_length
                    if len(buffer) >= total_packet_length:
                        return buffer[:total_packet_length] # Return the first complete packet
                
                if time.time() - start_time > self.timeout / 1000:
                    raise ZKTimeoutError("Timeout on writing message")

        except socket.timeout:
            raise ZKTimeoutError("Timeout on writing message")
        except socket.error as e:
            raise ZKConnectionError(f"Error writing message: {e}")

    def request_data(self, msg):
        try:
            self.socket.sendall(msg)
            
            buffer = b''
            start_time = time.time()
            
            while True:
                chunk = self.socket.recv(1024)
                if not chunk:
                    raise ZKDisconnectedError("Socket connection broken during request_data")
                
                buffer += chunk
                
                if len(buffer) >= 8:
                    inner_buffer_length = struct.unpack('<H', buffer[4:6])[0]
                    total_packet_length = 8 + inner_buffer_length
                    
                    if len(buffer) >= total_packet_length:
                        return buffer[:total_packet_length] # Return the first complete packet
                
                if time.time() - start_time > self.timeout / 1000:
                    raise ZKTimeoutError("Timeout on receiving response after requesting data")
                    
        except socket.timeout:
            raise ZKTimeoutError("Timeout on receiving response after requesting data")
        except socket.error as e:
            raise ZKConnectionError(f"Error during request_data: {e}")

    def execute_cmd(self, command, data):
        if command == CMD_CONNECT:
            self.session_id = 0
            self.reply_id = 0
        else:
            self.reply_id += 1

        buf = create_tcp_header(command, self.session_id, self.reply_id, data)
        reply = self.write_message(buf, command in [CMD_CONNECT, CMD_EXIT])
        
        r_reply = remove_tcp_header(reply)
        if r_reply and len(r_reply) >= 0:
            if command == CMD_CONNECT:
                self.session_id = struct.unpack('<H', r_reply[4:6])[0]
        return r_reply

    def send_chunk_request(self, start, size):
        self.reply_id += 1
        req_data = bytearray(8)
        struct.pack_into('<II', req_data, 0, start, size)
        buf = create_tcp_header(CMD_DATA_RDY, self.session_id, self.reply_id, req_data)
        self.socket.sendall(buf)

    def read_with_buffer(self, req_data):
        self.reply_id += 1
        buf = create_tcp_header(CMD_DATA_WRRQ, self.session_id, self.reply_id, req_data)
        
        initial_reply = self.request_data(buf) # This should return the first complete packet
        
        header = decode_tcp_header(initial_reply[:16])
        
        if header['command_id'] == CMD_DATA:
            return initial_reply[16:] # Return payload if it's a single CMD_DATA response
        elif header['command_id'] in [CMD_ACK_OK, CMD_PREPARE_DATA]:
            recv_data = initial_reply[16:] # Payload of the initial reply
            size = struct.unpack('<I', recv_data[1:5])[0] # Total size of data to receive
            
            remain = size % MAX_CHUNK
            number_chunks = (size - remain) // MAX_CHUNK
            
            # 1. Send all chunk requests
            for i in range(number_chunks + 1):
                if i == number_chunks:
                    self.send_chunk_request(i * MAX_CHUNK, remain)
                else:
                    self.send_chunk_request(i * MAX_CHUNK, MAX_CHUNK)
            
            # 2. Receive all expected data into a buffer and extract packets
            accumulated_inner_buffers = b'' # This will store the inner_buffer of each ZKLib packet
            receive_buffer = b''
            start_time = time.time()
            
            # The total size we expect to receive is 'size' (from initial_reply)
            # We need to keep receiving until accumulated_inner_buffers reaches 'size'
            # plus the 8 bytes for each chunk header that will be stripped later.
            expected_raw_payload_size = size + ((number_chunks + 1) * 8) # Total size of inner_buffers including chunk headers

            while len(accumulated_inner_buffers) < expected_raw_payload_size:
                try:
                    chunk = self.socket.recv(1024) # Read whatever is available
                    if not chunk:
                        raise ZKDisconnectedError("Socket connection broken during data reception")
                    
                    receive_buffer += chunk
                    
                    # Try to extract complete ZKLib packets from the buffer
                    while len(receive_buffer) >= 8:
                        inner_buffer_length = struct.unpack('<H', receive_buffer[4:6])[0]
                        total_packet_length = 8 + inner_buffer_length
                        
                        if len(receive_buffer) >= total_packet_length:
                            # We have a complete packet
                            packet = receive_buffer[:total_packet_length]
                            receive_buffer = receive_buffer[total_packet_length:] # Remove processed packet
                            
                            # Extract the inner_buffer (payload after 16-byte ZKLib header)
                            if len(packet) >= 16: # Ensure packet is at least 16 bytes for ZKLib header
                                inner_buffer = packet[16:]
                                accumulated_inner_buffers += inner_buffer
                            else:
                                print("Warning: ZKLib packet too short for inner_buffer extraction.")
                                # This packet is malformed, skip it and try to read more
                                break # Break from inner while loop to receive more data
                        else:
                            # Not enough data for a complete packet yet, break and read more
                            break
                            
                except socket.timeout:
                    raise ZKTimeoutError("Timeout on receiving data chunks")
                except Exception as e:
                    raise ZKConnectionError(f"Error during receiving data chunks: {e}")
                
                if time.time() - start_time > self.timeout / 1000:
                    raise ZKTimeoutError("Timeout on receiving all data chunks")
            
            # After receiving all inner_buffers, strip the 8-byte chunk headers
            final_payload = b''
            current_offset = 0
            
            # Iterate through the accumulated_inner_buffers, extracting the actual data
            # and skipping the 8-byte chunk header for each logical chunk.
            for i in range(number_chunks + 1):
                chunk_payload_size = MAX_CHUNK
                if i == number_chunks: # Last chunk
                    chunk_payload_size = remain
                
                # Each inner_buffer chunk is (8 bytes header + actual_data_size)
                # So, we need to skip 8 bytes and take chunk_payload_size bytes
                
                start_index = current_offset + 8
                end_index = start_index + chunk_payload_size
                
                if end_index <= len(accumulated_inner_buffers):
                    final_payload += accumulated_inner_buffers[start_index:end_index]
                    current_offset = end_index
                else:
                    print(f"Warning: Incomplete chunk data during final payload assembly for chunk {i}.")
                    break # Exit loop if we can't extract a full chunk

            return final_payload
        else:
            raise ZKError(f"Unhandled command: {header['command_id']}")

    def get_attendances(self):
        if self.socket:
            self.free_data()

        try:
            data = self.read_with_buffer(GET_ATTENDANCE_LOGS)
        except Exception as e:
            raise ZKError(f"Error getting attendances: {e}")

        if self.socket:
            self.free_data()

        record_packet_size = 40
        record_data = data[4:]
        records = []
        while len(record_data) >= record_packet_size:
            record = decode_record_data_40(record_data[:record_packet_size])
            records.append({**record, 'ip': self.ip})
            record_data = record_data[record_packet_size:]
        
        return records

    def free_data(self):
        return self.execute_cmd(CMD_FREE_DATA, b'')

    def disconnect(self):
        if self.socket:
            self.execute_cmd(CMD_EXIT, b'')
            self.socket.close()
            self.socket = None