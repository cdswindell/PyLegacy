from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from typing import TypeVar

import sys

from .multibyte_constants import TMCCPrefixEnum, TMCC2ParameterEnum

if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from ..command_req import CommandReq
from ..constants import DEFAULT_ADDRESS, CommandScope
from ..tmcc2.tmcc2_constants import TMCC2_SCOPE_TO_FIRST_BYTE_MAP, LEGACY_MULTIBYTE_COMMAND_PREFIX
from .multibyte_constants import TMCC2MultiByteEnum

E = TypeVar("E", bound=TMCC2MultiByteEnum)

MULTIBYTE_PREFIX_BYTE = LEGACY_MULTIBYTE_COMMAND_PREFIX.to_bytes(1, byteorder="big")


class MultiByteReq(CommandReq, ABC):
    __metaclass__ = ABCMeta

    @classmethod
    def build(
        cls, command: TMCC2MultiByteEnum, address: int = DEFAULT_ADDRESS, data: int = 0, scope: CommandScope = None
    ) -> Self:
        if isinstance(command, TMCC2ParameterEnum):
            from .param_command_req import ParameterCommandReq  # noqa: E402

            return ParameterCommandReq.build(command, address, data, scope)

    @classmethod
    def vet_bytes(cls, param: bytes, cmd_type: str = "", raise_exception: bool = True) -> tuple[bool, bool]:
        is_vmb = False
        is_d4 = False

        if not param:
            if raise_exception:
                raise ValueError("Command requires at least 9 bytes")
            else:
                return is_vmb, is_d4
        if len(param) < 9:
            if raise_exception:
                raise ValueError(f"{cmd_type} command requires at least 9 bytes {param.hex(':')}")
            else:
                return is_vmb, is_d4
        if (
            len(param) == 9
            and param[3] == LEGACY_MULTIBYTE_COMMAND_PREFIX
            and param[6] == LEGACY_MULTIBYTE_COMMAND_PREFIX
        ):
            is_vmb = True
        elif (
            len(param) == 21
            and param[7] == LEGACY_MULTIBYTE_COMMAND_PREFIX
            and param[14] == LEGACY_MULTIBYTE_COMMAND_PREFIX
        ):
            is_vmb = is_d4 = True
        return is_vmb, is_d4

    @classmethod
    def from_bytes(cls, param: bytes, from_tmcc_rx: bool = False, is_tmcc4: bool = False) -> Self:
        is_vmb, _ = cls.vet_bytes(param, "Multy-byte")
        if is_vmb is True:
            index = 0x00F0 & int.from_bytes(param[1:3], byteorder="big")
            prefix = TMCCPrefixEnum.by_value(index)
            if prefix == TMCCPrefixEnum.PARAMETER:
                from .param_command_req import ParameterCommandReq  # noqa: E402

                return ParameterCommandReq.from_bytes(param, from_tmcc_rx, is_tmcc4)
            elif prefix == TMCCPrefixEnum.R4LC:
                from .r4lc_command_req import R4LCCommandReq  # noqa: E402

                return R4LCCommandReq.from_bytes(param, from_tmcc_rx, is_tmcc4)
            elif prefix == TMCCPrefixEnum.VARIABLE:
                from .dcds_command_req import VariableCommandReq

                return VariableCommandReq.from_bytes(param, from_tmcc_rx, is_tmcc4)
        raise ValueError(f"Invalid multibyte command: : {param.hex(':')}")

    def __init__(
        self,
        command_def_enum: E,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
    ) -> None:
        super().__init__(command_def_enum, address, data, scope)

    @property
    def num_bytes(self) -> int:
        """
        Returns the number of bytes in this command. Except for the
        Variable length  multibyte commands, this is always 9 bytes
        in three sets of three bytes a piece.
        """
        if 1 <= self.address <= 99:
            return 9
        else:  # 4-digit addressing
            return 21

    @property
    def as_bytes(self) -> bytes:
        byte_str = bytes()
        byte_str += TMCC2_SCOPE_TO_FIRST_BYTE_MAP[self.scope].to_bytes(1, byteorder="big")
        byte_str += self._word_1
        byte_str += self.word_prefix
        byte_str += self._word_2
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
    def multibyte_word_prefix(self):
        return LEGACY_MULTIBYTE_COMMAND_PREFIX.to_bytes(1, byteorder="big")

    @property
    def address_byte(self) -> bytes:
        e_t = 1 if self.scope == CommandScope.TRAIN else 0
        if 1 <= self.address <= 99:
            address = self.address
        else:
            address = 0  # prep for 4-digit
        return ((address << 1) + e_t).to_bytes(1, "big")

    @property
    def word_prefix(self) -> bytes:
        return MULTIBYTE_PREFIX_BYTE + self.address_byte

    @property
    def _word_1(self) -> bytes:
        if 1 <= self.address <= 99:
            address = self.address
        else:
            address = 0  # prep for 4-digit
        return ((address << 1) + 1).to_bytes(1, "big") + self.index_byte

    @property
    def _word_2(self) -> bytes:
        return self.data_byte

    # noinspection PyUnusedLocal
    @staticmethod
    def checksum(data: bytes = None) -> bytes:
        """
        Calculate the checksum of a fixed-length lionel tmcc2 multibyte command.
        The checksum is calculated adding together the second 2 bytes of the
        parameter index and parameter data words, and the addr byte of the checksum
        word, and returning the 1's complement of that sum mod 256.

        We make use of self.command_scope to determine if the command directed at
        an engine or train.
        """
        byte_sum = 0
        for b in data:
            if b not in {0xF8, 0xF9, 0xFB}:
                byte_sum += int(b)
        return (~(byte_sum % 256) & 0xFF).to_bytes(1, byteorder="big")  # return 1's complement of sum mod 256

    def _apply_address(self, **kwargs) -> int:
        return self.command_def.bits

    def _apply_data(self, **kwargs) -> int:
        return self.command_def.bits

    @property
    @abstractmethod
    def index_byte(self) -> bytes:
        pass

    @property
    @abstractmethod
    def data_byte(self) -> bytes:
        pass
