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

from gpiozero import Button

from ..db.component_state import IrdaState, EngineState, TrainState, SwitchState, BlockState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler, P
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, Direction
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum, TMCC1_RESTRICTED_SPEED
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2_RESTRICTED_SPEED

log = logging.getLogger(__name__)


# noinspection PyUnresolvedReferences
class Block:
    """
    Represents a Block entity in a railway system simulation.

    The Block class models a segment of track in a railway system. It provides mechanisms
    to monitor and control the state of the block, including occupancy detection, speed
    control, and signaling. The class supports the integration of track components (such as
    switches and sensors) for automating block management and ensuring safe train operations.

    Attributes:
        state (BlockState): Retrieves the current state of the block.
        name (str | None): The optional name of the block.
        block_id (int): The unique identifier for the block.
        scope (CommandScope): Returns the command scope for the block.
        address (int): Alias for block_id, representing the block's address.
        sensor_track (IrdaState | None): The associated sensor track state, if any.
        switch (SwitchState | None): The associated switch state, if configured.
        occupied_by (EngineState | TrainState | None): The motive entity occupying the block.
        occupied_direction (Direction | None): Direction of the motive occupying the block.
        is_occupied (bool): True if the block is occupied, False otherwise.
        is_slowed (bool | None): Indicates if the block is being slowed (can be None if not applicable).
        is_stopped (bool | None): Indicates if the block is stopped (can be None if not applicable).
        prev_block (Block | None): Adjacent block in the "previous" direction, if configured.
        next_block (Block | None): Adjacent block in the "next" direction, if configured.
        is_left_to_right (bool): Indicates whether the block is oriented from left to right.
        is_right_to_left (bool): Indicates whether the block is oriented from right to left.
        direction (Direction): Represents the direction of the block based on its orientation.
    """

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
        self._motive_direction = None
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
        self._sensor_track_watcher = self._switch_watcher = None
        if self.sensor_track:
            self._sensor_track_watcher = StateWatcher(self.sensor_track, self._cache_motive)
        # finally, update corresponding state record on all nodes
        self.broadcast_state()
        self._block_state = ComponentStateStore.get_state(CommandScope.BLOCK, self.block_id)

    def __repr__(self) -> str:
        nm = f" {self.name}" if self.name else ""
        oc = f" Occupied: {self.is_occupied if self.is_occupied is not None else 'Unknown'}"
        dr = f" Direction: {self.direction.name}" if self.direction else ""
        return f"Block{nm} #{self.block_id}{oc}{dr}"

    @property
    def state(self) -> BlockState:
        return self._block_state

    @property
    def name(self) -> str:
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
    def occupied_direction(self) -> Direction:
        return self._motive_direction

    @property
    def is_occupied(self) -> bool:
        return (
            (self._occupied_btn and self._occupied_btn.is_active)
            or (self._slow_btn and self._slow_btn.is_active)
            or (self._stop_btn and self._stop_btn.is_active)
        )

    @property
    def is_slowed(self) -> bool:
        return self._slow_btn.is_active if self._slow_btn else None

    @property
    def is_stopped(self) -> bool:
        return self._stop_btn.is_active if self._stop_btn else None

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

    @property
    def direction(self) -> Direction:
        return Direction.L2R if self.is_left_to_right else Direction.R2L

    def broadcast_state(self):
        from ..pdi.block_req import BlockReq
        from ..comm.comm_buffer import CommBuffer

        block_req = BlockReq(self)
        CommBuffer.get().update_state(block_req)

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
            self._switch_watcher = StateWatcher(self.switch, self.respond_to_thrown_switch)
            if was_clear is True:
                self.respond_to_thrown_switch()
        else:
            pass

    def signal_slowdown(self) -> None:
        log.info(f"Block {self.block_id} signal_slow_down")
        self.slow_down()
        self.broadcast_state()

    def signal_stop(self) -> None:
        log.info(f"Block {self.block_id} signal_stop")
        # if next block is occupied, stop train in this block immediately
        if self.next_block and self.next_block.is_occupied:
            self.stop_immediate()
        self.broadcast_state()

    def signal_block_clear(self) -> None:
        log.info(f"Block {self.block_id} signal_block_clear")
        self._original_speed = None
        self._current_motive = None
        if self._prev_block and self.is_occupied is False:
            self._prev_block.next_block_clear(self)
        self.broadcast_state()

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
        log.info(
            f"Cache Motive called,  {self.sensor_track.tmcc_id} {scope} {last_id} "
            f"{ld} {self.sensor_track.last_direction}"
        )
        last_motive = self.occupied_by

        # we want to record the info on the train in the block whether it
        # is coming or going; although if it is going, we have to figure out
        # how to clear it...
        if self.sensor_track.is_train is True and self.sensor_track.last_train_id:
            self._current_motive = ComponentStateStore.get_state(CommandScope.TRAIN, self.sensor_track.last_train_id)
        elif self.sensor_track.is_engine is True and self.sensor_track.last_engine_id:
            self._current_motive = ComponentStateStore.get_state(CommandScope.ENGINE, self.sensor_track.last_engine_id)
        else:
            # a train is passing out of this block
            self._current_motive = None
            self._motive_direction = None

        if self._current_motive:
            self._original_speed = self._current_motive.speed
            self._motive_direction = self.sensor_track.last_direction
        else:
            self._original_speed = None
            self._motive_direction = None
        if last_motive != self.occupied_by:
            self.broadcast_state()

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
