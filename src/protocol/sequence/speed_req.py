from __future__ import annotations

from .sequence_req import SequenceReq, T
from ..constants import CommandScope


class SpeedReq(SequenceReq):
    def __init__(
        self,
        address: int,
        speed: int | str | T = None,
        scope: CommandScope = CommandScope.ENGINE,
        is_tmcc: bool = False,
    ) -> None:
        super().__init__(address, scope)
        t, s, _, e = self.decode_rr_speed(speed, is_tmcc)
        self.add(t, address)
        self.add(s, address, scope=scope, delay=3)
        self.add(e, address, scope=scope, delay=6)
