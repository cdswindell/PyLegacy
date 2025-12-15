#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from threading import Event
from typing import cast

from guizero.event import EventData

from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..db.accessory_state import AccessoryState
from ..gui.component_state_gui import ComponentStateGui
from ..gui.state_based_gui import StateBasedGui, MomentaryActionHandler
from ..pdi.asc2_req import Asc2Req
from ..pdi.constants import PdiCommand, Asc2Action


class AccessoriesGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
    ) -> None:
        self._is_momentary = set()
        self._released_events = dict[int, Event]()
        StateBasedGui.__init__(
            self,
            "Accessories",
            label,
            width,
            height,
            aggrigator,
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
        )

    def _post_process_state_buttons(self) -> None:
        for tmcc_id in self._is_momentary:
            if tmcc_id in self._state_buttons:
                pb = self._state_buttons[tmcc_id]
                pb.when_left_button_pressed = self.when_pressed
                pb.when_left_button_released = self.when_released

    def get_target_states(self) -> list[AccessoryState]:
        pds: list[AccessoryState] = []
        accs = self._state_store.get_all(CommandScope.ACC)
        for acc in accs:
            acc = cast(AccessoryState, acc)
            if acc.is_power_district or acc.is_sensor_track or acc.is_amc2:
                continue
            pds.append(acc)
            name_lc = acc.road_name.lower()
            if "aux1" in name_lc or "ax1" in name_lc or "(a1)" in name_lc or "(m)" in name_lc:
                self._is_momentary.add(acc.address)
        return pds

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, pd: AccessoryState) -> None:
        with self._cv:
            if pd.tmcc_id in self._is_momentary:
                pass
            elif pd.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, pd.tmcc_id).send()

    def when_pressed(self, event: EventData) -> None:
        pb = event.widget
        state = pb.component_state
        if state.is_asc2:
            Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1).send()
        else:
            if state.tmcc_id in self._released_events:
                event = self._released_events[state.tmcc_id]
                self._released_events[state.tmcc_id].clear()
            else:
                self._released_events[state.tmcc_id] = event = Event()
            _ = MomentaryActionHandler(pb, event, state, 0.2)

    def when_released(self, event: EventData) -> None:
        state = event.widget.component_state
        if state.is_asc2:
            Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).send()
        else:
            state = event.widget.component_state
            self._released_events[state.tmcc_id].set()
