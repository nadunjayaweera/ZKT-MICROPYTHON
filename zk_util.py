import struct
from zk_commands import COMMANDS, USHRT_MAX
from log import log

def parse_time_to_date(time):
    second = time % 60
    time = (time - second) // 60
    minute = time % 60
    time = (time - minute) // 60
    hour = time % 24
    time = (time - hour) // 24
    day = time % 31 + 1
    time = (time - (day - 1)) // 31
    month = time % 12
    time = (time - month) // 12
    year = time + 2000
    
    return (year, month + 1, day, hour, minute, second)

def parse_hex_to_time(hex_data):
    time = {
        'year': hex_data[0],
        'month': hex_data[1],
        'date': hex_data[2],
        'hour': hex_data[3],
        'minute': hex_data[4],
        'second': hex_data[5]
    }
    
    return (2000 + time['year'], time['month'] - 1, time['date'], time['hour'], time['minute'], time['second'])

def create_checksum(buf):
    chksum = 0
    for i in range(0, len(buf), 2):
        if i == len(buf) - 1:
            chksum += buf[i]
        else:
            chksum += struct.unpack('<H', buf[i:i+2])[0]
        chksum %= USHRT_MAX
    chksum = USHRT_MAX - chksum - 1
  
    return chksum

def create_udp_header(command, session_id, reply_id, data=b''):
    data_buffer = data
    buf = bytearray(8 + len(data_buffer))
    
    struct.pack_into('<H', buf, 0, command)
    struct.pack_into('<H', buf, 2, 0)  # Placeholder for checksum
    struct.pack_into('<H', buf, 4, session_id)
    struct.pack_into('<H', buf, 6, reply_id)
    
    buf[8:] = data_buffer
    
    checksum = create_checksum(buf)
    struct.pack_into('<H', buf, 2, checksum)
    
    reply_id = (reply_id + 1) % USHRT_MAX
    struct.pack_into('<H', buf, 6, reply_id)
    
    return buf

def create_tcp_header(command, session_id, reply_id, data=b''):
    data_buffer = data
    buf = bytearray(8 + len(data_buffer))
    
    struct.pack_into('<H', buf, 0, command)
    struct.pack_into('<H', buf, 2, 0)  # Placeholder for checksum
    struct.pack_into('<H', buf, 4, session_id)
    struct.pack_into('<H', buf, 6, reply_id)
    
    buf[8:] = data_buffer
    
    checksum = create_checksum(buf)
    struct.pack_into('<H', buf, 2, checksum)
    
    reply_id = (reply_id + 1) % USHRT_MAX
    struct.pack_into('<H', buf, 6, reply_id)
    
    prefix_buf = bytearray([0x50, 0x50, 0x82, 0x7d, 0x13, 0x00, 0x00, 0x00])
    struct.pack_into('<H', prefix_buf, 4, len(buf))
    
    return prefix_buf + buf

def remove_tcp_header(buf):
    if len(buf) < 8:
        return buf
    
    if buf[:4] != b'\x50\x50\x82\x7d':
        return buf
    
    return buf[8:]

def decode_user_data_28(user_data):
    uid = struct.unpack('<H', user_data[0:2])[0]
    role = struct.unpack('<B', user_data[2:3])[0]
    name = user_data[8:16].decode('ascii').split('\0')[0]
    user_id = struct.unpack('<L', user_data[24:28])[0]
    return {'uid': uid, 'role': role, 'name': name, 'user_id': user_id}

def decode_user_data_72(user_data):
    uid = struct.unpack('<H', user_data[0:2])[0]
    role = struct.unpack('<B', user_data[2:3])[0]
    password = user_data[3:11].decode('ascii').split('\0')[0]
    name = user_data[11:].decode('ascii').split('\0')[0]
    cardno = struct.unpack('<L', user_data[35:39])[0]
    user_id = user_data[48:57].decode('ascii').split('\0')[0]
    return {'uid': uid, 'role': role, 'password': password, 'name': name, 'cardno': cardno, 'user_id': user_id}

def decode_record_data_40(record_data):
    user_sn = struct.unpack('<H', record_data[0:2])[0]
    device_user_id = record_data[2:11].decode('ascii').split('\0')[0]
    record_time = parse_time_to_date(struct.unpack('<L', record_data[27:31])[0])
    return {'user_sn': user_sn, 'device_user_id': device_user_id, 'record_time': record_time}

def decode_record_data_16(record_data):
    device_user_id = struct.unpack('<H', record_data[0:2])[0]
    record_time = parse_time_to_date(struct.unpack('<L', record_data[4:8])[0])
    return {'device_user_id': device_user_id, 'record_time': record_time}

def decode_record_real_time_log_18(record_data):
    user_id = struct.unpack('<B', record_data[8:9])[0]
    att_time = parse_hex_to_time(record_data[12:18])
    return {'user_id': user_id, 'att_time': att_time}

def decode_record_real_time_log_52(record_data):
    payload = remove_tcp_header(record_data)
    recv_data = payload[8:]
    user_id = recv_data[0:9].decode('ascii').split('\0')[0]
    att_time = parse_hex_to_time(recv_data[26:32])
    return {'user_id': user_id, 'att_time': att_time}

def decode_udp_header(header):
    command_id, checksum, session_id, reply_id = struct.unpack('<HHHH', header[:8])
    return {'command_id': command_id, 'checksum': checksum, 'session_id': session_id, 'reply_id': reply_id}

def decode_tcp_header(header):
    recv_data = header[8:]
    payload_size = struct.unpack('<H', header[4:6])[0]
    command_id, checksum, session_id, reply_id = struct.unpack('<HHHH', recv_data[:8])
    return {'command_id': command_id, 'checksum': checksum, 'session_id': session_id, 'reply_id': reply_id, 'payload_size': payload_size}

def export_error_message(command_value):
    for key, value in COMMANDS.items():
        if value == command_value:
            return key
    return 'AN UNKNOWN ERROR'

def check_not_event_tcp(data):
    try:
        data = remove_tcp_header(data)
        command_id = struct.unpack('<H', data[0:2])[0]
        event = struct.unpack('<H', data[4:6])[0]
        return event == COMMANDS['EF_ATTLOG'] and command_id == COMMANDS['CMD_REG_EVENT']
    except Exception as e:
        log(f"[228] : {str(e)} ,{data.hex()} ")
        return False

def check_not_event_udp(data):
    command_id = decode_udp_header(data[:8])['command_id']
    return command_id == COMMANDS['CMD_REG_EVENT']
