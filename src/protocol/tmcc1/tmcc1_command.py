import abc
from abc import ABC

from ..command_base import CommandBase
from ..constants import TMCC1_COMMAND_PREFIX


class TMCC1Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        super().__init__(self, baudrate, port)

    def _encode_address(self, address: int, command_op: int) -> bytes:
        return self._encode_command((address << 7) | command_op)

    def _command_prefix(self) -> bytes:
        return TMCC1_COMMAND_PREFIX
