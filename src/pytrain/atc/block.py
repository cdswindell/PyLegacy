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

from ..db.component_state import SwitchState
from ..db.engine_state import EngineState, TrainState
from ..db.irda_state import IrdaState
from ..db.block_state import BlockState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler, P
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, Direction
from ..protocol.multibyte.multibyte_constants import TMCC2RailSoundsDialogControl
from ..protocol.tmcc1.tmcc1_constants import TMCC1_RESTRICTED_SPEED, TMCC1EngineCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2_RESTRICTED_SPEED, TMCC2EngineCommandEnum
from ..utils.validations import Validations

log = logging.getLogger(__name__)


class Block:
    """
    This class represents a Block, a section of a railway network, and manages its state and status.

    The Block is designed to monitor presence and state information for engines or trains traversing through it.
    It integrates with sensors and other components to track occupancy, direction, and events like entering
    or exiting a portion of the Block. Blocks can also be linked together to form a sequence in the network,
    with support for directionality and connections to adjacent Blocks. Furthermore, Blocks interact with switches
    to handle diverging or converging paths and broadcast their state to external systems.

    Args:
        block_id (int): Unique identifier for the block.
        block_name (Optional[str]): Name of the block, if any.
        sensor_track_id (Optional[int]): Unique identifier for the IRDA sensor used to track trains in the block.
        enter_pin (Optional[P]): Pin for the entry button used to mark the block as occupied.
        slow_pin (Optional[P]): Pin for the slow section button in the block.
        stop_pin (Optional[P]): Pin for the stop section button in the block.
        left_to_right (bool): Default directionality of the block (left to right if True).
        dialog (bool): Determines whether dialogs are triggered for block events (default is True).

    Errors:
        AttributeError: Raised in situations such as invalid block id, missing switches, or incorrect configuration.
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
        enter_pin: P = None,
        slow_pin: P = None,
        stop_pin: P = None,
        left_to_right: bool = True,
        dialog: bool = True,
    ) -> None:
        # check if block_id is valid
        Validations.validate_int(
            block_id,
            min_value=1,
            max_value=99,
            label="Block ID",
        )
        Validations.validate_int(
            sensor_track_id,
            min_value=1,
            max_value=99,
            label="Sensor Track TMCC ID",
            allow_none=True,
        )
        if ComponentStateStore.get_state(CommandScope.BLOCK, block_id, create=False):
            raise AttributeError(f"Block ID {block_id} is in use")
        self._block_id = block_id
        self._block_name = block_name
        if sensor_track_id:
            self._sensor_track: IrdaState = ComponentStateStore.get_state(CommandScope.IRDA, sensor_track_id)
        else:
            self._sensor_track = None

        self._enter_btn = self.button(enter_pin) if enter_pin else None
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
        self._dialog = dialog
        self._order_activated = []
        self._order_deactivated = []

        # add handlers for state change
        if self._enter_btn:
            self._enter_btn.when_activated = self.signal_occupied_enter
            self._enter_btn.when_activated = self.signal_occupied_exit
        if self._slow_btn:
            self._slow_btn.when_activated = self.signal_slow_enter
            self._slow_btn.when_deactivated = self.signal_slow_exit
        if self._stop_btn:
            self._stop_btn.when_activated = self.signal_stop_enter
            self._stop_btn.when_deactivated = self.signal_stop_exit

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
    def name(self) -> str:
        return self._block_name

    @property
    def block_id(self) -> int:
        return self._block_id

    @property
    def sensor_track(self) -> IrdaState:
        """
        Return the IrdaState at the end of the block, if any.
        Required to control the specific engine/train in the block
        """
        return self._sensor_track

    @property
    def switch(self) -> SwitchState:
        """
        Return the SwitchState at the end of the block, if any
        """
        return self._switch

    @property
    def occupied_by(self) -> EngineState | TrainState | None:
        """
        Return the EngineState or TrainState of the entity
        currently traversing or stopped in the block
        """
        return self._current_motive

    @property
    def occupied_direction(self) -> Direction:
        """
        What direction is the train in the block moving,
        L to R or R to L.
        """
        return self._motive_direction

    @property
    def is_occupied(self) -> bool:
        """
        Is the block occupied?
        """
        return (
            (self.occupied_by and self.occupied_direction == self.direction)
            or self.is_entered is True
            or self.is_slowed is True
            or self.is_stopped is True
        )

    @property
    def is_clear(self) -> bool:
        """
        Is the block unoccupied?
        """
        return self.is_occupied is False

    @property
    def is_entered(self) -> bool:
        """
        Is the "entered" block portion occupied?
        """
        return self._enter_btn.is_active if self._enter_btn else None

    @property
    def is_slowed(self) -> bool:
        """
        Is the "slow" block portion occupied?
        """
        return self._slow_btn.is_active if self._slow_btn else None

    @property
    def is_stopped(self) -> bool:
        """
        Is the "stopped" block portion occupied?
        """
        return self._stop_btn.is_active if self._stop_btn else None

    @property
    def is_dialog(self) -> bool:
        """
        Returns True if tower/Engineer dialogs are given in
        response to block events in this block
        """
        return self._dialog

    @is_dialog.setter
    def is_dialog(self, dialog: bool) -> None:
        self._dialog = dialog

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
        """
        Block directionality. Can be L to R (default) or R to L.
        The IR Sensor track must be at the beginning of the block,
        so for an L to R block, the sensor track is placed to the
        left of the block entrance.
        """
        return Direction.L2R if self.is_left_to_right else Direction.R2L

    @property
    def state(self) -> BlockState:
        """
        Return the BlockState associated with this block
        """
        return self._block_state

    def broadcast_state(self):
        """
        Send current block state to PyTrain server and from
        there to all clients
        """
        from ..comm.comm_buffer import CommBuffer
        from ..pdi.block_req import BlockReq

        block_req = BlockReq(self)
        CommBuffer.get().update_state(block_req)

    def next_switch(self, switch_tmcc_id, thru_block: Block, out_block: Block) -> None:
        Validations.validate_int(
            switch_tmcc_id,
            min_value=1,
            max_value=99,
            label="Switch TMCC ID",
        )
        if thru_block is None or out_block is None:
            raise AttributeError("Thru and Out blocks cannot be None")
        if switch_tmcc_id:
            if thru_block is None or out_block is None:
                raise AttributeError("Thru and Out blocks cannot be None")
            if self == thru_block or self == out_block or thru_block == out_block:
                raise AttributeError("Thru and Out blocks cannot be the same block")
            self._switch: SwitchState = ComponentStateStore.get_state(CommandScope.SWITCH, switch_tmcc_id)
            if self._switch is None:
                raise AttributeError(f"Switch {switch_tmcc_id} not found")
            self._thru_block = thru_block
            self._out_block = out_block
            self._switch_watcher = StateWatcher(self.switch, self.respond_to_thrown_switch)
            # force call to the method that sets next_block
            self.respond_to_thrown_switch()
        else:
            raise AttributeError("Switch TMCC ID cannot be None")

    def signal_occupied_enter(self) -> None:
        log.info(f"Block {self.block_id} occupied enter")
        if 1 not in self._order_activated:
            self._order_activated.append(1)
        self.broadcast_state()

    def signal_occupied_exit(self) -> None:
        log.info(f"Block {self.block_id} occupied exit")
        if 1 not in self._order_deactivated:
            self._order_deactivated.append(1)
        # if we are traversing this block in reverse, which we know
        # because the motive direction differs from the defined block
        # direction, clear the motive info
        if self.occupied_direction and self.occupied_direction != self.direction:
            self._original_speed = None
            self._current_motive = None
            self._motive_direction = None
        self.broadcast_state()

    def signal_slow_enter(self) -> None:
        log.info(f"Block {self.block_id} slow enter")
        if 2 not in self._order_activated:
            self._order_activated.append(2)
        if self.occupied_direction == self.direction:
            if self.next_block and self.next_block.is_occupied:
                self.slow_down()
            elif self.next_block and self.next_block.is_clear:
                self.do_dialog(TMCC2RailSoundsDialogControl.ENGINEER_ALL_CLEAR)
        self.broadcast_state()

    def signal_slow_exit(self) -> None:
        log.info(f"Block {self.block_id} slow exit")
        self.broadcast_state()

    def signal_stop_enter(self) -> None:
        log.info(f"Block {self.block_id} stop enter")
        if 3 not in self._order_activated:
            self._order_activated.append(3)
        # if the next block is occupied, stop the train in this block immediately
        if self.occupied_direction == self.direction:
            if self.next_block and self.next_block.is_occupied:
                self.stop_immediate()
            # do dialog, if enabled
            elif self.next_block and self.next_block.is_clear:
                self.do_dialog(TMCC2RailSoundsDialogControl.ENGINEER_ALL_CLEAR)
        self.broadcast_state()

    def signal_stop_exit(self) -> None:
        log.info(f"Block {self.block_id} stop exit")
        if 3 not in self._order_deactivated:
            self._order_deactivated.append(3)
        # if exit was fired in the correct order, clear the block
        self.clear_block_info()
        if self._prev_block and self.is_clear:
            self._prev_block.next_block_clear(self)
        self.broadcast_state()

    def clear_block_info(self):
        self._original_speed = None
        self._current_motive = None
        self._motive_direction = None
        self._order_activated.clear()
        self._order_deactivated.clear()

    def next_block_clear(self, signaling_block: Block) -> None:
        log.info(f"Block {self.block_id} orig speed: {self._original_speed} Block {signaling_block.block_id} Clear")
        if signaling_block.is_occupied is False:
            self.resume_speed()

    def slow_down(self):
        if self.next_block and self.next_block.is_occupied:
            from ..protocol.sequence.ramped_speed_req import RampedSpeedReq

            if self._current_motive:
                restricted_speed = TMCC2_RESTRICTED_SPEED if self._current_motive.is_legacy else TMCC1_RESTRICTED_SPEED
                self._original_speed = self._current_motive.speed
                if self._original_speed > restricted_speed:
                    self.do_dialog(TMCC2RailSoundsDialogControl.TOWER_SPEED_RESTRICTED)
                    scope = self._current_motive.scope
                    tmcc_id = self._current_motive.tmcc_id
                    is_tmcc = self._current_motive.is_tmcc
                    req = RampedSpeedReq(tmcc_id, "restricted", scope, is_tmcc)
                    req.send()

    def stop_immediate(self):
        if self._current_motive:
            if self._original_speed is None:
                self._original_speed = self._current_motive.speed
            log.info(f"Immediate stop; previous speed: {self._original_speed}")
            self.do_dialog(TMCC2RailSoundsDialogControl.TOWER_SPEED_STOP_HOLD)
            scope = self._current_motive.scope
            tmcc_id = self._current_motive.tmcc_id
            if self._current_motive.is_tmcc is True:
                CommandReq(TMCC1EngineCommandEnum.STOP_IMMEDIATE, tmcc_id, scope=scope).send()
            else:
                CommandReq(TMCC2EngineCommandEnum.STOP_IMMEDIATE, tmcc_id, scope=scope).send()
        elif self.is_occupied is True:
            # send a stop to all engines, as otherwise, we could have a crash
            if self.is_dialog:
                self.do_dialog(5)
            else:
                CommandReq(TMCC1EngineCommandEnum.BLOW_HORN_ONE, 99).send()
            CommandReq(TMCC1EngineCommandEnum.STOP_IMMEDIATE, 99).send()

    def resume_speed(self) -> None:
        from ..protocol.sequence.ramped_speed_req import RampedSpeedReq

        if self._current_motive and self._original_speed:
            scope = self._current_motive.scope
            tmcc_id = self._current_motive.tmcc_id
            is_tmcc = self._current_motive.is_tmcc
            log.info(f"Resume Speed: {self._original_speed} for {scope.title} {tmcc_id}")
            self.do_dialog(TMCC2RailSoundsDialogControl.TOWER_DEPARTURE_GRANTED)
            req = RampedSpeedReq(tmcc_id, self._original_speed, scope, is_tmcc)
            req.send()

    def do_dialog(self, dialog: CommandDefEnum | int) -> None:
        if self.is_dialog and self._current_motive:
            scope = self._current_motive.scope
            tmcc_id = self._current_motive.tmcc_id
            if isinstance(dialog, int):
                req = CommandReq.build(TMCC2EngineCommandEnum.NUMERIC, tmcc_id, data=dialog, scope=scope)
            else:
                log.info(f"Do dialog {dialog.title} for {scope.title} {tmcc_id}")
                req = CommandReq.build(dialog, tmcc_id, scope=scope)
            req.send()

    def _cache_motive(self) -> None:
        scope = "Train" if self.sensor_track.is_train else "Engine"
        if scope == "Train":
            last_id = self.sensor_track.last_train_id
            prod_type = f"{self.sensor_track.product_type} " if self.sensor_track.product_type != "NA" else " Engine "
            eid = f" ({prod_type}{self.sensor_track.last_engine_id})"
        else:
            last_id = self.sensor_track.last_engine_id
            eid = ""
        ld = "L -> R" if self.is_left_to_right else "R -> L"
        log.info(
            f"Cache Motive called, {self.sensor_track.tmcc_id} {scope} {last_id}{eid} "
            f"{ld} {self.sensor_track.last_direction}"
        )
        # we want to record the info on the train in the block whether it
        # is coming or going; although if it is going, we have to figure out
        # how to clear it...
        last_motive = self.occupied_by
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
            if self.switch.is_through:
                self.next_block = self._thru_block
                self._out_block.prev_block = None
            elif self.switch.is_out:
                self.next_block = self._out_block
                self._thru_block.prev_block = None
            else:
                return
            if self.next_block.is_occupied is True:
                if self._stop_btn.is_active:
                    self.signal_stop_enter()
                elif self._slow_btn.is_active:
                    self.signal_slow_enter()
            elif self.next_block.is_clear:
                self.next_block_clear(self.next_block)
            self.broadcast_state()
