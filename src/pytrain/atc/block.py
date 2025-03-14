#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

from gpiozero import Button

from ..db.component_state import IrdaState, EngineState, TrainState
from ..db.component_state_store import ComponentStateStore
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


class Block:
    def __init__(
        self,
        block_name: str,
        block_id: int,
        sensor_track_id: int,
        occupancy_pin: int | str,
        slow_pin: int | str,
        stop_pin: int | str,
    ) -> None:
        self._block_name = block_name
        self._block_id = block_id
        if sensor_track_id:
            self._sensor_track: IrdaState = ComponentStateStore.get_state(CommandScope.IRDA, sensor_track_id)
            self.sensor_track.block = self
        else:
            # noinspection PyTypeChecker
            self._sensor_track = None
        self._occupancy_btn = Button(occupancy_pin)
        self._slow_btn = Button(slow_pin)
        self._stop_btn = Button(stop_pin)
        self._prev_block: Block | None = None
        self._next_block: Block | None = None
        self._current_motive: EngineState | TrainState | None = None
        self._original_speed: int | None = None

        # add handlers for state change
        self._slow_btn.when_activated = self.signal_slowdown
        self._stop_btn.when_activated = self.signal_stop_immediate
        self._stop_btn.when_deactivated = self.block_clear

    def __call__(self, *args, **kwargs) -> None:
        print(f"{self.sensor_track}")
        # called from ComponentState when engine/train passes sensor
        if self.sensor_track.is_train:
            self._current_motive = ComponentStateStore.get_state(CommandScope.TRAIN, self.sensor_track.last_train_id)
        else:
            self._current_motive = ComponentStateStore.get_state(CommandScope.ENGINE, self.sensor_track.last_engine_id)

    @property
    def block_name(self) -> str:
        return self._block_name

    @property
    def block_id(self) -> int:
        return self._block_id

    @property
    def sensor_track(self) -> IrdaState:
        return self._sensor_track

    @property
    def is_occupied(self) -> bool:
        return self._occupancy_btn.is_active or self._slow_btn.is_active or self._stop_btn.is_active

    def next_block_clear(self, signaling_block: Block) -> None:
        from ..protocol.sequence.ramped_speed_req import RampedSpeedReq

        # resume original speed
        if self._current_motive and self._original_speed and signaling_block.is_occupied is False:
            scope = self._current_motive.scope
            tmcc_id = self._current_motive.tmcc_id
            is_tmcc = self._current_motive.is_tmcc
            req = RampedSpeedReq(tmcc_id, self._original_speed, scope, is_tmcc)
            req.send()

    def signal_slowdown(self) -> None:
        from ..protocol.sequence.ramped_speed_req import RampedSpeedReq

        if self.is_occupied is True and self._current_motive:
            self._original_speed = self._current_motive.speed
            scope = self._current_motive.scope
            tmcc_id = self._current_motive.tmcc_id
            is_tmcc = self._current_motive.is_tmcc
            req = RampedSpeedReq(tmcc_id, "restricted", scope, is_tmcc)
            req.send()
        else:
            self._current_motive = None

    def signal_stop_immediate(self) -> None:
        if self._current_motive and self._original_speed:
            scope = self._current_motive.scope
            tmcc_id = self._current_motive.tmcc_id
            if self._current_motive.is_tmcc is True:
                req = CommandReq(TMCC1EngineCommandEnum.STOP_IMMEDIATE, tmcc_id, scope=scope)
            else:
                req = CommandReq(TMCC2EngineCommandEnum.STOP_IMMEDIATE, tmcc_id, scope=scope)
            req.send()

    def block_clear(self) -> None:
        self._original_speed = None
        self._current_motive = None
        if self._prev_block and self.is_occupied is False:
            self._prev_block.next_block_clear(self)
