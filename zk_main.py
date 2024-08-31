import socket
import time
import asyncio
from handler import ZKError, ERROR_TYPES
from zk_tcp import JTCP
from zk_udp import JUDP

class ZKLIB:
    def __init__(self, ip, port=4370, timeout=30, inport=4000):
        self.connection_type = None
        self.jtcp = JTCP(ip, port, timeout)
        self.judp = JUDP(ip, port, timeout, inport)
        self.interval = None
        self.timer = None
        self.is_busy = False
        self.ip = ip

    def function_wrapper(self, tcp_callback, udp_callback=None, command=''):
        if self.connection_type == 'tcp':
            if self.jtcp.socket:
                try:
                    return tcp_callback()
                except Exception as err:
                    raise ZKError(err, f"[TCP] {command}", self.ip)
            else:
                raise ZKError("Socket isn't connected!", "[TCP]", self.ip)
        elif self.connection_type == 'udp':
            if self.judp.socket:
                try:
                    return udp_callback()
                except Exception as err:
                    raise ZKError(err, f"[UDP] {command}", self.ip)
            else:
                raise ZKError("Socket isn't connected!", "[UDP]", self.ip)
        else:
            raise ZKError("Socket isn't connected!", "", self.ip)

    def create_socket(self):
        try:
            if not self.jtcp.socket:
                try:
                    print("Attempting TCP connection...")
                    self.jtcp.create_socket()
                    print("TCP socket created, attempting to connect...")
                    self.jtcp.connect()
                    print('Connected via TCP')
                except Exception as err:
                    print(f"Error during TCP connection setup: {err}, errno: {getattr(err, 'errno', 'No errno')}")
                    raise  # Rethrow the exception after logging

            self.connection_type = 'tcp'

        except Exception as err:
            self.jtcp.disconnect()

            if not isinstance(err, ZKError) or err.errno != ERROR_TYPES.ECONNREFUSED:
                raise ZKError(err, 'TCP CONNECT', self.ip)

            try:
                if not self.judp.socket:
                    print("Falling back to UDP...")
                    self.judp.create_socket()
                    self.judp.connect()
                print('Connected via UDP')
                self.connection_type = 'udp'
            except Exception as udp_err:
                print(f"Error during UDP connection setup: {udp_err}, errno: {getattr(udp_err, 'errno', 'No errno')}")
                if udp_err.errno != ERROR_TYPES.EADDRINUSE:
                    self.connection_type = None
                    self.judp.disconnect()
                    self.judp.socket = None
                    self.jtcp.socket = None
                    raise ZKError(udp_err, 'UDP CONNECT', self.ip)
                else:
                    self.connection_type = 'udp'

    def get_users(self):
        return self.function_wrapper(self.jtcp.get_users, self.judp.get_users, 'get_users')

    def get_time(self):
        return self.function_wrapper(self.jtcp.get_time, self.judp.get_time, 'get_time')

    def get_serial_number(self):
        return self.function_wrapper(self.jtcp.get_serial_number, command='get_serial_number')

    def get_device_version(self):
        return self.function_wrapper(self.jtcp.get_device_version, command='get_device_version')

    def get_device_name(self):
        return self.function_wrapper(self.jtcp.get_device_name, command='get_device_name')

    def get_platform(self):
        return self.function_wrapper(self.jtcp.get_platform, command='get_platform')

    def get_os(self):
        return self.function_wrapper(self.jtcp.get_os, command='get_os')

    def get_work_code(self):
        return self.function_wrapper(self.jtcp.get_work_code, command='get_work_code')

    def get_pin(self):
        return self.function_wrapper(self.jtcp.get_pin, command='get_pin')

    def get_face_on(self):
        return self.function_wrapper(self.jtcp.get_face_on, command='get_face_on')

    def get_ssr(self):
        return self.function_wrapper(self.jtcp.get_ssr, command='get_ssr')

    def get_firmware(self):
        return self.function_wrapper(self.jtcp.get_firmware, command='get_firmware')

    def set_user(self, uid, userid, name, password, role=0, cardno=0):
        return self.function_wrapper(lambda: self.jtcp.set_user(uid, userid, name, password, role, cardno), command='set_user')

    def get_attendance_size(self):
        return self.function_wrapper(self.jtcp.get_attendance_size, command='get_attendance_size')

    def get_attendances(self, cb):
        return self.function_wrapper(lambda: self.jtcp.get_attendances(cb), lambda: self.judp.get_attendances(cb), 'get_attendances')

    def get_real_time_logs(self, cb):
        return self.function_wrapper(lambda: self.jtcp.get_real_time_logs(cb), lambda: self.judp.get_real_time_logs(cb), 'get_real_time_logs')

    def disconnect(self):
        return self.function_wrapper(self.jtcp.disconnect, self.judp.disconnect, 'disconnect')

    def free_data(self):
        return self.function_wrapper(self.jtcp.free_data, self.judp.free_data, 'free_data')

    def disable_device(self):
        return self.function_wrapper(self.jtcp.disable_device, self.judp.disable_device, 'disable_device')

    def enable_device(self):
        return self.function_wrapper(self.jtcp.enable_device, self.judp.enable_device, 'enable_device')

    def get_info(self):
        return self.function_wrapper(self.jtcp.get_info, self.judp.get_info, 'get_info')

    def get_socket_status(self):
        return self.function_wrapper(self.jtcp.get_socket_status, self.judp.get_socket_status, 'get_socket_status')

    def clear_attendance_log(self):
        return self.function_wrapper(self.jtcp.clear_attendance_log, self.judp.clear_attendance_log, 'clear_attendance_log')

    def execute_cmd(self, command, data=''):
        return self.function_wrapper(lambda: self.jtcp.execute_cmd(command, data), lambda: self.judp.execute_cmd(command, data), 'execute_cmd')

    def set_interval_schedule(self, cb, timer):
        self.interval = True
        while self.interval:
            cb()
            time.sleep(timer)

    def set_timer_schedule(self, cb, timer):
        self.timer = time.time() + timer
        while time.time() < self.timer:
            pass
        cb()


# Example usage for testing TCP connection
if __name__ == "__main__":
    async def test():
        zk_instance = ZKLIB("192.168.1.235", 4370, 30)
        try:
            # Create socket to machine
            zk_instance.create_socket()

            # Get general info like logCapacity, user counts, logs count
            print("Device Info:", zk_instance.get_info())

            # Retrieve users
            users = zk_instance.get_users()
            print("User Details:", users['data'])

        except Exception as e:
            print("Error:", e)
        finally:
            # Disconnect from the device
            zk_instance.disconnect()

    # Run the test function
    asyncio.run(test())
