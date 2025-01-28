from __future__ import annotations

from .sequence_req import SequenceReq
from ..command_req import CommandReq
from ..constants import CommandScope
from ..sequence.sequence_constants import SequenceCommandEnum
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


class GradeCrossingReq(SequenceReq):
    def __init__(self, address: int, data: int, scope: CommandScope = CommandScope.ENGINE) -> None:
        super().__init__(SequenceCommandEnum.GRADE_CROSSING_SEQ, address, scope)
        self._data = data
        req15 = CommandReq(TMCC2EngineCommandEnum.QUILLING_HORN, address, 15, scope)
        req8 = CommandReq(TMCC2EngineCommandEnum.QUILLING_HORN, address, 8, scope)
        req4 = CommandReq(TMCC2EngineCommandEnum.QUILLING_HORN, address, 4, scope)
        req0 = CommandReq(TMCC2EngineCommandEnum.QUILLING_HORN, address, 0, scope)
        # first blast
        for _ in range(5):
            self.add(req15)
        self.add(req0)
        self.add(req8)

        # second blast
        delay = 1.1
        for _ in range(4):
            self.add(req8, delay=delay)
        self.add(req0, delay=delay)
        for _ in range(2):
            self.add(req8, delay=delay)

        # third blast
        delay += 1.1
        self.add(req8, delay=delay)
        self.add(req0, delay=delay)
        for _ in range(6):
            self.add(req15, delay=delay)

        # fourth blast
        delay += 1.05
        for _ in range(6):
            self.add(req15, delay=delay)
        for _ in range(3):
            self.add(req4, delay=delay)
        self.add(req0, delay=delay)
