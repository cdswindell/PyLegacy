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
    def from_bytes(cls, param: bytes, from_tmcc_rx: bool = False, is_tmcc4: bool = False) -> Self:
        is_pc, is_d4 = cls.vet_bytes(param, "Parameter")
        if is_pc is True:
            index = 0x00FF & int.from_bytes(param[1:3], byteorder="big")
            try:
                pi = TMCC2ParameterIndex(index)
            except ValueError:
                raise ValueError(f"Invalid parameter command: : {param.hex(':')}")
            if pi in PARAMETER_INDEX_TO_ENUM_MAP:
                param_enum = PARAMETER_INDEX_TO_ENUM_MAP[pi]
                if is_d4 is False:
                    command = int(param[5])
                else:  # account for 4-digit address encoded after each 3 bytes
                    command = int(param[9])
                cmd_enum = param_enum.by_value(command)
                if cmd_enum is not None:
                    scope = cmd_enum.scope
                    if int(param[0]) == LEGACY_TRAIN_COMMAND_PREFIX:
                        scope = CommandScope.TRAIN
                    # build_req the request and return
                    data = 0
                    p_arg = param[1:3] if is_d4 is False else param[1:7]
                    address = cmd_enum.value.address_from_bytes(p_arg)
                    cmd_req = ParameterCommandReq.build(cmd_enum, address, data, scope)
                    if from_tmcc_rx is True:
                        cmd_req._is_tmcc_rx = True
                    return cmd_req
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
    def index_byte(self) -> bytes:
        # noinspection PyTypeChecker
        return PARAMETER_ENUM_TO_INDEX_MAP[type(self._command_def_enum)].to_bytes(1, byteorder="big")

    @property
    def data_byte(self) -> bytes:
        return self.command_def.bits.to_bytes(1, byteorder="big")
