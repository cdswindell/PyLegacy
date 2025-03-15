#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

from threading import Thread

from gpiozero import Button

from ..db.component_state import IrdaState, EngineState, TrainState
from ..db.component_state_store import ComponentStateStore
from ..gpio.gpio_handler import DEFAULT_BOUNCE_TIME
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


class Block(Thread):
    def __init__(
        self,
        block_id: int,
        block_name: str = None,
        sensor_track_id: int = None,
        occupied_pin: int | str = None,
        slow_pin: int | str = None,
        stop_pin: int | str = None,
        left_to_right: bool = True,
    ) -> None:
        self._block_id = block_id
        self._block_name = block_name
        if sensor_track_id:
            self._sensor_track: IrdaState = ComponentStateStore.get_state(CommandScope.IRDA, sensor_track_id)
        else:
            # noinspection PyTypeChecker
            self._sensor_track = None
        self._occupied_btn = Button(occupied_pin, bounce_time=DEFAULT_BOUNCE_TIME) if occupied_pin else None
        self._slow_btn = Button(slow_pin, bounce_time=DEFAULT_BOUNCE_TIME) if slow_pin else None
        self._stop_btn = Button(stop_pin, bounce_time=DEFAULT_BOUNCE_TIME) if stop_pin else None
        self._prev_block: Block | None = None
        self._next_block: Block | None = None
        self._current_motive: EngineState | TrainState | None = None
        self._original_speed: int | None = None
        self._left_to_right = left_to_right if left_to_right is not None else True

        # add handlers for state change
        if self._slow_btn:
            self._slow_btn.when_activated = self.signal_slowdown
        if self._stop_btn:
            self._stop_btn.when_activated = self.signal_stop_immediate
        if self._slow_btn:
            self._stop_btn.when_deactivated = self.block_clear

        # start thread if sensor track specified, we also delay calling super until
        # buttons have been created
        super().__init__(daemon=True, name=f"Block {self.block_id} Occupied: {self.is_occupied}")
        if self.sensor_track:
            self.start()

    def __repr__(self) -> str:
        nm = f" {self.block_name}" if self.block_name else ""
        return f"Block{nm} #{self.block_id} Occupied: {self.is_occupied}"

    def run(self) -> None:
        while self.sensor_track and True:
            self.sensor_track.changed.wait()
            self.sensor_track.changed.clear()
            with self.sensor_track.synchronizer:
                self._cache_motive()

    def __call__(self, *args, **kwargs) -> None:
        self._cache_motive()

    def _cache_motive(self) -> None:
        scope = "Train" if self.sensor_track.is_train else "Engine"
        last_id = self.sensor_track.last_engine_id
        ld = "L -> R" if self.is_left_to_right else "R -> L"
        print(f"{self.sensor_track.tmcc_id} {scope} {last_id} {ld} {self.sensor_track.last_direction}")

        dir_int = 1 if self.is_left_to_right else 0
        if dir_int == self.sensor_track.last_direction:
            if self.sensor_track.is_train is True and self.sensor_track.last_train_id:
                self._current_motive = ComponentStateStore.get_state(
                    CommandScope.TRAIN, self.sensor_track.last_train_id
                )
            elif self.sensor_track.is_engine is True and self.sensor_track.last_engine_id:
                self._current_motive = ComponentStateStore.get_state(
                    CommandScope.ENGINE, self.sensor_track.last_engine_id
                )
            else:
                self._current_motive = None
        else:
            self._current_motive = None
        if self._current_motive:
            self._original_speed = self._current_motive.speed
        else:
            self._original_speed = None

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
        return (
            (self._occupied_btn and self._occupied_btn.is_active)
            or (self._slow_btn and self._slow_btn.is_active)
            or (self._stop_btn and self._stop_btn.is_active)
        )

    @property
    def prev_block(self) -> Block | None:
        return self._prev_block

    @prev_block.setter
    def prev_block(self, block: Block) -> None:
        self._prev_block = block
        if block and block.next_block != self:
            block.next_block = self

    @property
    def next_block(self) -> Block | None:
        return self._next_block

    @next_block.setter
    def next_block(self, block: Block) -> None:
        self._next_block = block
        if block and block.prev_block != self:
            block.prev_block = self

    @property
    def is_left_to_right(self) -> bool:
        return self._left_to_right

    @property
    def is_right_to_left(self) -> bool:
        return not self._left_to_right

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

        print(f"Block {self.block_id} signal_slow_down")
        if self.next_block and self.next_block.is_occupied:
            if self._current_motive:
                self._original_speed = self._current_motive.speed
                scope = self._current_motive.scope
                tmcc_id = self._current_motive.tmcc_id
                is_tmcc = self._current_motive.is_tmcc
                req = RampedSpeedReq(tmcc_id, "restricted", scope, is_tmcc)
                req.send()

    def signal_stop_immediate(self) -> None:
        print(f"Block {self.block_id} signal_stop_immediate")
        if self.next_block and self.next_block.is_occupied:
            if self._current_motive:
                if self._original_speed is None:
                    self._original_speed = self._current_motive.speed
                scope = self._current_motive.scope
                tmcc_id = self._current_motive.tmcc_id
                if self._current_motive.is_tmcc is True:
                    req = CommandReq(TMCC1EngineCommandEnum.STOP_IMMEDIATE, tmcc_id, scope=scope)
                else:
                    req = CommandReq(TMCC2EngineCommandEnum.STOP_IMMEDIATE, tmcc_id, scope=scope)
                req.send()

    def block_clear(self) -> None:
        print(f"Block {self.block_id} signal_block_clear")
        self._original_speed = None
        self._current_motive = None
        if self._prev_block and self.is_occupied is False:
            self._prev_block.next_block_clear(self)
