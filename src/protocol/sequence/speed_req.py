from __future__ import annotations

import argparse

from .sequence_req import SequenceReq, T
from ..constants import CommandScope, OfficialRRSpeeds
from ..tmcc1.tmcc1_constants import TMCC1RRSpeeds, TMCC1EngineCommandDef
from src.protocol.multybyte.multibyte_constants import TMCC2RailSoundsDialogControl
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandDef, TMCC2RRSpeeds


class SpeedReq(SequenceReq):
    def __init__(
        self,
        address: int,
        speed: int | str | T = None,
        scope: CommandScope = CommandScope.ENGINE,
        is_tmcc: bool = False,
    ) -> None:
        super().__init__(address, scope)
        t, s, e = self._decode_speed(speed, is_tmcc)
        self.add(t, address)
        self.add(s, address, scope=scope, delay=3)
        self.add(e, address, scope=scope, delay=6)

    def _decode_speed(self, speed, is_tmcc):
        base = None
        speed_enum = None
        if isinstance(speed, OfficialRRSpeeds):
            base = f"SPEED_{speed.name}"
            if isinstance(speed, TMCC1RRSpeeds):
                speed_enum = TMCC1EngineCommandDef.by_name(base)
            else:
                speed_enum = TMCC2EngineCommandDef.by_name(base)
            if speed_enum is None:
                raise ValueError(f"Unknown speed type: {speed}")
        elif isinstance(speed, int):
            if is_tmcc:
                for rr_speed in TMCC1RRSpeeds:
                    if speed in rr_speed.value:
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC1EngineCommandDef.by_name(base)
                        break
            else:
                for rr_speed in TMCC2RRSpeeds:
                    if speed in rr_speed.value:
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC2EngineCommandDef.by_name(base)
                        break
        elif isinstance(speed, str):
            try:
                args = self._speed_parser().parse_args(["-" + speed.strip()])
                speed_enum = args.command
                base = speed_enum.name
            except argparse.ArgumentError:
                pass
        if speed_enum is None:
            raise ValueError(f"Unknown speed type: {speed}")

        tower = TMCC2RailSoundsDialogControl.by_name(f"TOWER_{base}")
        engr = TMCC2RailSoundsDialogControl.by_name(f"ENGINEER_{base}")
        return tower, speed_enum, engr
