from __future__ import annotations

from abc import ABC

from .ramp_speed_req import RampSpeedReqBase
from .sequence_constants import SequenceCommandEnum
from .sequence_req import T
from ..constants import CommandScope
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

CANCELABLE_REQUESTS = {
    TMCC1EngineCommandEnum.ABSOLUTE_SPEED,
    TMCC2EngineCommandEnum.ABSOLUTE_SPEED,
    TMCC2EngineCommandEnum.ENGINE_LABOR,
    TMCC2EngineCommandEnum.DIESEL_RPM,
    SequenceCommandEnum.RAMPED_SPEED_SEQ,
    SequenceCommandEnum.SET_SPEED_RPM,
}


def labor_delta(cur_speed: int, new_speed: int, cur_labor: int) -> int:
    delta = new_speed - cur_speed
    if delta > 0:
        return min(31, max(0, round((delta * 0.09546) - 0.5401)) + cur_labor)
    elif delta < 0:
        return max(0, cur_labor - max(0, round((-0.06030 * delta) + 0.01052)))
    else:
        return cur_labor


class RampedSpeedReqBase(RampSpeedReqBase, ABC):
    """Legacy sequence identifiers use the same exclusive local ramp as new requests."""


class RampedSpeedReq(RampedSpeedReqBase):
    def __init__(
        self,
        address: int,
        speed: int | str | T,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(SequenceCommandEnum.RAMPED_SPEED_SEQ, address, speed, scope)


SequenceCommandEnum.RAMPED_SPEED_SEQ.value.register_cmd_class(RampedSpeedReq)


class RampedSpeedDialogReq(RampedSpeedReqBase):
    def __init__(
        self,
        address: int,
        speed: int | str | T,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(
            SequenceCommandEnum.RAMPED_SPEED_DIALOG_SEQ,
            address,
            speed,
            scope,
            dialog=True,
        )


SequenceCommandEnum.RAMPED_SPEED_DIALOG_SEQ.value.register_cmd_class(RampedSpeedDialogReq)
