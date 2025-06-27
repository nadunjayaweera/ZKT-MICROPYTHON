# micropython_zklib/zklib/errors.py

class ZKError(Exception):
    def __init__(self, message, command=None, ip=None):
        super().__init__(message)
        self.command = command
        self.ip = ip

    def __str__(self):
        return f"ZKError: {self.args[0]}, Command: {self.command}, IP: {self.ip}"

class ZKConnectionError(ZKError):
    pass

class ZKTimeoutError(ZKError):
    pass

class ZKRefusedError(ZKError):
    pass

class ZKDisconnectedError(ZKError):
    pass
