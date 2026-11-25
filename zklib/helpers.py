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
    # MicroPython's str/bytes.decode may reject keyword arguments.
    # ZKT user IDs are typically zero-padded ASCII text. Filter non-ASCII
    # bytes without allocating a large intermediate string.
    raw_user_id = record_data[2:11].split(b'\x00', 1)[0]
    device_user_id = ''.join(chr(ch) for ch in raw_user_id if 32 <= ch <= 126)
    record_time = parse_time(struct.unpack('<I', record_data[27:31])[0])
    return {'user_sn': user_sn, 'device_user_id': device_user_id, 'record_time': record_time}


def decode_tcp_header(header):
    recv_data = header[8:]
    payload_size = struct.unpack('<H', header[4:6])[0]
    command_id, check_sum, session_id, reply_id = struct.unpack('<HHHH', recv_data[:8])
    return {'command_id': command_id, 'check_sum': check_sum, 'session_id': session_id, 'reply_id': reply_id, 'payload_size': payload_size}


def validate_attendance_record(record):
    """Conservative validation: never pretend to repair unknown raw bytes."""
    uid = record.get('device_user_id', '')
    if not uid or not uid.strip():
        return 'EMPTY_DEVICE_USER_ID'
    try:
        parts = record.get('record_time', '').replace(' ', '-').replace(':', '-').split('-')
        if len(parts) != 6:
            return 'INVALID_TIMESTAMP_FORMAT'
        year, month, day, hour, minute, second = [int(p) for p in parts]
        if year < 2000 or year > 2035:
            return 'IMPLAUSIBLE_TIMESTAMP_YEAR'
        if not 1 <= month <= 12 or not 0 <= hour <= 23 or not 0 <= minute <= 59 or not 0 <= second <= 59:
            return 'INVALID_TIMESTAMP_COMPONENT'
        if month == 2:
            leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
            days = 29 if leap else 28
        elif month in (4, 6, 9, 11):
            days = 30
        else:
            days = 31
        if day < 1 or day > days:
            return 'INVALID_CALENDAR_DATE'
    except (ValueError, TypeError, AttributeError):
        return 'INVALID_TIMESTAMP_FORMAT'
    return None
