#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

from __future__ import annotations

from typing import cast

from ..constants import DEFAULT_ADDRESS, CommandScope
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm
from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq


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
        self.add(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, data=data, scope=scope)
        rpm = tmcc2_speed_to_rpm(data)
        self.add(TMCC2EngineCommandEnum.DIESEL_RPM, data=rpm, scope=scope)

    def _apply_data(self, new_data: int = None) -> int:
        from ...db.component_state_store import ComponentStateStore
        from ...db.engine_state import EngineState

        state = cast(EngineState, ComponentStateStore.get_state(self.scope, self.address, create=False))
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
