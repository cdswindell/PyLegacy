from __future__ import annotations

from typing import Dict, Type

from .abs_speed_rpm import AbsoluteSpeedRpm
from .grade_crossing_req import GradeCrossingReq
from .labor_effect import LaborEffectUpReq, LaborEffectDownReq
from .ramped_speed_req import RampedSpeedReq, RampedSpeedDialogReq
from .speed_req import SpeedReq

from ..command_def import CommandDefEnum
from ..constants import CommandScope, CommandSyntax
from ..tmcc2.tmcc2_constants import TMCC2CommandDef


class SequenceDef(TMCC2CommandDef):
    from .sequence_req import SequenceReq

    def __init__(
        self,
        command_bits: int,
        scope: CommandScope = CommandScope.ENGINE,
        is_addressable: bool = True,
        d_min: int = 0,
        d_max: int = 0,
        d_map: Dict[int, int] = None,
        cmd_class: Type[SequenceReq] = None,
    ) -> None:
        super().__init__(
            command_bits,
            scope=scope,
            is_addressable=is_addressable,
            d_min=d_min,
            d_max=d_max,
            d_map=d_map,
        )
        self._cmd_class = cmd_class

    def cmd_class(self) -> Type[SequenceReq]:
        return self._cmd_class

    @property
    def scope(self) -> CommandScope | None:
        return CommandScope.SYSTEM

    @property
    def syntax(self) -> CommandSyntax:
        return CommandSyntax.LEGACY

    @property
    def is_tmcc1(self) -> bool:
        return self.syntax == CommandSyntax.TMCC

    @property
    def is_tmcc2(self) -> bool:
        return self.syntax == CommandSyntax.LEGACY

    @property
    def first_byte(self) -> bytes | None:
        raise NotImplementedError

    @property
    def address_mask(self) -> bytes | None:
        raise NotImplementedError


class SequenceCommandEnum(CommandDefEnum):
    SYSTEM = SequenceDef(0x00)
    ABSOLUTE_SPEED_SEQ = SequenceDef(1, d_max=199, cmd_class=SpeedReq)
    RAMPED_SPEED_SEQ = SequenceDef(2, d_max=199, cmd_class=RampedSpeedReq)
    RAMPED_SPEED_DIALOG_SEQ = SequenceDef(3, d_max=199, cmd_class=RampedSpeedDialogReq)
    GRADE_CROSSING_SEQ = SequenceDef(4, cmd_class=GradeCrossingReq)
    LABOR_EFFECT_DOWN_SEQ = SequenceDef(5, cmd_class=LaborEffectDownReq)
    LABOR_EFFECT_UP_SEQ = SequenceDef(5, cmd_class=LaborEffectUpReq)
    ABSOLUTE_SPEED_RPM = SequenceDef(6, d_max=199, cmd_class=AbsoluteSpeedRpm)
