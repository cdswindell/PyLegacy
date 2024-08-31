import abc

import serial


class CommandBase:
    __metaclass__ = abc.ABCMeta

    def __init__(self, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        self._baudrate = baudrate
        self._port = port
        self._is_legacy_cmd = None  # set value once we know what kind of command we have
        self._command = None  # provided by _build_command method in subclasses

    def fire(self) -> None:
        self.queue_cmd(self._command)

    def queue_cmd(self, cmd: bytes) -> None:
        print(f"Fire command {cmd.hex()}")

        if self._is_legacy_cmd:
            baudrate = self._baudrate
        else:
            baudrate = 9600

        with serial.Serial(self._port, baudrate) as ser:
            # Write the byte sequence
            ser.write(cmd)

    @abc.abstractmethod
    def _build_command(self) -> bytes | None:
        return None
