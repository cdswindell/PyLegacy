from __future__ import annotations


import sys

from .multibyte_command_req import MultiByteReq
from .multibyte_constants import TMCC2R4LCIndex, TMCC2R4LCEnum, UnitAssignment

if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from ..constants import DEFAULT_ADDRESS, CommandScope
from ..tmcc2.tmcc2_constants import LEGACY_MULTIBYTE_COMMAND_PREFIX
from ..tmcc2.tmcc2_constants import LEGACY_TRAIN_COMMAND_PREFIX

"""
Commands to modify R4LC EEPROM
"""


class R4LCCommandReq(MultiByteReq):
    @classmethod
    def build(
        cls, command: TMCC2R4LCEnum, address: int = DEFAULT_ADDRESS, data: int = 0, scope: CommandScope = None
    ) -> Self:
        return R4LCCommandReq(command, address, data, scope)

    @classmethod
    def from_bytes(cls, param: bytes, from_tmcc_rx: bool = False, is_tmcc4: bool = False) -> Self:
        if not param:
            raise ValueError("Command requires at least 9 bytes")
        if len(param) < 9:
            raise ValueError(f"R4LC command requires at least 9 bytes {param.hex(':')}")
        if (
            len(param) == 9
            and param[3] == LEGACY_MULTIBYTE_COMMAND_PREFIX
            and param[6] == LEGACY_MULTIBYTE_COMMAND_PREFIX
        ):
            index = 0x00FF & int.from_bytes(param[1:3], byteorder="big")
            try:
                pi = TMCC2R4LCIndex(index)
            except ValueError:
                raise ValueError(f"Invalid R4LC command: : {param.hex(':')}")
            cmd_enum = TMCC2R4LCEnum(pi.name)
            data = int(param[5])
            scope = CommandScope.ENGINE
            if int(param[0]) == LEGACY_TRAIN_COMMAND_PREFIX:
                scope = CommandScope.TRAIN
            # build_req the request and return
            address = cmd_enum.value.address_from_bytes(param[1:3])
            cmd_req = R4LCCommandReq.build(cmd_enum, address, data, scope)
            if from_tmcc_rx is True:
                cmd_req._is_tmcc_rx = True
            return cmd_req
        raise ValueError(f"Invalid R4LC command: : {param.hex(':')}")

    def __init__(
        self,
        command_def_enum: TMCC2R4LCEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
    ) -> None:
        super().__init__(command_def_enum, address, data, scope)

    def __repr__(self) -> str:
        if self.command == TMCC2R4LCEnum.TRAIN_UNIT:
            data = UnitAssignment.by_value(self._data)
            if data is not None:
                return f"[{self.scope.name} {self.address} {self.command_name} {data.name} (0x{self.as_bytes.hex()})]"
        return super().__repr__()

    @property
    def index_byte(self) -> bytes:
        return self.command_def.bits.to_bytes(1, byteorder="big")

    @property
    def data_byte(self) -> bytes:
        return (0x00).to_bytes(1, byteorder="big")
