from __future__ import annotations

from ..constants import CommandScope
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm
from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq, T


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
        if not is_tmcc:
            rpm = tmcc2_speed_to_rpm(sp)
            self.add(TMCC2EngineCommandEnum.DIESEL_RPM, address, data=rpm, scope=scope, delay=4)
        self.add(e, address, scope=scope, delay=6)


SequenceCommandEnum.ABSOLUTE_SPEED_SEQ.value.register_cmd_class(SpeedReq)
