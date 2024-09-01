import abc
from abc import ABC

import serial
from serial.serialutil import SerialException


class CommandBase(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
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
    def port(self) -> str:
        return self._port

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def command_bytes(self) -> bytes:
        return self._command

    @property
    def command_prefix(self) -> bytes:
        return self._command_prefix()

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

    @staticmethod
    def _encode_command(command: int, num_bytes: int = 2) -> bytes:
        return command.to_bytes(num_bytes, byteorder='big')

    @abc.abstractmethod
    def _build_command(self) -> bytes | None:
        return None

    @abc.abstractmethod
    def _command_prefix(self) -> bytes | None:
        return None

    @abc.abstractmethod
    def _encode_address(self, address: int, command_op: int) -> bytes | None:
        return None


