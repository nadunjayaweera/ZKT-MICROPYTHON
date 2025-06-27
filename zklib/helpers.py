# micropython_zklib/zklib/helpers.py
import struct
from .constants import USHRT_MAX

def parse_time(time):
    second = time % 60
    time = (time - second) // 60
    minute = time % 60
    time = (time - minute) // 60
    hour = time % 24
    time = (time - hour) // 24
    day = (time % 31) + 1
    time = (time - (day - 1)) // 31
    month = time % 12
    time = (time - month) // 12
    year = time + 2000
    return f"{year}-{month+1}-{day} {hour}:{minute}:{second}"


def create_chk_sum(buf):
    chksum = 0
    for i in range(0, len(buf), 2):
        if i == len(buf) - 1:
            chksum += buf[i]
        else:
            chksum += struct.unpack('<H', buf[i:i+2])[0]
        chksum %= USHRT_MAX
    chksum = USHRT_MAX - chksum - 1
    return chksum


def create_tcp_header(command, session_id, reply_id, data):
    buf = bytearray(8 + len(data))
    struct.pack_into('<H', buf, 0, command)
    struct.pack_into('<H', buf, 2, 0)
    struct.pack_into('<H', buf, 4, session_id)
    struct.pack_into('<H', buf, 6, reply_id)
    buf[8:] = data

    chksum = create_chk_sum(buf)
    struct.pack_into('<H', buf, 2, chksum)

    reply_id = (reply_id + 1) % USHRT_MAX
    struct.pack_into('<H', buf, 6, reply_id)

    prefix_buf = bytearray([0x50, 0x50, 0x82, 0x7d, 0x13, 0x00, 0x00, 0x00])
    struct.pack_into('<I', prefix_buf, 4, len(buf))

    return bytes(prefix_buf) + bytes(buf)


def remove_tcp_header(buf):
    if len(buf) < 8:
        return buf
    if buf[:4] != b'\x50\x50\x82\x7d':
        return buf
    return buf[8:]


def decode_record_data_40(record_data):
    user_sn = struct.unpack('<H', record_data[:2])[0]
    device_user_id = record_data[2:11].decode('ascii', errors='ignore').split('\0')[0]
    record_time = parse_time(struct.unpack('<I', record_data[27:31])[0])
    return {'user_sn': user_sn, 'device_user_id': device_user_id, 'record_time': record_time}


def decode_tcp_header(header):
    recv_data = header[8:]
    payload_size = struct.unpack('<H', header[4:6])[0]
    command_id, check_sum, session_id, reply_id = struct.unpack('<HHHH', recv_data[:8])
    return {'command_id': command_id, 'check_sum': check_sum, 'session_id': session_id, 'reply_id': reply_id, 'payload_size': payload_size}
