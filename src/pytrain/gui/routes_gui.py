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

from ..db.component_state import RouteState
from ..gui.component_state_gui import ComponentStateGui
from ..gui.state_based_gui import StateBasedGui
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1RouteCommandEnum


class RoutesGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        scale_by: float = 1.0,
        exclude_unnamed: bool = True,
    ) -> None:
        StateBasedGui.__init__(
            self,
            "Routes",
            label,
            width,
            height,
            aggrigator,
            disabled_bg="red",
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
        )

    def get_target_states(self) -> list[RouteState]:
        pds: list[RouteState] = []
        accs = self._state_store.get_all(CommandScope.ROUTE)
        for acc in accs:
            pds.append(cast(RouteState, acc))
        return pds

    def is_active(self, state: RouteState) -> bool:
        return state.is_active

    def switch_state(self, pd: RouteState) -> None:
        with self._cv:
            if pd.is_active:
                CommandReq(TMCC1RouteCommandEnum.FIRE, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1RouteCommandEnum.FIRE, pd.tmcc_id).send()
