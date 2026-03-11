#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from typing import TYPE_CHECKING, cast

from guizero import Box, CheckBox, TitleBox

from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from ..components.checkbox_group import CheckBoxGroup
from ..components.touch_list_box import TouchListBox
from ..guizero_base import LIONEL_BLUE, LIONEL_ORANGE
from ...db.accessory_state import AccessoryState
from ...db.engine_state import EngineState
from ...protocol.constants import CommandScope

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

SORT_OPTS = [
    ["Name", 0],
    ["Road #", 1],
    ["TMCC ID", 2],
]


class CatalogPanel:
    def __init__(self, gui: "EngineGui", width: int, height: int):
        self._gui = gui
        self._width = width
        self._height = height
        self._scope = None
        self._state_store = self._gui.state_store
        self._catalog = None
        self._sort_btns = self._sel_btns = self._sel_box = None
        self._scoped_sort_order = {}
        self._scoped_selection = {}
        self._skip_update = False
        self._entry_state_map = {}
        self._overlay = None
        self._width_scale_factor = 3.375
        self._sel_1_btn = self._sel_2_btn = self._sel_3_btn = None
        self._configured_acc_labels: list[str] | None = None
        self._configured_acc_dict: dict[str, ConfiguredAccessoryAdapter] | None = None

    @property
    def overlay(self) -> Box:
        if self._overlay is None:
            # noinspection PyProtectedMember, PyUnresolvedReferences
            self._overlay = self._gui._popup.create_popup("Catalog", self.build)
        return self._overlay

    def build(self, body: Box) -> None:
        catalog_box = Box(body, border=1, align="top")
        catalog_box.tk.config(width=self._width)

        # sort
        sb = Box(catalog_box, align="top")
        sb.tk.config(width=self._width)
        tb = TitleBox(
            sb,
            text="Sort By",
            layout="grid",  # use grid INSIDE the TitleBox
            align="top",
            width=self._width,
            height=int(self._gui.button_size * 0.8),
        )
        tb.text_size = self._gui.s_10
        tb.tk.config(width=self._width)
        tb.tk.pack_propagate(False)

        self._sort_btns = CheckBoxGroup(
            tb,
            size=self._gui.s_18,
            grid=[0, 0, 2, 1],
            options=SORT_OPTS,
            selected=str(0),
            horizontal=True,
            align="top",
            width=int(self._width / self._width_scale_factor),
            padx=10,
            pady=6,
            style="radio",
            command=self.on_sort,
        )

        # select options
        self._sel_box = sb = Box(catalog_box, align="top")
        sb.tk.config(width=self._width)
        self._sel_btns = tb = TitleBox(
            sb,
            text="Show",
            layout="grid",  # use grid INSIDE the TitleBox
            align="top",
            width=self._width,
            height=int(self._gui.button_size * 0.8),
        )
        tb.text_size = self._gui.s_10
        tb.tk.config(width=self._width)
        tb.tk.pack_propagate(False)

        self._sel_1_btn = CheckBox(tb, text="Diesel", grid=[0, 0])
        self._sel_2_btn = CheckBox(tb, text="Steam", grid=[1, 0])
        self._sel_3_btn = CheckBox(tb, text="Other", grid=[2, 0])

        for cb in (self._sel_1_btn, self._sel_2_btn, self._sel_3_btn):
            cb.value = 0
            cb.update_command(self.on_sort)
            CheckBoxGroup.decorate_checkbox(
                cb,
                self._gui.s_18,
                padx=10,
                pady=6,
                width=int(self._width / self._width_scale_factor),
            )

        # catalog
        self._catalog = lb = TouchListBox(
            catalog_box,
            items=[],
            scrollbar=True,
            on_hold_select=self.on_select,
        )
        lb.text_size = self._gui.s_24
        lb.bg = "#f7f7f7"

        tk_listbox = lb.children[0].tk
        tk_listbox.config(width=21, height=10)

        tk_scrollbar = lb.children[1].tk
        tk_scrollbar.config(
            width=50,
            troughcolor=LIONEL_BLUE,
            activebackground=LIONEL_ORANGE,  # bright Lionel orange for the handle
            bg="lightgrey",
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,
        )  # pixels

    def configure(self, scope: CommandScope) -> None:
        assert self.overlay  # force creation of panel

        # Updates catalog entries based on sort order
        if self._scope != scope:
            # configure the selection buttons and reset them to all on
            self.configure_selection_btns(scope)

            # restore sort order
            sort_order = self._scoped_sort_order[scope] if scope in self._scoped_sort_order else 0
            self._set_sort_order_widget(sort_order)

            # rebuild catalog
            self._catalog.clear()
            self._entry_state_map.clear()
            # include configured accessories, if requested
            need_separator = False
            if scope == CommandScope.ACC and self._sel_1_btn.value == 1:
                self._harvest_configured_accessories()
                if self._configured_acc_labels:
                    for label in self._configured_acc_labels:
                        self._catalog.append(label)
                    self._entry_state_map.update(self._configured_acc_dict)
                    need_separator = True
            states = self.apply_selection_filter(scope, self._state_store.get_all(scope))
            if sort_order == 0:
                states.sort(key=lambda x: x.name)
            elif sort_order == 1:
                states.sort(key=lambda x: x.road_number)
            elif sort_order == 2:
                states.sort(key=lambda x: x.tmcc_id)
            for state in states:
                if sort_order == 0:
                    entry = f"{state.name}"
                elif sort_order == 1:
                    entry = f"{state.road_number}: {state.road_name}"
                elif sort_order == 2:
                    if scope in {CommandScope.ACC, CommandScope.SWITCH, CommandScope.ROUTE}:
                        entry = f"{state.tmcc_id:02d}: {state.name}"
                    else:
                        entry = f"{state.tmcc_id}: {state.name}"
                else:
                    entry = None
                if entry:
                    if need_separator:
                        self._catalog.append("-" * 30)
                        need_separator = False
                    self._entry_state_map[entry] = state
                    self._catalog.append(entry)
            self._scope = scope

    def configure_selection_btns(self, scope: CommandScope):
        if scope in {CommandScope.SWITCH, CommandScope.ROUTE}:
            self._sel_box.hide()
        else:
            if scope not in self._scoped_selection:
                self._scoped_selection[scope] = (1, 1, 1)
            btn_values = self._scoped_selection[scope]
            for i, cb in enumerate((self._sel_1_btn, self._sel_2_btn, self._sel_3_btn)):
                cb.value = btn_values[i]
            if scope == CommandScope.ACC:
                self._sel_1_btn.text = "Op Accs"
                self._sel_2_btn.text = "LCS"
                self._sel_3_btn.text = "Other"
            else:
                self._sel_1_btn.text = "Diesel"
                self._sel_2_btn.text = "Steam"
                self._sel_3_btn.text = "Other"
            self._sel_box.show()

    def _harvest_configured_accessories(self) -> None:
        if self._configured_acc_labels is None:
            self._configured_acc_labels = []
            self._configured_acc_dict = {}
            if self._gui.accessories.has_any():
                # Maps configured accessory labels to accessory instances
                for k, v in self._gui.accessories.configured_by_label_map().items():
                    if k and v:
                        v = v[0] if isinstance(v, list) else v
                        self._configured_acc_labels.append(v.label)
                        self._configured_acc_dict[v.label] = self._gui.accessory_provider.get(v)
                self._configured_acc_labels.sort()

    @property
    def title(self) -> str:
        return self._scope.plural if self._scope else "N/A"

    def on_sort(self) -> None:
        self._scoped_sort_order[self._scope] = int(self._sort_btns.value)
        self._scoped_selection[self._scope] = (self._sel_1_btn.value, self._sel_2_btn.value, self._sel_3_btn.value)
        if self._skip_update:
            return
        scope = self._scope
        self._scope = None
        self.configure(scope)

    def _set_sort_order_widget(self, sort_order: int) -> None:
        try:
            self._skip_update = True
            self._sort_btns.value = str(sort_order)
        finally:
            self._skip_update = False

    # noinspection PyUnusedLocal
    def on_select(self, idx: int, item: str) -> None:
        from ...db.component_state import ComponentState

        state = self._entry_state_map.get(item, None)
        if isinstance(state, ComponentState):
            self._gui.update_component_info(state.address)
        elif isinstance(state, ConfiguredAccessoryAdapter):
            # we want to make sure we activate *this* accessory; if the configured
            # accessory's activated TMCC ID maps to multiple accessories, like a
            # master power button would, choose another
            activated_tmcc_id = state.tmcc_id
            accs = self._gui.accessory_provider.adapters_for_tmcc_id(activated_tmcc_id)
            # Selects alternate TMCC ID if multiple accessories exist
            if accs and len(accs) > 1:
                if len(state.tmcc_ids) > 1:
                    state.activate_tmcc_id(state.tmcc_ids[-1])
            self._gui.update_component_info(state.tmcc_id)

    def apply_selection_filter(self, scope, states):
        if scope in {CommandScope.SWITCH, CommandScope.ROUTE}:
            return states

        if scope == CommandScope.ACC:
            sel_lcs = self._sel_2_btn.value == 1
            sel_other = self._sel_3_btn.value == 1

            def allowed(state: AccessoryState) -> bool:
                return (sel_lcs and state.is_lcs) or (sel_other and not state.is_lcs)

            return [s for s in states if allowed(cast(AccessoryState, s))]
        else:
            sel_diesel = self._sel_1_btn.value == 1
            sel_steam = self._sel_2_btn.value == 1
            sel_other = self._sel_3_btn.value == 1

            def allowed(state: EngineState) -> bool:
                return (
                    (sel_diesel and state.is_diesel)
                    or (sel_steam and state.is_steam)
                    or (sel_other and not state.is_diesel and not state.is_steam)
                )

            return [s for s in states if allowed(cast(EngineState, s))]
