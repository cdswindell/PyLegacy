#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from typing import cast

from ..db.accessory_state import AccessoryState
from ..db.engine_state import TrainState
from ..gui.component_state_gui import ComponentStateGui
from ..gui.state_based_gui import StateBasedGui
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


class PowerDistrictsGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
    ) -> None:
        StateBasedGui.__init__(
            self,
            "Power Districts",
            label,
            width,
            height,
            aggrigator,
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
        )

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState | TrainState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            acc = cast(AccessoryState, acc)
            if acc.is_power_district:
                pds.append(acc)
        trains = self._state_store.get_all(CommandScope.TRAIN)
        for train in trains:
            train = cast(TrainState, train)
            if train.is_power_district:
                pds.append(train)
        return pds

    def is_active(self, state: AccessoryState | TrainState) -> bool:
        return state.is_aux_on

    def switch_state(self, pd: AccessoryState | TrainState) -> None:
        with self._cv:
            if isinstance(pd, AccessoryState):
                enum = TMCC1AuxCommandEnum.AUX2_OPT_ONE if pd.is_aux_on else TMCC1AuxCommandEnum.AUX1_OPT_ONE
                scope = CommandScope.ACC
            elif isinstance(pd, TrainState):
                enum = (
                    TMCC2EngineCommandEnum.AUX2_OPTION_ONE if pd.is_aux_on else TMCC2EngineCommandEnum.AUX1_OPTION_ONE
                )
                scope = CommandScope.TRAIN
            CommandReq(enum, pd.tmcc_id, scope=scope).send(repeat=2)
