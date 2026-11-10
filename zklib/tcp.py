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
        # TCP is a byte stream: always consume the exact framed packet.
        self.socket.sendall(msg)
        command, payload, raw_header = self._read_packet_stream(with_header=True)
        return raw_header + payload

    def request_data(self, msg):
        return self.write_message(msg)

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

    def _read_packet_stream(self, with_header=False):
        # ZK TCP envelope: 4-byte signature, uint32 inner length,
        # and 8-byte command/checksum/session/reply header.
        prefix = self._recv_all(8)
        if prefix[:4] != b'\x50\x50\x82\x7d':
            raise ZKError("Invalid ZKT TCP packet prefix")
        length = struct.unpack('<I', prefix[4:8])[0]
        if length < 8 or length > 8192:
            raise ZKError("Unexpected ZKT TCP frame length %d" % length)
        header = self._recv_all(8)
        command = struct.unpack('<H', header[:2])[0]
        remaining = length - 8
        payload = self._recv_all(remaining) if remaining else b''
        if with_header:
            return command, payload, prefix + header
        return command, payload

    def _transfer_size(self, payload):
        # ZK6 buffered read uses a one-byte marker then LE uint32.
        if len(payload) >= 5:
            return struct.unpack('<I', payload[1:5])[0]
        if len(payload) == 4:
            return struct.unpack('<I', payload)[0]
        raise ZKError("Invalid PREPARE_DATA payload length %d" % len(payload))

    def _receive_chunk(self, expected, offset, command, payload):
        # 1504 (READ_BUFFER) can return DATA directly or a PREPARE_DATA
        # control frame followed by DATA and an ACK. A PREPARE frame with
        # 8-byte payload has the requested chunk length as its FIRST uint32.
        # Do not decode bytes [1:5] here: that offset applies only to the
        # initial 1503 (PREPARE_BUFFER) metadata and misreads 8-byte frames.
        if command in (CMD_DATA, CMD_ACK_DATA):
            if len(payload) != expected:
                raise ZKError("Chunk at %d has %d bytes, expected %d" %
                              (offset, len(payload), expected))
            return payload

        if command != CMD_PREPARE_DATA:
            raise ZKError("Unexpected chunk response %d at offset %d" %
                          (command, offset))

        if len(payload) == 8:
            announced, extra = struct.unpack('<II', payload)
            if offset == 0:
                print("First chunk PREPARE: announced=%d extra=%d" %
                      (announced, extra))
        elif len(payload) == 4:
            announced = struct.unpack('<I', payload)[0]
        elif len(payload) == 5:
            announced = struct.unpack('<I', payload[1:5])[0]
        else:
            raise ZKError("Unsupported chunk PREPARE payload length %d at offset %d" %
                          (len(payload), offset))

        if announced != expected:
            raise ZKError("Chunk at offset %d announced %d bytes; expected %d" %
                          (offset, announced, expected))

        parts = bytearray()
        while len(parts) < announced:
            next_cmd, block = self._read_packet_stream()
            if next_cmd not in (CMD_DATA, CMD_ACK_DATA):
                raise ZKError("Expected DATA at offset %d, got command %d" %
                              (offset, next_cmd))
            if len(parts) + len(block) > announced:
                raise ZKError("DATA at offset %d exceeded announced size" % offset)
            parts.extend(block)

        end_cmd, end_payload = self._read_packet_stream()
        if end_cmd != CMD_ACK_OK:
            raise ZKError("Expected ACK_OK after chunk at %d, got %d" %
                          (offset, end_cmd))
        return bytes(parts)

    def _iter_attendance_bytes(self, chunk_size=1024):
        if chunk_size < 40 or chunk_size > 4096:
            raise ValueError("chunk_size must be between 40 and 4096")

        self.reply_id += 1
        request = create_tcp_header(CMD_DATA_WRRQ, self.session_id,
                                    self.reply_id, GET_ATTENDANCE_LOGS)
        self.socket.sendall(request)
        command, payload = self._read_packet_stream()
        if command == CMD_DATA:
            # Direct response from the machine (smaller datasets).
            # Limit memory by rejecting larger single frames.
            yield payload
            return
        if command == CMD_ACK_ERROR:
            raise ZKError("Device rejected attendance buffer request")
        if command not in (CMD_ACK_OK, CMD_PREPARE_DATA):
            raise ZKError("Unexpected attendance response %d" % command)

        # Some machines first ACK then send a separate PREPARE frame.
        # An ACK containing the 5-byte buffered-read metadata is also valid.
        if command == CMD_ACK_OK and len(payload) < 5:
            command, payload = self._read_packet_stream()
            if command == CMD_DATA:
                yield payload
                return
            if command != CMD_PREPARE_DATA:
                raise ZKError("Expected PREPARE_DATA after ACK; got %d" % command)
        total = self._transfer_size(payload)
        if total == 0:
            return
        print("Attendance transfer size:", total, "bytes")
        offset = 0
        while offset < total:
            size = min(chunk_size, total - offset)
            print("Requesting chunk: offset=%d size=%d" % (offset, size))
            self.send_chunk_request(offset, size)
            for attempt in range(4):
                cmd, data = self._read_packet_stream()
                if cmd == CMD_ACK_OK and not data:
                    continue
                if cmd == CMD_ACK_ERROR:
                    raise ZKError("Device rejected read at offset %d" % offset)
                chunk = self._receive_chunk(size, offset, cmd, data)
                yield chunk
                offset += size
                print("Chunk received; next offset=%d / %d" % (offset, total))
                break
            else:
                raise ZKError("No chunk data at offset %d" % offset)

    def diagnose_attendance(self, chunk_size=2048):
        # Read only the first chunk; diagnose structure before writing JSON.
        try:
            import ubinascii as binascii
        except ImportError:
            import binascii
        self.free_data()
        stream = self._iter_attendance_bytes(chunk_size)
        try:
            chunk = next(stream)
            print("RAW FIRST CHUNK length:", len(chunk))
            print("RAW FIRST 120 BYTES (hex):",
                  binascii.hexlify(chunk[:120]))
            if len(chunk) < 44:
                raise ZKError("First chunk too small for length plus record")
            header_size = struct.unpack('<I', chunk[:4])[0]
            print("FIRST FOUR BYTES AS LENGTH:", header_size)
            print("LENGTH MOD 40:", header_size % 40)
            for ix in range(3):
                start = 4 + ix * 40
                raw = chunk[start:start + 40]
                if len(raw) != 40:
                    break
                print("SAMPLE", ix, "RAW:", binascii.hexlify(raw))
                print("SAMPLE", ix, "DECODED:", decode_record_data_40(raw))
                print("SAMPLE", ix, "TIME RAW:",
                      binascii.hexlify(raw[27:31]))
            print("Diagnostic only: no attendance JSON file written")
            return header_size
        finally:
            try:
                stream.close()
            except Exception:
                pass
            try:
                self.free_data()
            except Exception:
                pass

    def iter_attendances(self, chunk_size=2048):
        # ZKT response is 4-byte LE byte-count followed by 40-byte records.
        # Preserve incomplete records at boundaries; never decode chunk headers.
        pending = b''
        expected_records = None
        parsed_records = 0
        header_remaining = 4
        header_bytes = b''
        for chunk in self._iter_attendance_bytes(chunk_size):
            if header_remaining:
                take = min(header_remaining, len(chunk))
                header_bytes += chunk[:take]
                chunk = chunk[take:]
                header_remaining -= take
                if header_remaining == 0:
                    byte_count = struct.unpack('<I', header_bytes)[0]
                    if byte_count % 40 != 0:
                        raise ZKError("Attendance length %d is not divisible by 40" % byte_count)
                    expected_records = byte_count // 40
                    print("Expecting %d attendance records" % expected_records)
            pending += chunk
            position = 0
            while len(pending) - position >= 40:
                record = decode_record_data_40(pending[position:position + 40])
                if record['record_time'].startswith('2000-1-1 0:0:0'):
                    raise ZKError('Invalid zero timestamp; possible record misalignment')
                record['ip'] = self.ip
                parsed_records += 1
                if expected_records is not None and parsed_records > expected_records:
                    raise ZKError("Too many records; expected %d" % expected_records)
                yield record
                position += 40
            pending = pending[position:]
        if header_remaining or pending:
            raise ZKError("Incomplete attendance data at end of transfer")
        if parsed_records != expected_records:
            raise ZKError("Expected %d records; received %d" %
                          (expected_records, parsed_records))

    def save_attendances_json(self, filename="attendance.json", chunk_size=2048):
        try:
            import ujson as json
        except ImportError:
            import json
        count = 0
        # Temporary file ensures incomplete transfers don't replace valid data.
        temp_name = filename + ".tmp"
        self.free_data()
        try:
            with open(temp_name, "w") as output:
                output.write("[\n")
                for record in self.iter_attendances(chunk_size):
                    if count:
                        output.write(",\n")
                    output.write(json.dumps(record))
                    count += 1
                output.write("\n]\n")
            import os
            try:
                os.remove(filename)
            except OSError:
                pass
            os.rename(temp_name, filename)
            return count
        finally:
            try:
                self.free_data()
            except Exception:
                pass

    def get_attendances(self):
        # Compatibility API: this still accumulates all records in RAM.
        return list(self.iter_attendances())

    def free_data(self):
        return self.execute_cmd(CMD_FREE_DATA, b'')

    def disconnect(self):
        if self.socket:
            self.execute_cmd(CMD_EXIT, b'')
            self.socket.close()
            self.socket = None