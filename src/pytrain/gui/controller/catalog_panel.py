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
from guizero import Box, Text, TitleBox

from ...protocol.constants import CommandScope
from ..checkbox_group import CheckBoxGroup
from ..guizero_base import LIONEL_ORANGE, GuiZeroBase
from ..touch_list_box import TouchListBox

SORT_OPTS = [
    ["Name", 0],
    ["Road #", 1],
    ["TMCC ID", 2],
]


class CatalogPanel:
    def __init__(self, gui: GuiZeroBase, width: int, height: int):
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
            troughcolor="#003366",
            activebackground=LIONEL_ORANGE,  # bright Lionel orange for the handle
            bg="lightgrey",
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,
        )  # pixels

    def update(self, scope: CommandScope) -> None:
        if self._scope != scope:
            sort_order = self._scoped_sort_order[scope] if scope in self._scoped_sort_order else 0
            self._set_sort_order_widget(sort_order)
            self._catalog.clear()
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

    @property
    def title(self) -> str:
        return self._scope.plural if self._scope else "N/A"

    def on_sort(self) -> None:
        self._scoped_sort_order[self._scope] = int(self._sort_btns.value)
        if self._skip_update:
            return
        scope = self._scope
        self._scope = None
        self.update(scope)

    def _set_sort_order_widget(self, sort_order: int) -> None:
        try:
            self._skip_update = True
            self._sort_btns.value = str(sort_order)
        finally:
            self._skip_update = False

    # noinspection PyUnusedLocal
    def on_select(self, idx: int, item: str) -> None:
        from ...db.component_state import ComponentState
        from .engine_gui import EngineGui

        state = self._entry_state_map.get(item, None)

        if isinstance(state, ComponentState) and isinstance(self._gui, EngineGui):
            self._gui.update_component_info(state.address)
