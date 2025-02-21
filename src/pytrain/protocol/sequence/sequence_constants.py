from __future__ import annotations

from typing import Dict, TypeVar

from ..command_def import CommandDefEnum
from ..constants import CommandScope, CommandSyntax
from ..tmcc2.tmcc2_constants import TMCC2CommandDef

S = TypeVar("S", bound="SequenceDef")


class SequenceDef(TMCC2CommandDef):
    def __init__(
        self,
        command_bits: int,
        scope: CommandScope = CommandScope.ENGINE,
        is_addressable: bool = True,
        d_min: int = 0,
        d_max: int = 0,
        d_map: Dict[int, int] = None,
        interval: int = None,
        cmd_class: S = None,
    ) -> None:
        super().__init__(
            command_bits,
            scope=scope,
            is_addressable=is_addressable,
            d_min=d_min,
            d_max=d_max,
            d_map=d_map,
            interval=interval,
        )
        self._cmd_class = cmd_class

    @property
    def cmd_class(self) -> S:
        return self._cmd_class

    def register_cmd_class(self, cmd_class: S) -> None:
        if self._cmd_class is None:
            self._cmd_class = cmd_class

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
    ABSOLUTE_SPEED_SEQ = SequenceDef(1, d_max=199)
    RAMPED_SPEED_SEQ = SequenceDef(2, d_max=199)
    RAMPED_SPEED_DIALOG_SEQ = SequenceDef(3, d_max=199)
    GRADE_CROSSING_SEQ = SequenceDef(4)
    LABOR_EFFECT_DOWN_SEQ = SequenceDef(5)
    LABOR_EFFECT_UP_SEQ = SequenceDef(6)
    ABSOLUTE_SPEED_RPM = SequenceDef(7, d_max=199)
