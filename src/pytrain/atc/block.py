#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

import logging
from threading import Thread

from gpiozero import Button

from ..db.component_state import IrdaState, EngineState, TrainState, SwitchState
from ..db.component_state_store import ComponentStateStore
from ..db.watchable import Watchable
from ..gpio.gpio_handler import GpioHandler, P
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum, TMCC1_RESTRICTED_SPEED
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2_RESTRICTED_SPEED

log = logging.getLogger(__name__)


class Block(Watchable):
    @classmethod
    def button(cls, pin: P) -> Button:
        return GpioHandler.make_button(pin)

    # noinspection PyTypeChecker
    def __init__(
        self,
        block_id: int,
        block_name: str = None,
        sensor_track_id: int = None,
        occupied_pin: P = None,
        slow_pin: P = None,
        stop_pin: P = None,
        left_to_right: bool = True,
    ) -> None:
        self._block_id = block_id
        self._block_name = block_name
        if sensor_track_id:
            self._sensor_track: IrdaState = ComponentStateStore.get_state(CommandScope.IRDA, sensor_track_id)
        else:
            self._sensor_track = None

        self._occupied_btn = self.button(occupied_pin) if occupied_pin else None
        self._slow_btn = self.button(slow_pin) if slow_pin else None
        self._stop_btn = self.button(stop_pin) if stop_pin else None

        self._prev_block: Block | None = None
        self._next_block: Block | None = None
        self._current_motive: EngineState | TrainState | None = None
        self._original_speed: int | None = None
        self._switch: SwitchState = None
        self._thru_block: Block = None
        self._out_block: Block = None
        self._left_to_right = left_to_right if left_to_right is not None else True

        # add handlers for state change
        if self._slow_btn:
            self._slow_btn.when_activated = self.signal_slowdown
        if self._stop_btn:
            self._stop_btn.when_activated = self.signal_stop
            self._stop_btn.when_deactivated = self.signal_block_clear

        # start thread if sensor track specified, we also delay calling super until
        # buttons have been created
        self._watch_sensor_track_thread = self._watch_switch_thread = None
        if self.sensor_track:
            self._watch_sensor_track_thread = Thread(target=self.watch_sensor_track, daemon=True)
            self._watch_sensor_track_thread.start()

    def __repr__(self) -> str:
        nm = f" {self.block_name}" if self.block_name else ""
        return f"Block{nm} #{self.block_id} Occupied: {self.is_occupied}"

    def watch_sensor_track(self) -> None:
        while self.sensor_track and True:
            self.sensor_track.changed.wait()
            self.sensor_track.changed.clear()
            with self.sensor_track.synchronizer:
                self._cache_motive()

    def watch_switch(self) -> None:
        while self.switch and True:
            self.switch.changed.wait()
            self.switch.changed.clear()
            with self.switch.synchronizer:
                self.respond_to_thrown_switch()

    @property
    def block_name(self) -> str:
        return self._block_name

    @property
    def block_id(self) -> int:
        return self._block_id

    @property
    def scope(self) -> CommandScope:
        return CommandScope.BLOCK

    @property
    def address(self) -> int:
        return self._block_id

    @property
    def sensor_track(self) -> IrdaState:
        return self._sensor_track

    @property
    def switch(self) -> SwitchState:
        return self._switch

    @property
    def occupied_by(self) -> EngineState | TrainState | None:
        return self._current_motive

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

    def next_switch(self, switch_tmcc_id, thru_block: Block, out_block: Block) -> None:
        if switch_tmcc_id:
            if thru_block is None or out_block is None:
                raise AttributeError("Thru and Out blocks cannot be None")
            if self == thru_block or self == out_block or thru_block == out_block:
                raise AttributeError("Thru and Out blocks cannot be the same block")
            self._switch: SwitchState = ComponentStateStore.get_state(CommandScope.SWITCH, switch_tmcc_id)
            self._thru_block = thru_block
            self._out_block = out_block
            was_clear = True if self.switch.changed.is_set() is False else False
            self._watch_switch_thread = Thread(target=self.watch_switch, daemon=True)
            self._watch_switch_thread.start()
            if was_clear is True:
                self.respond_to_thrown_switch()
        else:
            pass

    def signal_slowdown(self) -> None:
        log.info(f"Block {self.block_id} signal_slow_down")
        self.slow_down()
        with self.synchronizer:
            self.synchronizer.notify_all()

    def signal_stop(self) -> None:
        log.info(f"Block {self.block_id} signal_stop")
        # if next block is occupied, stop train in this block immediately
        if self.next_block and self.next_block.is_occupied:
            self.stop_immediate()
        with self.synchronizer:
            self.synchronizer.notify_all()

    def signal_block_clear(self) -> None:
        log.info(f"Block {self.block_id} signal_block_clear")
        self._original_speed = None
        self._current_motive = None
        if self._prev_block and self.is_occupied is False:
            self._prev_block.next_block_clear(self)
        with self.synchronizer:
            self.synchronizer.notify_all()

    def next_block_clear(self, signaling_block: Block) -> None:
        from ..protocol.sequence.ramped_speed_req import RampedSpeedReq

        # resume original speed
        log.info(f"Block {self.block_id} NBC speed: {self._original_speed} {signaling_block.is_occupied}")
        if self._current_motive and self._original_speed and signaling_block.is_occupied is False:
            scope = self._current_motive.scope
            tmcc_id = self._current_motive.tmcc_id
            is_tmcc = self._current_motive.is_tmcc
            req = RampedSpeedReq(tmcc_id, self._original_speed, scope, is_tmcc)
            req.send()

    def slow_down(self):
        if self.next_block and self.next_block.is_occupied:
            from ..protocol.sequence.ramped_speed_req import RampedSpeedReq

            if self._current_motive:
                restricted_speed = TMCC2_RESTRICTED_SPEED if self._current_motive.is_legacy else TMCC1_RESTRICTED_SPEED
                self._original_speed = self._current_motive.speed
                if self._original_speed > restricted_speed:
                    scope = self._current_motive.scope
                    tmcc_id = self._current_motive.tmcc_id
                    is_tmcc = self._current_motive.is_tmcc
                    req = RampedSpeedReq(tmcc_id, "restricted", scope, is_tmcc)
                    req.send()

    def stop_immediate(self):
        if self._current_motive:
            if self._original_speed is None:
                self._original_speed = self._current_motive.speed
            scope = self._current_motive.scope
            tmcc_id = self._current_motive.tmcc_id
            if self._current_motive.is_tmcc is True:
                CommandReq(TMCC1EngineCommandEnum.STOP_IMMEDIATE, tmcc_id, scope=scope).send()
            else:
                CommandReq(TMCC2EngineCommandEnum.STOP_IMMEDIATE, tmcc_id, scope=scope).send()
        elif self.is_occupied is True:
            # send a stop to all engines, as otherwise, we could have a crash
            CommandReq(TMCC1EngineCommandEnum.BLOW_HORN_ONE, 99).send()
            CommandReq(TMCC1EngineCommandEnum.STOP_IMMEDIATE, 99).send()

    def _cache_motive(self) -> None:
        scope = "Train" if self.sensor_track.is_train else "Engine"
        last_id = self.sensor_track.last_engine_id
        ld = "L -> R" if self.is_left_to_right else "R -> L"
        log.info(f"{self.sensor_track.tmcc_id} {scope} {last_id} {ld} {self.sensor_track.last_direction}")

        dir_int = 1 if self.is_left_to_right else 0
        last_motive = self.occupied_by
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
        if last_motive != self.occupied_by:
            with self.synchronizer:
                self.synchronizer.notify_all()

    def respond_to_thrown_switch(self) -> None:
        if self.switch:
            log.info(f"{self.switch} Thru: {self._thru_block} Out: {self._out_block}")
            if self.switch.is_through and self.next_block != self._thru_block:
                self.next_block = self._thru_block
            elif self.switch.is_out and self.next_block != self._out_block:
                self.next_block = self._out_block
            else:
                return
            if self.next_block.is_occupied is False:
                self.next_block.signal_block_clear()
            else:
                if self._stop_btn.is_active:
                    self.signal_stop()
                elif self._slow_btn.is_active:
                    self.signal_slowdown()
