#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from ...db.comp_data import CompData
from ..constants import DEFAULT_ADDRESS, CommandScope
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm
from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq


class SetSpeedReq(SequenceReq):
    """Request to set the speed of a Lionel Legacy engine or train."""

    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(SequenceCommandEnum.SET_SPEED_RPM, address, scope)
        self._target_speed = data
        self.add(CompData.generate_update_req("target_speed", data, self.state))
        if address == DEFAULT_ADDRESS:
            self.add(TMCC1EngineCommandEnum.ABSOLUTE_SPEED, address, data, scope)
            self.add(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, address, data, scope)
        else:
            speed_enum = (
                TMCC1EngineCommandEnum.ABSOLUTE_SPEED if self.is_tmcc1 else TMCC2EngineCommandEnum.ABSOLUTE_SPEED
            )
            self.add(speed_enum, address, data, scope)

        if address == DEFAULT_ADDRESS or self.is_tmcc2:
            rpm = tmcc2_speed_to_rpm(data)
            self.add(TMCC2EngineCommandEnum.DIESEL_RPM, address, data=rpm, scope=scope, delay=0.2)

    def _apply_data(self, new_data: int = None) -> int:
        if self.state:
            new_speed = min(self.state.speed_max, self.data)
            self._data = new_speed
        else:
            new_speed = self.data

        for req_wrapper in self._requests:
            req = req_wrapper.request
            if req.command == TMCC2EngineCommandEnum.DIESEL_RPM:
                req.data = tmcc2_speed_to_rpm(new_speed)
            elif req.command in {TMCC1EngineCommandEnum.ABSOLUTE_SPEED, TMCC2EngineCommandEnum.ABSOLUTE_SPEED}:
                req.data = new_speed
        return 0

    def _on_before_send(self) -> None:
        if self.state:
            from ...comm.comm_buffer import CommBuffer
            from .ramped_speed_req import CANCELABLE_REQUESTS

            CommBuffer.cancel_delayed_requests(self.state, requests=CANCELABLE_REQUESTS)
            self.state.comp_data.target_speed = self._target_speed
            self.state.is_ramping = False


SequenceCommandEnum.SET_SPEED_RPM.value.register_cmd_class(SetSpeedReq)
