from __future__ import annotations

import sys

from .multibyte_command_req import MultiByteReq
from .multibyte_constants import TMCC2_VARIABLE_INDEX, TMCC2VariableEnum, VariableCommandDef

if sys.version_info >= (3, 11):
    from typing import List, Self

from ..constants import DEFAULT_ADDRESS, CommandScope
from ..tmcc2.tmcc2_constants import (
    LEGACY_TRAIN_COMMAND_PREFIX,
    TMCC2_SCOPE_TO_FIRST_BYTE_MAP,
)

"""
Commands to send/receive variable data byte commands
"""


class VariableCommandReq(MultiByteReq):
    @classmethod
    def build(
        cls,
        command: TMCC2VariableEnum,
        address: int = DEFAULT_ADDRESS,
        data_bytes: int | List[int] = None,
        scope: CommandScope = None,
    ) -> Self:
        return VariableCommandReq(command, address, data_bytes, scope)

    @classmethod
    def from_bytes(cls, param: bytes, from_tmcc_rx: bool = False, is_tmcc4: bool = False) -> Self:
        _, is_mvb, is_d4 = cls.vet_bytes(param, "Variable")
        if is_mvb:
            # 0xf8 bb 6f | fb ba 01 | fb ba 01 | fb ba b0 | fb ba c8 | fb ba b9
            index = 0x00FF & int.from_bytes(param[1:3], byteorder="big")
            if index != TMCC2_VARIABLE_INDEX:
                raise ValueError(f"Invalid Variable byte command: {param.hex(':')}")
            pkt_len = 7 if is_d4 else 3
            num_data_words = int(param[pkt_len + 2])
            if (5 + num_data_words) * pkt_len != len(param):
                raise ValueError(f"Command requires {(5 + num_data_words) * pkt_len} bytes: {param.hex(':')}")
            # extract command
            pi = int(param[3 * pkt_len + 2]) << 8 | int(param[2 * pkt_len + 2])
            cmd_enum = TMCC2VariableEnum.by_value(pi)
            if isinstance(cmd_enum, TMCC2VariableEnum):
                scope = CommandScope.ENGINE
                if int(param[0]) == LEGACY_TRAIN_COMMAND_PREFIX:
                    scope = CommandScope.TRAIN
                data_bytes = []
                # harvest all the data bytes; they are the third byte of each data word
                # data starts with word 5
                for i in range(4 * pkt_len + 2, 5 * pkt_len + (num_data_words - 1) * pkt_len, pkt_len):
                    data_bytes.append(param[i])
                # validate check checksum
                chksum_byte_index = 2 - pkt_len
                if cls.checksum(param[:chksum_byte_index], is_d4) != param[chksum_byte_index].to_bytes(
                    1, byteorder="big"
                ):
                    raise ValueError(
                        f"Invalid Variable byte checksum: {param.hex(':')} != {cls.checksum(param[:-1]).hex()}"
                    )
                # build_req the request and return
                address = cmd_enum.value.address_from_bytes(param[1:7] if is_d4 else param[1:3])
                cmd_req = VariableCommandReq.build(cmd_enum, address, data_bytes, scope)
                cmd_req._is_tmcc_rx = from_tmcc_rx
                cmd_req._is_tmcc4 = is_d4
                return cmd_req
        raise ValueError(f"Invalid variable byte command: {param.hex(':')}")

    def __init__(
        self,
        command_def_enum: TMCC2VariableEnum,
        address: int = DEFAULT_ADDRESS,
        data_bytes: int | List[int] = None,
        scope: CommandScope = None,
    ) -> None:
        if isinstance(data_bytes, int):
            super().__init__(command_def_enum, address, data_bytes, scope)
        elif isinstance(data_bytes, list) and len(data_bytes) == 1 and isinstance(data_bytes[0], int):
            super().__init__(command_def_enum, address, data_bytes[0], scope)
        else:
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
        Returns the number of bytes in this command. Commands consist
        of three-byte words where:
            Word 1: Command index
            Word 2: Number of data words (N)
            Word 3: LSB of destination address
            Word 4: MSB of destination address
            Words 5 - N: Data words
            Word N + 1: Checksum
        """
        pkt_len = 7 if self.is_tmcc4 else 3
        return (5 + self.command.value.num_data_bytes) * pkt_len

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
        if self.address > 99:
            # handle 4-digit address
            address_bytes = str(self.address).zfill(4).encode()
            tmp = bytes()
            for i in range(0, len(byte_str), 3):
                tmp += byte_str[i : i + 3] + address_bytes
            byte_str = tmp
        return byte_str

    @property
    def index_byte(self) -> bytes:
        return TMCC2_VARIABLE_INDEX.to_bytes(1, byteorder="big")

    @property
    def data_byte(self) -> bytes:
        return (0x00).to_bytes(1, byteorder="big")
