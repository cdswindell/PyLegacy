from __future__ import annotations

from typing import Dict

import sys

from .multibyte_command_req import MultiByteReq
from .multibyte_constants import TMCC2MaskingControl, TMCC2ParameterEnum

if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from ..constants import DEFAULT_ADDRESS, CommandScope
from ..tmcc2.tmcc2_constants import TMCC2_SCOPE_TO_FIRST_BYTE_MAP, LEGACY_MULTIBYTE_COMMAND_PREFIX
from ..tmcc2.tmcc2_constants import LEGACY_TRAIN_COMMAND_PREFIX
from .multibyte_constants import TMCC2ParameterIndex
from .multibyte_constants import TMCC2RailSoundsDialogControl
from .multibyte_constants import TMCC2RailSoundsEffectsControl, TMCC2EffectsControl
from .multibyte_constants import TMCC2LightingControl


# noinspection PyTypeChecker
PARAMETER_ENUM_TO_INDEX_MAP: Dict[TMCC2ParameterEnum, TMCC2ParameterIndex] = {
    TMCC2RailSoundsDialogControl: TMCC2ParameterIndex.DIALOG_TRIGGERS,
    TMCC2RailSoundsEffectsControl: TMCC2ParameterIndex.EFFECTS_TRIGGERS,
    TMCC2MaskingControl: TMCC2ParameterIndex.MASKING_CONTROLS,
    TMCC2EffectsControl: TMCC2ParameterIndex.EFFECTS_CONTROLS,
    TMCC2LightingControl: TMCC2ParameterIndex.LIGHTING_CONTROLS,
}

PARAMETER_INDEX_TO_ENUM_MAP = {s: p for p, s in PARAMETER_ENUM_TO_INDEX_MAP.items()}


class ParameterCommandReq(MultiByteReq):
    @classmethod
    def build(
        cls, command: TMCC2ParameterEnum, address: int = DEFAULT_ADDRESS, data: int = 0, scope: CommandScope = None
    ) -> Self:
        return ParameterCommandReq(command, address, data, scope)

    @classmethod
    def from_bytes(cls, param: bytes) -> Self:
        if not param:
            raise ValueError("Command requires at least 9 bytes")
        if len(param) < 9:
            raise ValueError(f"Parameter command requires at least 9 bytes {param.hex(':')}")
        if (
            len(param) == 9
            and param[3] == LEGACY_MULTIBYTE_COMMAND_PREFIX
            and param[6] == LEGACY_MULTIBYTE_COMMAND_PREFIX
        ):
            index = 0x00FF & int.from_bytes(param[1:3], byteorder="big")
            try:
                pi = TMCC2ParameterIndex(index)
            except ValueError:
                raise ValueError(f"Invalid parameter command: : {param.hex(':')}")
            if pi in PARAMETER_INDEX_TO_ENUM_MAP:
                param_enum = PARAMETER_INDEX_TO_ENUM_MAP[pi]
                command = int(param[5])
                cmd_enum = param_enum.by_value(command)
                if cmd_enum is not None:
                    scope = cmd_enum.scope
                    if int(param[0]) == LEGACY_TRAIN_COMMAND_PREFIX:
                        scope = CommandScope.TRAIN
                    # build_req the request and return
                    data = 0
                    address = cmd_enum.value.address_from_bytes(param[1:3])
                    return ParameterCommandReq.build(cmd_enum, address, data, scope)
        raise ValueError(f"Invalid parameter command: : {param.hex(':')}")

    def __init__(
        self,
        command_def_enum: TMCC2ParameterEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
    ) -> None:
        super().__init__(command_def_enum, address, data, scope)

    @property
    def parameter_index(self) -> TMCC2ParameterIndex:
        # noinspection PyTypeChecker
        return PARAMETER_ENUM_TO_INDEX_MAP[type(self._command_def_enum)]

    @property
    def parameter_index_byte(self) -> bytes:
        return self.parameter_index.to_bytes(1, byteorder="big")

    @property
    def data_byte(self) -> bytes:
        return self.command_def.bits.to_bytes(1, byteorder="big")

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
        return ((self.address << 1) + 1).to_bytes(1, "big") + self.parameter_index_byte

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
