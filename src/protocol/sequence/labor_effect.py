from __future__ import annotations

import abc
from abc import ABC

from .sequence_req import SequenceReq
from ..constants import CommandScope, DEFAULT_ADDRESS
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandDef
from ...db.component_state_store import ComponentStateStore


class LaborEffect(SequenceReq, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        address: int,
        scope: CommandScope = CommandScope.ENGINE,
        inc: int = 0,
    ) -> None:
        super().__init__(address, scope)
        self._inc = inc
        self._scope = scope
        self._state = None
        self.add(TMCC2EngineCommandDef.ENGINE_LABOR, address, scope=scope)

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
        labor = self._state.labor + self._inc
        labor = min(max(labor, 0), 31)
        for req in self._requests:
            req.data = labor


class LaborEffectUpReq(LaborEffect):
    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(address, scope, 1)


class LaborEffectDownReq(LaborEffect):
    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(address, scope, -1)
