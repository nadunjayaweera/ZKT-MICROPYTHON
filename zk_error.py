class ZKError(Exception):  # Inherit from Exception
    ERROR_TYPES = {
        'ECONNRESET': 'ECONNRESET',
        'ECONNREFUSED': 'ECONNREFUSED',
        'EADDRINUSE': 'EADDRINUSE',
        'ETIMEDOUT': 'ETIMEDOUT'
    }

    def __init__(self, err, command, ip):
        self.err = err
        self.ip = ip
        self.command = command

    def toast(self):
        if self.err == ZKError.ERROR_TYPES['ECONNRESET']:
            return f'Another device is connecting to the device, so the connection is interrupted (IP: {self.ip}).'
        elif self.err == ZKError.ERROR_TYPES['ECONNREFUSED']:
            return f'Connection refused by the device (IP: {self.ip}).'
        elif self.err == ZKError.ERROR_TYPES['ETIMEDOUT']:
            return f'Connection to the device timed out (IP: {self.ip}).'
        else:
            return f'Error: {str(self.err)} (Command: {self.command}, IP: {self.ip}).'

    def get_error(self):
        return {
            'err': {
                'message': str(self.err),
                'code': self.err
            },
            'ip': self.ip,
            'command': self.command
        }
