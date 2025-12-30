#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#  All Rights Reserved.
#
#  This work is licensed under the terms of the LPGL license.
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import abc
from abc import ABC

from ..constants import DEFAULT_ADDRESS, CommandScope
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq


class CycleToneReqBase(SequenceReq, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        command: SequenceCommandEnum,
        address: int,
        scope: CommandScope = CommandScope.ENGINE,
        data: int = None,
    ) -> None:
        super().__init__(command, address, scope)
        self._scope = scope
        self._data = data
        self._state = None
        self.add(TMCC2EngineCommandEnum.AUX1_OPTION_ONE, scope=scope)

    @property
    def scope(self) -> CommandScope | None:
        return self._scope

    @scope.setter
    def scope(self, new_scope: CommandScope) -> None:
        if new_scope != self._scope:
            # can only change scope for Engine and Train commands, and then, just from the one to the other
            if self._scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                if new_scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                    self._scope = new_scope
                    self._apply_scope()
                    return
            raise AttributeError(f"Scope {new_scope} not supported for {self}")


class CycleHornToneReq(CycleToneReqBase):
    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        data: int = None,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(SequenceCommandEnum.CYCLE_HORN_TONE, address, scope, data)
        self.add(TMCC2EngineCommandEnum.QUILLING_HORN, address, scope=scope, data=2, delay=0.2)
        self.add(TMCC2EngineCommandEnum.BLOW_HORN_ONE, address, scope=scope, delay=0.4, repeat=2)


SequenceCommandEnum.CYCLE_HORN_TONE.value.register_cmd_class(CycleHornToneReq)


class CycleBellToneReq(CycleToneReqBase):
    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        data: int = None,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(SequenceCommandEnum.CYCLE_BELL_TONE, address, scope, data)
        self.add(TMCC2EngineCommandEnum.BELL_SLIDER_POSITION, address, scope=scope, data=2, delay=0.2)
        self.add(TMCC2EngineCommandEnum.BELL_ONE_SHOT_DING, address, scope=scope, data=3, delay=0.4)


SequenceCommandEnum.CYCLE_BELL_TONE.value.register_cmd_class(CycleBellToneReq)
