from __future__ import annotations

import abc
from abc import ABC

from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq
from ..constants import CommandScope, DEFAULT_ADDRESS
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from ...db.component_state_store import ComponentStateStore


class LaborEffectBase(SequenceReq, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        command: SequenceCommandEnum,
        address: int,
        scope: CommandScope = CommandScope.ENGINE,
        data: int = 0,
        inc: int = 0,
    ) -> None:
        super().__init__(command, address, scope)
        self._inc = inc
        self._scope = scope
        self._data = data
        self._state = None
        self.add(TMCC2EngineCommandEnum.ENGINE_LABOR, scope=CommandScope.ENGINE)

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

    def _recalculate(self):
        self._state = ComponentStateStore.get_state(self.scope, self.address, False)
        if self._state:
            labor = self._state.labor + self._inc
            labor = min(max(labor, 0), 31)
            for req_wrapper in self._requests:
                req = req_wrapper.request
                req.data = labor


class LaborEffectUpReq(LaborEffectBase):
    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(SequenceCommandEnum.LABOR_EFFECT_UP_SEQ, address, scope, data, 1)


SequenceCommandEnum.LABOR_EFFECT_UP_SEQ.value.register_cmd_class(LaborEffectUpReq)


class LaborEffectDownReq(LaborEffectBase):
    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(SequenceCommandEnum.LABOR_EFFECT_DOWN_SEQ, address, scope, data, -1)


SequenceCommandEnum.LABOR_EFFECT_DOWN_SEQ.value.register_cmd_class(LaborEffectDownReq)
