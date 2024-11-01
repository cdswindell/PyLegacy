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
    def from_bytes(cls, param: bytes) -> Self:
        if not param:
            raise ValueError("Command requires at least 9 bytes")
        if len(param) < 9:
            raise ValueError(f"Multy-byte command requires at least 9 bytes {param.hex(':')}")
        if (
            len(param) == 9
            and param[3] == LEGACY_MULTIBYTE_COMMAND_PREFIX
            and param[6] == LEGACY_MULTIBYTE_COMMAND_PREFIX
        ):
            index = 0x00F0 & int.from_bytes(param[1:3], byteorder="big")
            prefix = TMCCPrefixEnum.by_value(index)
            if prefix == TMCCPrefixEnum.PARAMETER:
                from .param_command_req import ParameterCommandReq  # noqa: E402

                return ParameterCommandReq.from_bytes(param)
            elif prefix == TMCCPrefixEnum.R4LC:
                from .r4lc_command_req import R4LCCommandReq  # noqa: E402

                return R4LCCommandReq.from_bytes(param)
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
    def as_bytes(self) -> bytes:
        return (
            TMCC2_SCOPE_TO_FIRST_BYTE_MAP[self.scope].to_bytes(1, byteorder="big")
            + self._word_1
            + LEGACY_MULTIBYTE_COMMAND_PREFIX.to_bytes(1, byteorder="big")
            + self._word_2
            + LEGACY_MULTIBYTE_COMMAND_PREFIX.to_bytes(1, byteorder="big")
            + self._word_3
        )

    @property
    def _word_2_3_prefix(self) -> bytes:
        e_t = 1 if self.scope == CommandScope.TRAIN else 0
        return ((self.address << 1) + e_t).to_bytes(1, "big")

    @property
    def _word_1(self) -> bytes:
        print(self._command_def_enum.as_bytes.hex(":"))
        return ((self.address << 1) + 1).to_bytes(1, "big") + self._command_def_enum.as_bytes

    @property
    def _word_2(self) -> bytes:
        return self._word_2_3_prefix + self.data_byte

    @property
    def _word_3(self) -> bytes:
        return self._word_2_3_prefix + self._checksum()

    def _checksum(self) -> bytes:
        """
        Calculate the checksum of a lionel tmcc2 multibyte command. The checksum
        is calculated adding together the second 2 bytes of the parameter index
        and parameter data words, and the 2 byte of the checksum word, and returning
        the 1's complement of that sum mod 256.

        We make use of self.command_scope to determine if the command directed at
        an engine or train.
        """
        cmd_bytes = self._word_1 + self._word_2 + self._word_2_3_prefix
        byte_sum = 0
        for b in cmd_bytes:
            byte_sum += int(b)
        return (~(byte_sum % 256) & 0xFF).to_bytes(1, byteorder="big")  # return 1's complement of sum mod 256

    def _apply_address(self, **kwargs) -> int:
        return self.command_def.bits

    def _apply_data(self, **kwargs) -> int:
        return self.command_def.bits

    @property
    @abstractmethod
    def data_byte(self) -> bytes:
        pass
