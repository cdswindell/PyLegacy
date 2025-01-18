from __future__ import annotations

from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq, T
from ..constants import CommandScope
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm


class SpeedReq(SequenceReq):
    def __init__(
        self,
        address: int,
        speed: int | str | T = None,
        scope: CommandScope = CommandScope.ENGINE,
        is_tmcc: bool = False,
    ) -> None:
        super().__init__(SequenceCommandEnum.ABSOLUTE_SPEED_SEQ, address, scope)
        t, s, sp, e = self.decode_rr_speed(speed, is_tmcc)
        self.add(t, address, scope=scope)
        self.add(s, address, scope=scope, delay=3)
        if is_tmcc is False:
            rpm = tmcc2_speed_to_rpm(sp)
            self.add(TMCC2EngineCommandEnum.DIESEL_RPM, address, data=rpm, scope=scope, delay=4)
        self.add(e, address, scope=scope, delay=6)
