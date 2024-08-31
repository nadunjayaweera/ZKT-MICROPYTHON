class ERROR_TYPES:
    ECONNRESET = 'ECONNRESET'
    ECONNREFUSED = 'ECONNREFUSED'
    EADDRINUSE = 'EADDRINUSE'
    ETIMEDOUT = 'ETIMEDOUT'

class ZKError(Exception):
    def __init__(self, err, command, ip):
        self.err = err
        self.ip = ip
        self.command = command

    def toast(self):
        if self.err == ERROR_TYPES.ECONNRESET:
            return f'Another device is connecting to the device so the connection is interrupted. IP: {self.ip}'
        elif self.err == ERROR_TYPES.ECONNREFUSED:
            return f'IP of the device is refused. IP: {self.ip}'
        else:
            return f'Error: {self.err} on IP: {self.ip}'

    def get_error(self):
        return {
            'err': {
                'message': str(self.err),
                'code': self.err
            },
            'ip': self.ip,
            'command': self.command
        }

# Example usage
if __name__ == "__main__":
    try:
        raise ZKError(ERROR_TYPES.ECONNREFUSED, 'CMD_CONNECT', '192.168.1.235')
    except ZKError as e:
        print(e.toast())
