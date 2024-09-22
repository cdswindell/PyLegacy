from typing import Dict, Self

from src.protocol.command_req import CommandReq
from src.protocol.constants import DEFAULT_ADDRESS, CommandScope
from src.protocol.tmcc2.tmcc2_constants import TMCC2_SCOPE_TO_FIRST_BYTE_MAP, LEGACY_PARAMETER_COMMAND_PREFIX
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2ParameterEnum, TMCC2ParameterIndex
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2_PARAMETER_INDEX_PREFIX, TMCC2ParameterCommandDef
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2RailSoundsDialogControl
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2RailSoundsEffectsControl, TMCC2EffectsControl
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2LightingControl

# noinspection PyTypeChecker
TMCC2_PARAMETER_ENUM_TO_TMCC2_PARAMETER_INDEX_MAP: Dict[TMCC2ParameterEnum, TMCC2ParameterIndex] = {
    TMCC2RailSoundsDialogControl: TMCC2ParameterIndex.DIALOG_TRIGGERS,
    TMCC2RailSoundsEffectsControl: TMCC2ParameterIndex.EFFECTS_TRIGGERS,
    TMCC2EffectsControl: TMCC2ParameterIndex.EFFECTS_CONTROLS,
    TMCC2LightingControl: TMCC2ParameterIndex.LIGHTING_CONTROLS,
}


class ParameterCommandReq(CommandReq):
    @classmethod
    def build(cls,
              command: TMCC2ParameterEnum,
              address: int = DEFAULT_ADDRESS,
              data: int = 0,
              scope: CommandScope = None) -> Self:
        return ParameterCommandReq(command, address, data, scope)

    def __init__(self,
                 command_def_enum: TMCC2ParameterEnum,
                 address: int = DEFAULT_ADDRESS,
                 data: int = 0,
                 scope: CommandScope = None) -> None:
        super().__init__(command_def_enum, address, data, scope)

    @property
    def parameter_index(self) -> TMCC2ParameterIndex:
        # noinspection PyTypeChecker
        return TMCC2_PARAMETER_ENUM_TO_TMCC2_PARAMETER_INDEX_MAP[type(self._command_def_enum)]

    @property
    def parameter_index_byte(self) -> bytes:
        return (TMCC2_PARAMETER_INDEX_PREFIX | self.parameter_index).to_bytes(1, byteorder='big')

    @property
    def parameter_data(self) -> TMCC2ParameterCommandDef:
        return TMCC2ParameterCommandDef(self._command_def)

    @property
    def parameter_data_byte(self) -> bytes:
        return self.command_def.bits.to_bytes(1, byteorder='big')

    @property
    def as_bytes(self) -> bytes:
        return (TMCC2_SCOPE_TO_FIRST_BYTE_MAP[self.scope].to_bytes(1, byteorder='big') +
                self._word_1 +
                LEGACY_PARAMETER_COMMAND_PREFIX.to_bytes(1, byteorder='big') +
                self._word_2 +
                LEGACY_PARAMETER_COMMAND_PREFIX.to_bytes(1, byteorder='big') +
                self._word_3)

    @property
    def _word_2_3_prefix(self) -> bytes:
        e_t = 1 if self.scope == CommandScope.TRAIN else 0
        return ((self.address << 1) + e_t).to_bytes(1, 'big')

    @property
    def _word_1(self) -> bytes:
        return ((self.address << 1) + 1).to_bytes(1, 'big') + self.parameter_index_byte

    @property
    def _word_2(self) -> bytes:
        return self._word_2_3_prefix + self.parameter_data_byte

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
        return (~(byte_sum % 256) & 0xFF).to_bytes(1, byteorder='big')  # return 1's complement of sum mod 256

    def _apply_address(self, **kwargs) -> int:
        return self.command_def.bits

    def _apply_data(self, **kwargs) -> int:
        return self.command_def.bits
