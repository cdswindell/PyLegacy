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
from typing import Dict, Any


from ..pdi.constants import PdiCommand, IrdaAction
from ..pdi.irda_req import IrdaSequence, IrdaReq
from ..protocol.constants import Direction, CommandScope
from .component_state import LcsState, P, log, SCOPE_TO_STATE_MAP


class IrdaState(LcsState):
    """
    Maintain the state of a Sensor Track (Irda)
    """

    def __init__(self, scope: CommandScope = CommandScope.IRDA) -> None:
        if scope != CommandScope.IRDA:
            raise ValueError(f"Invalid scope: {scope}, expected {CommandScope.IRDA.name}")
        super().__init__(scope)
        self._sequence: IrdaSequence | None = None
        self._loco_rl: int | None = 255
        self._loco_lr: int | None = 255
        self._last_train_id = self._last_engine_id = self._last_dir = self._product_id = None

    def __repr__(self) -> str:
        if self.sequence and self.sequence != IrdaSequence.NONE:
            rle = f"{self._loco_rl}" if self._loco_rl and self._loco_rl != 255 else "Any"
            lre = f"{self._loco_lr}" if self._loco_lr and self._loco_lr != 255 else "Any"
            rl = f" When Engine ID (R -> L): {rle}"
            lr = f" When Engine ID (L -> R): {lre}"
        else:
            rl = lr = ""
        le = f" Last Engine ID: {self._last_engine_id}" if self._last_engine_id else ""
        lt = f" Last Train ID: {self._last_train_id}" if self._last_train_id else ""
        if self._last_dir is not None:
            ld = " L --> R" if self._last_dir == 1 else " R --> L"
        else:
            ld = ""
        return f"Sensor Track {self.address}: Sequence: {self.sequence_str}{rl}{lr}{le}{lt}{ld}"

    def update(self, command: P) -> None:
        from ..comm.comm_buffer import CommBuffer
        from .component_state_store import ComponentStateStore

        if command:
            with self._cv:
                self._is_known = True
                super().update(command)
                if isinstance(command, IrdaReq) and command.pdi_command == PdiCommand.IRDA_RX:
                    if command.action == IrdaAction.CONFIG:
                        self._sequence = command.sequence
                        self._loco_rl = command.loco_rl
                        self._loco_lr = command.loco_lr
                    elif command.action == IrdaAction.SEQUENCE:
                        self._sequence = command.sequence
                    elif command.action == IrdaAction.DATA:
                        # change engine/train speed, based on the direction of travel
                        self._last_engine_id = command.engine_id
                        self._last_train_id = command.train_id
                        self._last_dir = command.direction
                        self._product_id = command.product_id
                        if log.isEnabledFor(logging.DEBUG):
                            log.debug(f"IRDA {self.address} Sequence: {self.sequence} Command: {command}")
                        if (
                            self.sequence
                            in {
                                IrdaSequence.SLOW_SPEED_NORMAL_SPEED,
                                IrdaSequence.NORMAL_SPEED_SLOW_SPEED,
                            }
                            and CommBuffer.is_server()
                        ):
                            rr_speed = None
                            if command.is_right_to_left:
                                rr_speed = "slow" if self.sequence == IrdaSequence.SLOW_SPEED_NORMAL_SPEED else "normal"
                            elif command.is_left_to_right:
                                rr_speed = "normal" if self.sequence == IrdaSequence.SLOW_SPEED_NORMAL_SPEED else "slow"
                            if rr_speed:
                                address = None
                                scope = CommandScope.ENGINE
                                if command.train_id:
                                    address = command.train_id
                                    scope = CommandScope.TRAIN
                                elif command.engine_id:
                                    address = command.engine_id
                                state = ComponentStateStore.get_state(scope, address)
                                if state is not None:
                                    from ..protocol.sequence.ramped_speed_req import RampedSpeedReq

                                    # noinspection PyTypeChecker
                                    RampedSpeedReq(address, rr_speed, scope=scope, is_tmcc=state.is_tmcc).send()
                            # send update to Train and component engines as well
                            orig_scope = command.scope
                            orig_tmcc_id = command.tmcc_id
                            try:
                                if command.engine_id:
                                    engine_state = ComponentStateStore.get_state(CommandScope.ENGINE, command.engine_id)
                                    command.scope = CommandScope.ENGINE
                                    command.tmcc_id = command.engine_id
                                    engine_state.update(command)
                            finally:
                                command.scope = orig_scope
                                command.tmcc_id = orig_tmcc_id
                    self.changed.set()
                    self._cv.notify_all()

    @property
    def sequence(self) -> IrdaSequence:
        return self._sequence

    @property
    def sequence_str(self) -> str | None:
        return self.sequence.name.title() if self.sequence else "NA"

    @property
    def last_direction(self) -> Direction:
        if self._last_dir == 1:
            return Direction.L2R
        elif self._last_dir == 0:
            return Direction.R2L
        else:
            return Direction.UNKNOWN

    @property
    def is_left_to_right(self) -> bool:
        return self.last_direction == 1

    @property
    def is_right_to_left(self) -> bool:
        return self.last_direction == 0

    @property
    def last_engine_id(self) -> int:
        return self._last_engine_id

    @property
    def last_train_id(self) -> int:
        return self._last_train_id

    @property
    def is_engine(self) -> bool:
        return (self.is_train is False) and (self._last_engine_id is not None) and (self._last_engine_id > 0)

    @property
    def product_type(self) -> str:
        return self._product_id

    @property
    def is_train(self) -> bool:
        return (self._last_train_id is not None) and (self._last_train_id > 0)

    def as_bytes(self) -> bytes:
        # TODO: return IrdaAction.DATA
        if self.is_known:
            return IrdaReq(
                self.address,
                PdiCommand.IRDA_RX,
                IrdaAction.CONFIG,
                sequence=self._sequence,
                loco_rl=self._loco_rl,
                loco_lr=self._loco_lr,
            ).as_bytes
        else:
            return bytes()

    def as_dict(self) -> Dict[str, Any]:
        d = super()._as_dict()
        d["last_direction"] = self.last_direction.name.lower()
        d["last_engine_id"] = self.last_engine_id
        d["last_train_id"] = self.last_train_id
        d["sequence"] = self.sequence.name.lower() if self.sequence else "none"
        return d


SCOPE_TO_STATE_MAP.update({CommandScope.IRDA: IrdaState})
