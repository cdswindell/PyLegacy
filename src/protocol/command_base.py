import abc
import time
from abc import ABC

from .command_req import CommandReq
from .constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandDefEnum, CommandDef, CommandScope
from .validations import Validations
from ..comm.comm_buffer import CommBuffer


class CommandBase(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 command: CommandDefEnum,
                 command_req: CommandReq,
                 address: int = 99,
                 data: int = 0,
                 scope: CommandScope = None,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        self._address = address
        self._command = None  # provided by _build_command method in subclasses
        # validate baudrate
        if baudrate is None or baudrate < 110 or baudrate > 115200 or not isinstance(baudrate, int):
            raise ValueError("baudrate must be between 110 and 115200")
        self._baudrate = baudrate
        # validate port
        if port is None:
            raise ValueError("port cannot be None")
        self._port = port

        # persist command information
        self._command_def_enum: CommandDefEnum = command
        self._command_def: CommandDef = command.value
        self._command_req: CommandReq = command_req
        self._data: int = data
        self._scope: CommandScope = scope

        # build the command
        self._command = self._build_command()

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def bits(self) -> int:
        return self._command_req.bits

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

    def send(self, repeat: int = 1, delay: int = 0, shutdown: bool = False):
        """
            Send the command to the LCS SER2 and keep comm buffer alive.
        """
        Validations.validate_int(repeat, min_value=1)
        Validations.validate_int(delay, min_value=0)

        # create a CommBuffer to enqueue commands
        comm_buffer = CommBuffer(baudrate=self.baudrate, port=self.port)
        for _ in range(repeat):
            if delay > 0 and repeat == 1:
                time.sleep(delay)
            comm_buffer.enqueue_command(self.command_bytes)
            if repeat != 1 and delay > 0 and _ != repeat - 1:
                time.sleep(delay)
        if shutdown:
            comm_buffer.shutdown()
            comm_buffer.join()

    def fire(self, repeat: int = 1, delay: int = 0) -> None:
        """
            Fire the command immediately and shut down comm buffers, once empty
        """
        self.send(repeat=repeat, delay=delay, shutdown=True)

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
