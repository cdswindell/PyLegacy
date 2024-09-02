import abc
from abc import ABC

from ..command_base import CommandBase
from ..constants import TMCC2CommandScope


class TMCC2Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, command_scope: TMCC2CommandScope, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        super().__init__(baudrate, port)
        self._command_scope = command_scope

    def _encode_address(self, address: int, command_op: int) -> bytes:
        return self._encode_command((address << 9) | command_op)

    def _command_prefix(self) -> bytes:
        return self._command_scope.to_bytes(1, byteorder='big')
