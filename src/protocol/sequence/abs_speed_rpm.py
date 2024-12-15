from __future__ import annotations


from .sequence_req import SequenceReq
from ..constants import CommandScope
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandDef, tmcc2_speed_to_rpm


class AbsoluteSpeedRpm(SequenceReq):
    def __init__(
        self,
        address: int,
        scope: CommandScope = CommandScope.ENGINE,
        data: int = 0,
        inc: int = 0,
    ) -> None:
        super().__init__(address, scope)
        self._inc = inc
        self._scope = scope
        self._data = data
        self._state = None
        self.add(TMCC2EngineCommandDef.ABSOLUTE_SPEED, scope=CommandScope.ENGINE)
        self.add(TMCC2EngineCommandDef.DIESEL_RPM, scope=CommandScope.ENGINE)

    @property
    def scope(self) -> CommandScope | None:
        return self._scope

    @scope.setter
    def scope(self, new_scope: CommandScope) -> None:
        if new_scope != self._scope:
            # can only change scope for Engine and Train commands, and then, just from the one to the other
            if self._scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                if new_scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                    self._scope = new_scope
                    self._apply_scope()
                    return
            raise AttributeError(f"Scope {new_scope} not supported for {self}")

    def _apply_data(self, new_data: int = None) -> int:
        for req_wrapper in self._requests:
            req = req_wrapper.request
            if req.command == TMCC2EngineCommandDef.ABSOLUTE_SPEED:
                req.data = self.data
            elif req.command == TMCC2EngineCommandDef.DIESEL_RPM:
                req.data = tmcc2_speed_to_rpm(self.data)
        return 0
