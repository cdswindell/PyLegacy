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
        self._state = ComponentStateStore.get_state(self.scope, self.address, False)
        self.add(TMCC2EngineCommandDef.ENGINE_LABOR, address, scope=scope)

    @property
    def scope(self) -> CommandScope | None:
        return self._scope

    def _recalculate(self):
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
