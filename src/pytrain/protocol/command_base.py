import abc
from abc import ABC
from ipaddress import IPv4Address, IPv6Address
from typing import Sequence, TypeVar

from ..comm.comm_buffer import CommBuffer
from ..pdi.pdi_req import PdiReq
from ..utils.validations import Validations
from .command_def import CommandDef, CommandDefEnum
from .command_req import CommandReq
from .constants import DEFAULT_BAUDRATE, DEFAULT_PORT, MINIMUM_DURATION_INTERVAL_MSEC, CommandScope

R = TypeVar("R", bound=CommandReq | PdiReq | Sequence[CommandReq | PdiReq])


class CommandBase(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        command: CommandDefEnum | None,
        command_req: R,
        address: int = 99,
        data: int = 0,
        scope: CommandScope = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
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
        # validate server ip address
        self._server, self._port = CommBuffer.parse_server(server, port)

        # persist command information
        self._command_def_enum: CommandDefEnum = command
        self._command_def: CommandDef = command.value if command else None
        self._command_req: R = command_req
        self._data: int = data
        self._scope: CommandScope = scope

        # build_req the command
        self._command = self._build_command()

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def bits(self) -> int:
        return self._command_req.bits if isinstance(self._command_req, CommandReq) else 0

    @property
    def address(self) -> int:
        return self._address

    @property
    def port(self) -> str:
        return self._port

    @property
    def server(self) -> IPv4Address | IPv6Address | None:
        return self._server

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def command_bytes(self) -> bytes:
        return self._command

    @property
    def command_prefix(self) -> bytes:
        return self._command_prefix()

    @property
    def command_req(self) -> R:
        return self._command_req

    def send(
        self,
        repeat: int = None,
        delay: float = None,
        duration: float = None,
        interval: int = None,
        shutdown: bool = False,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ):
        """
        Send the command to the LCS SER2 and keep comm buffer alive.
        """
        Validations.validate_int(repeat, min_value=1)
        Validations.validate_int(interval, min_value=MINIMUM_DURATION_INTERVAL_MSEC, allow_none=True)
        Validations.validate_float(delay, min_value=0)
        Validations.validate_float(duration, min_value=0, allow_none=True)
        if isinstance(self.command_req, CommandReq) or isinstance(self.command_req, PdiReq):
            reqs = [self.command_req]
        elif isinstance(self.command_req, Sequence):
            reqs = self.command_req
        else:
            raise ValueError(f"Unknown command type: {type(self.command_req)}")
        for req in reqs:
            req.send(
                repeat=repeat,
                delay=delay,
                duration=duration,
                interval=interval,
                baudrate=baudrate,
                port=port,
                server=server,
            )
        if shutdown:
            buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)
            buffer.shutdown()
            buffer.join()

    def fire(
        self,
        repeat: int = 1,
        delay: float = 0,
        duration: float = 0,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        """
        Fire the command immediately and shut down comm buffers, once empty
        """
        self.send(
            repeat=repeat,
            delay=delay,
            duration=duration,
            shutdown=True,
            baudrate=baudrate,
            port=port,
            server=server,
        )

    @staticmethod
    def _encode_command(command: int, num_bytes: int = 2) -> bytes:
        return command.to_bytes(num_bytes, byteorder="big")

    @abc.abstractmethod
    def _build_command(self) -> bytes | None:
        return None

    @abc.abstractmethod
    def _command_prefix(self) -> bytes | None:
        return None

    @abc.abstractmethod
    def _encode_address(self, command_op: int) -> bytes | None:
        return None
