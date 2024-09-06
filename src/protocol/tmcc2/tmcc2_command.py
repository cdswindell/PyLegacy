import abc
from abc import ABC

from ..command_base import CommandBase
from ..constants import TMCCCommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT


class TMCC2Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 command_scope: TMCCCommandScope,
                 address: int = 99,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        super().__init__(address, baudrate, port)
        self._command_scope = command_scope

    @property
    def scope(self) -> TMCCCommandScope:
        return self._command_scope

    def _encode_address(self, command_op: int) -> bytes:
        return self._encode_command((self.address << 9) | command_op)

    def _command_prefix(self) -> bytes:
        return self._command_scope.to_bytes(1, byteorder='big')
