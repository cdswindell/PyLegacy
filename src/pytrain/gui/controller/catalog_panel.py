#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
#
#
from typing import TYPE_CHECKING

from guizero import Box, Text, TitleBox

from ..accessories.config import ConfiguredAccessory
from ..components.checkbox_group import CheckBoxGroup
from ..components.touch_list_box import TouchListBox
from ..guizero_base import LIONEL_BLUE, LIONEL_ORANGE
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
        self._sort_btns = None
        self._scoped_sort_order = {}
        self._skip_update = False
        self._entry_state_map = {}
        self._overlay = None
        self._configured_acc_labels: list[str] | None = None
        self._configured_acc_dict: dict[str, ConfiguredAccessory] | None = None

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
        sb = Box(catalog_box, layout="grid", align="top")
        sb.tk.config(width=self._width)
        tb = TitleBox(
            sb,
            text="Sort By",
            layout="grid",  # use grid INSIDE the TitleBox
            align="top",
            width=self._width,
            height=self._gui.button_size,
            grid=[0, 0, 2, 1],
        )
        tb.text_size = self._gui.s_10
        tb.tk.grid_configure(column=0, row=0, columnspan=2, rowspan=1, sticky="nsew")
        tb.tk.config(width=self._width)
        tb.tk.pack_propagate(False)
        tb.tk.grid_columnconfigure(0, weight=1)

        sp = Text(tb, text=" ", grid=[0, 0, 2, 1], height=1, bold=True, align="top")
        sp.text_size = self._gui.s_2
        self._sort_btns = CheckBoxGroup(
            tb,
            size=self._gui.s_18,
            grid=[0, 1, 2, 1],
            options=SORT_OPTS,
            selected=str(0),
            horizontal=True,
            align="top",
            width=int(self._width / 3.55),
            padx=14,
            pady=12,
            style="radio",
            command=self.on_sort,
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
            sort_order = self._scoped_sort_order[scope] if scope in self._scoped_sort_order else 0
            self._set_sort_order_widget(sort_order)
            self._catalog.clear()
            self._entry_state_map.clear()
            if scope == CommandScope.ACC:
                self._harvest_configured_accessories()
                if self._configured_acc_labels:
                    for label in self._configured_acc_labels:
                        self._catalog.append(label)
                    self._entry_state_map.update(self._configured_acc_dict)
                    self._catalog.append("-" * 30)
            states = self._state_store.get_all(scope)
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
                    self._entry_state_map[entry] = state
                    self._catalog.append(entry)
            self._scope = scope

    def _harvest_configured_accessories(self) -> None:
        if self._configured_acc_labels is None:
            self._configured_acc_labels = []
            self._configured_acc_dict = {}
            if self._gui.configured_accessories.has_any():
                for k, v in self._gui.configured_accessories.configured_by_label_map().items():
                    if k and v:
                        v = v[0] if isinstance(v, list) else v
                        self._configured_acc_labels.append(v.label)
                        self._configured_acc_dict[v.label] = v
                self._configured_acc_labels.sort()

    @property
    def title(self) -> str:
        return self._scope.plural if self._scope else "N/A"

    def on_sort(self) -> None:
        self._scoped_sort_order[self._scope] = int(self._sort_btns.value)
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
        elif isinstance(state, ConfiguredAccessory):
            print(state)
        else:
            print(f"Unknown state {type(state)}: {state}")
