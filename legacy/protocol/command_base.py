class CommandBase:
    def __init__(self, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        self._baudrate = baudrate
        self._port = port
