from __future__ import annotations

from .sequence_req import SequenceReq, T
from ..constants import CommandScope
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandDef
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandDef
from ...db.component_state_store import ComponentStateStore


class RampedSpeedReq(SequenceReq):
    def __init__(
        self,
        address: int,
        speed: int | str | T = None,
        scope: CommandScope = CommandScope.ENGINE,
        dialog: bool = False,
        is_tmcc: bool = False,
    ) -> None:
        super().__init__(address, scope)
        tower, s, speed_req, engr = self.decode_rr_speed(speed, is_tmcc)
        # if an integer speed was provided, use it, otherwise, rely on rr speed
        # # provided by decode call; only do this if dialogs are NOT requested
        if isinstance(speed, int) and dialog is False:
            speed_req = speed
        speed_enum = TMCC2EngineCommandDef.ABSOLUTE_SPEED if s.is_tmcc2 else TMCC1EngineCommandDef.ABSOLUTE_SPEED
        # get current state record
        cur_state = ComponentStateStore.get_state(scope, address, create=False)
        # if there is no state information, treat this as an ABSOLUTE_SPEED req
        if cur_state is None or cur_state.speed is None:
            if dialog is True:
                from src.protocol.sequence.speed_req import SpeedReq

                sr = SpeedReq(address, speed, scope, is_tmcc)
                for request in sr.requests:
                    self.add(request.request, delay=request.delay, repeat=request.repeat)
            else:
                self.add(speed_enum, address, speed_req, scope)
        else:
            # issue tower dialog, if requested
            if dialog is True:
                self.add(tower, address, scope=scope)
            # use current speed and momentum to build up or down speed
            cs = cur_state.speed
            delay = 0.0
            inc = 3
            if cur_state.momentum is not None:
                delay_inc = 0.200 + (cur_state.momentum * 0.010)
                inc = 2 if cur_state.momentum >= 6 else inc
                inc = 1 if cur_state.momentum >= 7 else inc
            else:
                delay_inc = 0.200
            # are we speeding up or down?
            ramp = range(cs + inc, speed_req + 1, inc) if cs < speed_req else range(cs - inc, speed_req + 1, -inc)
            for speed in ramp:
                self.add(speed_enum, address, speed, scope, delay=delay)
                delay += delay_inc
            # make sure the final speed is requested
            if ramp[-1] != speed_req:
                self.add(speed_enum, address, speed_req, scope, delay=delay)
            # issue engineer dialog, if requested
            if dialog is True:
                self.add(engr, address, scope=scope, delay=delay)


class RampedSpeedDialogReq(RampedSpeedReq):
    def __init__(
        self,
        address: int,
        speed: int | str | T = None,
        scope: CommandScope = CommandScope.ENGINE,
        is_tmcc: bool = False,
    ) -> None:
        super().__init__(address, speed, scope, dialog=True, is_tmcc=is_tmcc)
