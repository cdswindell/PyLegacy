#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from typing import Dict, Any

from ..protocol.constants import CommandScope, Direction
from .irda_state import IrdaState
from .engine_state import EngineState, TrainState
from .component_state import ComponentState, L, P, SCOPE_TO_STATE_MAP, SwitchState


class BlockState(ComponentState):
    """
    Maintain the state of a Block section
    """

    def __init__(self, scope: CommandScope = CommandScope.BLOCK) -> None:
        if scope != CommandScope.BLOCK:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._block_req = None
        self._block_id = None
        self._prev_block = None
        self._next_block = None
        self._occupied_by: EngineState | TrainState | None = None
        self._occupied_direction = None
        self._direction = None
        self._occupied: bool = False
        self._flags: int = 0
        self._sensor_track: IrdaState | None = None
        self._switch: SwitchState | None = None

    def __repr__(self) -> str:
        msg = f"{self.block_id:>2}" if self.block_id else "NA"
        msg += f" {self.direction.name.lower()}" if self.direction else ""
        msg += f" Occupied: {'Yes' if self.is_occupied is True else 'No '}"
        msg += f" {self.name}" if self.name else ""
        msg += f" {self.occupied_by.scope.label} {self.occupied_by.address}" if self.occupied_by else ""
        msg += (
            f" {self.occupied_direction.label}"
            if self.occupied_direction and self.occupied_direction != Direction.UNKNOWN
            else ""
        )
        return f"Block {msg}"

    def update(self, command: L | P) -> None:
        from ..pdi.block_req import BlockReq
        from .component_state_store import ComponentStateStore

        if command:
            with self._cv:
                super().update(command)
                if isinstance(command, BlockReq):
                    self._block_req = command
                    self._block_id = command.block_id
                    if command.prev_block_id:
                        self._prev_block = ComponentStateStore.get_state(CommandScope.BLOCK, command.prev_block_id)
                    else:
                        self._prev_block = None
                    if command.next_block_id:
                        self._next_block = ComponentStateStore.get_state(CommandScope.BLOCK, command.next_block_id)
                    else:
                        self._next_block = None
                    self._flags = command.flags
                    self._direction = command.direction
                    self._occupied = command.is_occupied
                    self._occupied_direction = command.motive_direction
                    if self._sensor_track is None and command.sensor_track_id:
                        self._sensor_track = ComponentStateStore.get_state(CommandScope.IRDA, command.sensor_track_id)
                    if self._switch is None and command.switch_id:
                        self._switch = ComponentStateStore.get_state(CommandScope.SWITCH, command.switch_id)
                    if command.motive_id:
                        self._occupied_by = ComponentStateStore.get_state(command.motive_scope, command.motive_id)
                    else:
                        self._occupied_by = None
                    self.changed.set()
                    self._cv.notify_all()

    @property
    def is_known(self) -> bool:
        return self._block_req is not None

    @property
    def is_tmcc(self) -> bool:
        return False

    @property
    def is_legacy(self) -> bool:
        return False

    @property
    def is_lcs(self) -> bool:
        return False

    @property
    def block_id(self) -> int:
        return self._block_id

    @property
    def flags(self) -> int:
        return self._flags

    @property
    def is_occupied(self) -> bool:
        return self._occupied

    @property
    def occupied_by(self) -> TrainState | EngineState:
        return self._occupied_by

    @property
    def occupied_direction(self) -> Direction:
        return self._occupied_direction

    @property
    def direction(self) -> Direction:
        return self._direction

    @property
    def sensor_track(self) -> IrdaState:
        return self._sensor_track

    @property
    def switch(self) -> SwitchState:
        return self._switch

    @property
    def prev_block(self) -> BlockState:
        return self._prev_block

    @property
    def next_block(self) -> BlockState:
        return self._next_block

    def as_bytes(self) -> bytes:
        from ..pdi.block_req import BlockReq

        return BlockReq(self).as_bytes

    def as_dict(self) -> Dict[str, Any]:
        if self.occupied_by:
            motive = {
                "scope": self.occupied_by.scope.name.lower(),
                "tmcc_id": self.occupied_by.address,
            }
        else:
            motive = None
        return {
            "block_id": self.block_id,
            "name": self.road_name,
            "direction": self.direction.name.lower(),
            "sensor_track": self.sensor_track.address if self.sensor_track else None,
            "switch": self.switch.address if self.switch else None,
            "previous_block_id": self.prev_block.block_id if self.prev_block else None,
            "next_block_id": self.next_block.block_id if self.next_block else None,
            "is_occupied": self.is_occupied,
            "occupied_by": motive,
        }


SCOPE_TO_STATE_MAP.update({CommandScope.BLOCK: BlockState})
