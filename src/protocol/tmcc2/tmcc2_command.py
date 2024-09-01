import abc
from abc import ABC

from ..command_base import CommandBase
from ..constants import TMCC2CommandScope, TMCC2_COMMAND_SCOPE_TO_COMMAND_PREFIX


class TMCC2Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, command_scope: TMCC2CommandScope, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        super().__init__(self, baudrate, port)
        self._command_scope = command_scope

    def _encode_address(self, address: int, command_op: int) -> bytes:
        return self._encode_command((address << 9) | command_op)

    def _command_prefix(self) -> bytes:
        return TMCC2_COMMAND_SCOPE_TO_COMMAND_PREFIX[self._command_scope]
