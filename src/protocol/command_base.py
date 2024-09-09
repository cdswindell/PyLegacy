import abc
import time
from abc import ABC

from .constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from ..comm.comm_buffer import CommBuffer


class CommandBase(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 address: int,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        self._address = address
        self._command = None  # provided by _build_command method in subclasses
        # validate baudrate
        if baudrate is None or baudrate < 110 or baudrate > 115000 or not isinstance(baudrate, int):
            raise ValueError("baudrate must be between 110 and 115000")
        self._baudrate = baudrate
        # validate port
        if port is None:
            raise ValueError("port cannot be None")
        self._port = port
        # create a CommBuffer to enqueue commands
        self._comm_buffer = CommBuffer(baudrate=self.baudrate, port=self.port)

    @property
    def address(self) -> int:
        return self._address

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

    def send(self, repeat: int = 1, shutdown: bool = False):
        """
            Send the command to the LCS SER2 and keep comm buffer alive.
        """
        for _ in range(repeat):
            self._comm_buffer.enqueue_command(self.command_bytes)
        if shutdown:
            time.sleep(1)
            self._comm_buffer.shutdown()

    def fire(self, repeat: int = 1) -> None:
        """
            Fire the command immediately and shut down comm buffers, once empty
        """
        self.send(repeat=repeat, shutdown=True)

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
    def _encode_address(self, command_op: int) -> bytes | None:
        return None
