import abc
import time
from abc import ABC
from enum import Enum
from typing import Type

from .constants import DEFAULT_BAUDRATE, DEFAULT_PORT, TMCC2CommandPrefix, TMCC1_COMMAND_PREFIX
from .constants import CommandScope, TMCC1Enum
from .constants import CommandSyntax, OptionEnum, Option
from .constants import TMCC2Enum, TMCC1RouteOption, TMCC1CommandPrefix
from .validations import Validations
from ..comm.comm_buffer import CommBuffer


class CommandBase(ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def send_command(cls,
                     address: int,
                     command: OptionEnum,
                     data: int = 0,
                     scope: CommandScope = None,
                     repeat: int = 1,
                     delay: int = 0,
                     baudrate: int = DEFAULT_BAUDRATE,
                     port: str = DEFAULT_PORT
                     ) -> None:
        # build & queue
        cmd = cls._build_command_bytes(address, command, data, scope)
        cls._enqueue_command(cmd, repeat, delay, baudrate, port)

    @classmethod
    def send_func(cls,
                  address: int,
                  command: OptionEnum,
                  data: int = 0,
                  scope: CommandScope = CommandScope.ENGINE,
                  repeat: int = 1,
                  delay: int = 0,
                  baudrate: int = DEFAULT_BAUDRATE,
                  port: str = DEFAULT_PORT
                  ):
        # build & queue
        cmd = cls._build_command_bytes(address, command, data, scope)

        def send_func() -> None:
            print(f"cmd: {cmd} repeat: {repeat} delay: {delay}")
            cls._enqueue_command(cmd, repeat, delay, baudrate, port)
        return send_func

    @classmethod
    def _determine_command_prefix_bytes(cls,
                                        command: OptionEnum,
                                        scope: CommandScope) -> bytes:
        """
            Generalized command scopes, such as ENGINE, SWITCH, etc.,
            map to syntax-specific command identifiers defined
            for the TMCC1 and TMCC2 commands
        """
        if scope is None:
            return command.command_prefix_bytes
        # otherwise, we need to figure out if we're returning a
        # TMCC1-style or TMCC2-style command prefix
        if isinstance(command, TMCC1Enum):
            return TMCC1_COMMAND_PREFIX.to_bytes(1, byteorder='big')
        elif isinstance(command, TMCC2Enum):
            return TMCC2CommandPrefix(scope.name).as_bytes
        raise TypeError(f"Command type not recognized {command}")

    @classmethod
    def _build_command_bytes(cls,
                             address: int,
                             command: OptionEnum,
                             data: int = 0,
                             scope: CommandScope = None,
                             ) -> bytes:
        # build command
        command_op = cls._vet_option(command, address, data, scope)
        prefix_bytes = cls._determine_command_prefix_bytes(command, scope)
        return prefix_bytes + command_op.as_bytes

    @classmethod
    def _vet_option(cls,
                    command: OptionEnum,
                    address: int,
                    data: int,
                    scope: CommandScope,
                    ) -> Option:
        if isinstance(command, TMCC1Enum):
            enum_class = TMCC1Enum
        elif isinstance(command, TMCC2Enum):
            enum_class = TMCC2Enum
        else:
            raise TypeError(f"Command type not recognized {command}")

        max_val = 99
        syntax = CommandSyntax.TMCC2 if enum_class == TMCC2Enum else CommandSyntax.TMCC1
        if syntax == CommandSyntax.TMCC1 and command == TMCC1RouteOption.ROUTE:
            scope = TMCC1CommandPrefix.ROUTE
            max_val = 31
        address = Validations.validate_int(address, min_value=1, max_value=max_val, label=scope.name.capitalize())

        # validate data field and apply data bits
        command_op: Option = command.option
        if command_op.num_data_bits > 0:
            command_op.apply_data(data)

        # apply address; also handles work for TMCC1 train commands
        command_op.apply_address(address, scope)
        return command_op

    @classmethod
    def _enqueue_command(cls, cmd: bytes, repeat: int, delay: int, baudrate: int, port: str):
        repeat = Validations.validate_int(repeat, min_value=1, label="repeat")
        delay = Validations.validate_int(delay, min_value=0, label="delay")

        # send command to comm buffer
        buffer = CommBuffer(baudrate=baudrate, port=port)
        for _ in range(repeat):
            if delay > 0 and repeat == 1:
                time.sleep(delay)
            buffer.enqueue_command(cmd)
            if repeat != 1 and delay > 0 and _ != repeat - 1:
                time.sleep(delay)

    def __init__(self,
                 address: int,
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

    def send(self, repeat: int = 1, delay: int = 0, shutdown: bool = False):
        """
            Send the command to the LCS SER2 and keep comm buffer alive.
        """
        Validations.validate_int(repeat, min_value=1)
        Validations.validate_int(delay, min_value=0)
        for _ in range(repeat):
            if delay > 0 and repeat == 1:
                time.sleep(delay)
            self._comm_buffer.enqueue_command(self.command_bytes)
            if repeat != 1 and delay > 0 and _ != repeat - 1:
                time.sleep(delay)
        if shutdown:
            self._comm_buffer.shutdown()
            self._comm_buffer.join()

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
