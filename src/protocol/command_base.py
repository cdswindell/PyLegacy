import abc
import time
from abc import ABC
from enum import Enum
from typing import Type

from .constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from .constants import CommandSyntax, OptionEnum, Option
from .constants import TMCC2Enum, TMCC1RouteOption, TMCC1CommandPrefix
from .validations import Validations
from ..comm.comm_buffer import CommBuffer


class CommandBase(ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def _vet_option(cls,
                    enum_class: Type[OptionEnum],
                    command: OptionEnum,
                    address: int,
                    data: int,
                    scope: Enum,
                    ) -> Option:
        if command is None or not isinstance(command, enum_class):
            raise TypeError(f"Command must be of type TMCC1Enum {command}")

        max_val = 99
        syntax = CommandSyntax.TMCC2 if enum_class == TMCC2Enum else CommandSyntax.TMCC1
        if syntax == CommandSyntax.TMCC1 and command == TMCC1RouteOption.ROUTE:
            scope = TMCC1CommandPrefix.ROUTE
            max_val = 31
        address = Validations.validate_int(address, min_value=1, max_value=max_val, label=scope.name.capitalize())

        # validate data field and apply data bits
        command_op: Option = command.value
        if command_op.num_data_bits > 0:
            command_op.apply_data(data)

        # apply address
        command_op.apply_address(address, syntax)
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
