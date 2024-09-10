import abc
from abc import ABC

from ..command_base import CommandBase
from ..constants import TMCC1_COMMAND_PREFIX, DEFAULT_BAUDRATE, DEFAULT_PORT, TMCC1Enum
from ..constants import OptionEnum, TMCC1CommandPrefix


class TMCC1Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def send_command(cls,
                     address: int,
                     command: OptionEnum,
                     data: int = 0,
                     scope: TMCC1CommandPrefix = None,
                     repeat: int = 1,
                     delay: int = 0,
                     baudrate: int = DEFAULT_BAUDRATE,
                     port: str = DEFAULT_PORT
                     ) -> None:
        # if scope not provided, look at first two bites of command
        if scope is None:
            scope_bits = (0xF000 & command.value.command) >> 8
            scope = TMCC1CommandPrefix.by_value(scope_bits, True)
        command_op = cls._vet_option(TMCC1Enum, command, address, data, scope)
        # apply scope bits; they are the first two
        if scope == TMCC1CommandPrefix.TRAIN:
            command_op = TMCC1CommandPrefix.TRAIN | command_op.command
        else:
            command_op = command_op.command
        cmd = TMCC1_COMMAND_PREFIX.to_bytes(1, byteorder='big') + command_op.to_bytes(2, byteorder='big')
        # and queue it to send
        cls._enqueue_command(cmd, repeat, delay, baudrate, port)

    def __init__(self,
                 address: int = 99,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        super().__init__(address, baudrate, port)

    def _encode_address(self, command_op: int) -> bytes:
        return self._encode_command((self.address << 7) | command_op)

    def _command_prefix(self) -> bytes:
        return TMCC1_COMMAND_PREFIX.to_bytes(1, 'big')
