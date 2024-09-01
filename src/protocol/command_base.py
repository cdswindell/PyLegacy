import abc

import serial
from serial.serialutil import SerialException


class CommandBase:
    __metaclass__ = abc.ABCMeta

    def __init__(self, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        self._is_legacy_cmd = None  # set value once we know what kind of command we have
        self._command = None  # provided by _build_command method in subclasses
        # validate baudrate
        if baudrate is None or baudrate < 110 or baudrate > 115000 or not isinstance(baudrate, int):
            raise ValueError("baudrate must be between 110 and 115000")
        self._baudrate = baudrate
        # validate port
        if port is None:
            raise ValueError("port cannot be None")
        self._port = port

    @property
    def is_legacy_cmd(self) -> bool:
        return bool(self._is_legacy_cmd)

    @property
    def is_tmcc1_cmd(self) -> bool:
        return self._is_legacy_cmd is not None and self._is_legacy_cmd is False

    @property
    def port(self) -> str:
        return self._port

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def command_bytes(self) -> bytes:
        return self._command

    def fire(self) -> None:
        try:
            self.queue_cmd(self._command)
        except SerialException as se:
            print(se)

    def queue_cmd(self, cmd: bytes) -> None:
        print(f"Fire command {cmd.hex()}")

        with serial.Serial(self.port, self.baudrate) as ser:
            # Write the byte sequence
            ser.write(cmd)

    @abc.abstractmethod
    def _build_command(self) -> bytes | None:
        return None
