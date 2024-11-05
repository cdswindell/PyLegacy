from __future__ import annotations

from .sequence_req import SequenceReq, T
from ..constants import CommandScope
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandDef
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandDef
from ...db.component_state_store import ComponentStateStore


class RealisticSpeedReq(SequenceReq):
    def __init__(
        self,
        address: int,
        speed: int | str | T = None,
        scope: CommandScope = CommandScope.ENGINE,
        is_tmcc: bool = False,
    ) -> None:
        super().__init__(address, scope)
        tower, s, speed_req, engr = self.decode_rr_speed(speed, is_tmcc)
        # if an integer speed was provided, use it, otherwise, rely on rr speed
        # # provided by decode call
        if isinstance(speed, int):
            speed_req = speed
        speed_enum = TMCC2EngineCommandDef.ABSOLUTE_SPEED if s.is_tmcc2 else TMCC1EngineCommandDef.ABSOLUTE_SPEED
        # get current state record
        cur_state = ComponentStateStore.get_state(scope, address, create=False)
        # if there is no state information, treat this as an ABSOLUTE_SPEED req
        if cur_state is None or cur_state.speed is None:
            self.add(speed_enum, address, speed_req, scope)
        else:
            # use current speed and momentum to build up or down speed
            cs = cur_state.speed
            # are we speeding up or down?
            ramp = range(cs + 3, speed_req + 1, 3) if cs < speed_req else range(cs - 3, speed_req + 1, -3)
            delay = 0.0
            momentum_factor = 1
            for speed in ramp:
                self.add(speed_enum, address, speed, scope, delay=delay)
                delay += 0.2 * momentum_factor
            # make sure the final speed is requested
            if ramp[-1] != speed_req:
                self.add(speed_enum, address, speed_req, scope, delay=delay)
