import abc
from abc import ABC

from ..command_base import CommandBase
from ..constants import TMCC1_COMMAND_PREFIX, DEFAULT_BAUDRATE, DEFAULT_PORT


class TMCC1Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 address: int = 99,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        super().__init__(address, baudrate, port)

    def _encode_address(self, command_op: int) -> bytes:
        return self._encode_command((self.address << 7) | command_op)

    def _command_prefix(self) -> bytes:
        return TMCC1_COMMAND_PREFIX.to_bytes(1, 'big')
