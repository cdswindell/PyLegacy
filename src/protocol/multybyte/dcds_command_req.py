from __future__ import annotations

import sys

from .multibyte_command_req import MultiByteReq
from .multibyte_constants import TMCC2_VARIABLE_INDEX, TMCC2DCDSEnum, VariableCommandDef

if sys.version_info >= (3, 11):
    from typing import List, Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from ..constants import DEFAULT_ADDRESS, CommandScope
from ..tmcc2.tmcc2_constants import (
    LEGACY_MULTIBYTE_COMMAND_PREFIX,
    LEGACY_TRAIN_COMMAND_PREFIX,
    TMCC2_SCOPE_TO_FIRST_BYTE_MAP,
)

"""
Commands to modify DCDS EEPROM
"""


class DcdsCommandReq(MultiByteReq):
    @classmethod
    def build(
        cls,
        command: TMCC2DCDSEnum,
        address: int = DEFAULT_ADDRESS,
        data_bytes: int | List[int] = None,
        scope: CommandScope = None,
    ) -> Self:
        return DcdsCommandReq(command, address, data_bytes, scope)

    @classmethod
    def from_bytes(cls, param: bytes) -> Self:
        if not param or len(param) < 18:
            raise ValueError(f"DCDS command requires at least 18 bytes {param.hex(':')}")
        if (
            len(param) >= 18
            and param[3] == param[6] == param[9] == param[12] == param[15] == LEGACY_MULTIBYTE_COMMAND_PREFIX
        ):
            index = 0x00FF & int.from_bytes(param[1:3], byteorder="big")
            if index != TMCC2_VARIABLE_INDEX:
                raise ValueError(f"Invalid DCDS command: {param.hex(':')}")
            num_data_words = int(param[5])
            if (5 + num_data_words) * 3 != len(param):
                raise ValueError(f"Command requires {(5 + num_data_words) * 3} bytes: {param.hex(':')}")
            pi = int(param[11]) << 8 | int(param[8])
            print(f"pi: {hex(pi)}")
            cmd_enum = TMCC2DCDSEnum.by_value(pi)
            print(f"pi: {hex(pi)} enum: {cmd_enum}")
            if cmd_enum:
                address = cmd_enum.value.address_from_bytes(param[1:3])
                scope = CommandScope.ENGINE
                if int(param[0]) == LEGACY_TRAIN_COMMAND_PREFIX:
                    scope = CommandScope.TRAIN
                data_bytes = []
                # harvest all the data bytes; they are the third byte of each data word
                # data starts with word 5
                for i in range(14, 15 + (num_data_words - 1) * 3, 3):
                    data_bytes.append(param[i])
                # build_req the request and return
                return DcdsCommandReq.build(cmd_enum, address, data_bytes, scope)
        raise ValueError(f"Invalid DCDS command: {param.hex(':')}")

    def __init__(
        self,
        command_def_enum: TMCC2DCDSEnum,
        address: int = DEFAULT_ADDRESS,
        data_bytes: int | List[int] = None,
        scope: CommandScope = None,
    ) -> None:
        super().__init__(command_def_enum, address, 0, scope)
        if data_bytes is not None and isinstance(data_bytes, int):
            self._data_bytes = [data_bytes]
        else:
            self._data_bytes = data_bytes if data_bytes is not None else []

    def __repr__(self) -> str:
        return super().__repr__()

    @property
    def data_bytes(self) -> List[int]:
        return self._data_bytes

    @property
    def num_bytes(self) -> int:
        """
        Returns the number of bytes in this command. Commands are comprised
        of three-byte words where:
            Word 1: Command index
            Word 2: Number of data words (N)
            Word 3: LSB of destination address
            Word 4: MSB of destination address
            Words 5 - N: Data words
            Word N + 1: Checksum
        """
        return (5 + self.command.value.num_data_bytes) * 3

    # noinspection PyTypeChecker
    @property
    def as_bytes(self) -> bytes:
        cd: VariableCommandDef = self.command_def
        byte_str = bytes()
        # first word is encoded address and 0x6F byte denoting variable byte packet
        byte_str += TMCC2_SCOPE_TO_FIRST_BYTE_MAP[self.scope].to_bytes(1, byteorder="big") + self._word_1
        # Word 2: number of data bytes/words
        byte_str += self.word_prefix + len(self.data_bytes).to_bytes(1, byteorder="big")
        # words 3 & 4: command LSB and MSB
        byte_str += self.word_prefix + cd.lsb.to_bytes(1, byteorder="big")
        byte_str += self.word_prefix + cd.msb.to_bytes(1, byteorder="big")
        # now add data words
        for data_byte in self.data_bytes:
            byte_str += self.word_prefix + data_byte.to_bytes(1, byteorder="big")
        # finally, add the checksum word
        byte_str += self.word_prefix
        byte_str += self.checksum(byte_str)
        return byte_str

    @property
    def index_byte(self) -> bytes:
        return TMCC2_VARIABLE_INDEX.to_bytes(1, byteorder="big")

    @property
    def data_byte(self) -> bytes:
        return (0x00).to_bytes(1, byteorder="big")
