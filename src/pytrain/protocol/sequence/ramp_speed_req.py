#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
from abc import ABC, ABCMeta

from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq, T
from ..constants import CommandScope, DEFAULT_ADDRESS
from ..multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm
from ...db.engine_state import EngineState

log = logging.getLogger(__name__)

ENGINEER_DIALOG_DELAY: float = 2.50


class RampSpeedReqBase(SequenceReq, ABC):
    """
    Base class for the threaded speed ramper.

    Unlike ``RampedSpeedReq``, this request expands no steps and schedules nothing;
    it emits the generation-appropriate ``TARGET_SPEED`` announcement (plus the tower
    and engineer dialogs, when asked) and hands the target to the engine's ramp
    thread in ``_on_before_send``.
    """

    __metaclass__ = ABCMeta

    # noinspection PyUnreachableCode
    def __init__(
        self,
        command: SequenceCommandEnum,
        address: int,
        speed: int | str | T = None,
        scope: CommandScope = CommandScope.ENGINE,
        dialog: bool = False,
    ) -> None:
        super().__init__(command, address, scope)
        tower, s, speed_req, engr = self.decode_rr_speed(speed, self.is_tmcc1)
        # if an integer speed was provided, use it, otherwise, rely on rr speed
        # provided by decode call; only do this if dialogs are NOT requested
        if isinstance(speed, int) and dialog is False:
            if isinstance(speed_req, int):
                speed_req = min(speed_req, speed)
            else:
                speed_req = speed

        # the target speed is kept unclamped; the ramp re-clamps to the live ceiling
        self._target_speed = speed_req
        self._dialog = dialog

        # if there is no state information, there is nothing to ramp; fall back to
        # a plain ABSOLUTE_SPEED (plus RPM), exactly as RampedSpeedReqBase does
        if address == DEFAULT_ADDRESS or not isinstance(self.state, EngineState) or self.state.speed is None:
            self._is_ramp = False
            if tower and engr and dialog:
                from .speed_req import SpeedReq

                sr = SpeedReq(address, speed, scope, self.is_tmcc1)
                for request in sr.requests:
                    self.add(request.request, delay=request.delay, repeat=request.repeat)
            else:
                if address == DEFAULT_ADDRESS:
                    self.add(TMCC1EngineCommandEnum.ABSOLUTE_SPEED, address, speed_req, scope)
                    self.add(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, address, speed_req, scope)
                else:
                    speed_enum = (
                        TMCC1EngineCommandEnum.ABSOLUTE_SPEED
                        if self.is_tmcc1
                        else TMCC2EngineCommandEnum.ABSOLUTE_SPEED
                    )
                    self.add(speed_enum, address, speed_req, scope)
                if address == DEFAULT_ADDRESS or self.is_tmcc2:
                    rpm = tmcc2_speed_to_rpm(speed_req)
                    self.add(TMCC2EngineCommandEnum.DIESEL_RPM, address, data=rpm, scope=scope, delay=0.2)
        else:
            self._is_ramp = True
            target_enum = (
                TMCC2EngineCommandEnumEx.TARGET_SPEED if self.state.is_legacy else TMCC1EngineCommandEnum.TARGET_SPEED
            )
            self.add(target_enum, self.address, self._target_speed, self.scope)
            # issue tower dialog, if requested
            if tower and dialog:
                self.add(tower, address, scope=scope)
            # issue engineer dialog, if requested
            if engr and dialog:
                self.add(engr, address, scope=scope, delay=ENGINEER_DIALOG_DELAY)

    @property
    def target_speed(self) -> int:
        return self._target_speed

    @property
    def is_ramp(self) -> bool:
        """True, when this request starts or retargets a ramp thread."""
        return self._is_ramp

    def _on_before_send(self) -> None:
        # start or retarget the ramp *before* the TARGET_SPEED bytes go out, so the
        # echo of our own announcement is recognized as the ramp's own
        if self._is_ramp and isinstance(self.state, EngineState):
            self.state.ramp_to(self._target_speed, dialog=self._dialog)


class RampSpeedReq(RampSpeedReqBase):
    def __init__(
        self,
        address: int,
        speed: int | str | T,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(SequenceCommandEnum.RAMP_SPEED_SEQ, address, speed, scope)


SequenceCommandEnum.RAMP_SPEED_SEQ.value.register_cmd_class(RampSpeedReq)


class RampSpeedDialogReq(RampSpeedReqBase):
    def __init__(
        self,
        address: int,
        speed: int | str | T,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(
            SequenceCommandEnum.RAMP_SPEED_DIALOG_SEQ,
            address,
            speed,
            scope,
            dialog=True,
        )


SequenceCommandEnum.RAMP_SPEED_DIALOG_SEQ.value.register_cmd_class(RampSpeedDialogReq)
