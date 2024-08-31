import struct as struct
import time

USHRT_MAX = 65535

def calculate_checksum(data):
    chksum = 0
    for i in range(0, len(data), 2):
        if i == len(data) - 1:
            chksum += data[i]
        else:
            chksum += struct.unpack('<H', data[i:i+2])[0]
        chksum %= USHRT_MAX
    chksum = USHRT_MAX - chksum - 1
    return chksum

def create_udp_header(command, session_id, reply_id, data=b''):
    buf = struct.pack('<HHHH', command, 0, session_id, reply_id) + data
    checksum = calculate_checksum(buf)
    packet = struct.pack('<HHHH', command, checksum, session_id, reply_id) + data
    return packet

def parse_response(data):
    if len(data) < 8:
        return None
    command, checksum, session_id, reply_id = struct.unpack('<HHHH', data[:8])
    payload = data[8:]
    return {
        'command': command,
        'checksum': checksum,
        'session_id': session_id,
        'reply_id': reply_id,
        'payload': payload
    }
