from __future__ import annotations

from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq
from ..constants import CommandScope, DEFAULT_ADDRESS
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm


class AbsoluteSpeedRpm(SequenceReq):
    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
        data: int = 0,
    ) -> None:
        super().__init__(SequenceCommandEnum.ABSOLUTE_SPEED_RPM, address, scope)
        self._scope = scope
        self._data = data
        self._state = None
        self.add(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, data=data, scope=CommandScope.ENGINE)
        rpm = tmcc2_speed_to_rpm(data)
        self.add(TMCC2EngineCommandEnum.DIESEL_RPM, data=rpm, scope=CommandScope.ENGINE)

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
        from ...db.component_state_store import ComponentStateStore

        state = ComponentStateStore.get_state(self.scope, self.address, create=False)
        if state:
            new_speed = min(state.speed_max, self.data)
            self._data = new_speed
        else:
            new_speed = self.data

        for req_wrapper in self._requests:
            req = req_wrapper.request
            if req.command == TMCC2EngineCommandEnum.DIESEL_RPM:
                req.data = tmcc2_speed_to_rpm(new_speed)
            elif req.command == TMCC2EngineCommandEnum.ABSOLUTE_SPEED:
                req.data = new_speed
        return 0


SequenceCommandEnum.ABSOLUTE_SPEED_RPM.value.register_cmd_class(AbsoluteSpeedRpm)
