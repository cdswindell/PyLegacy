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
from guizero import Box, ListBox, Text, TitleBox

from ...protocol.constants import CommandScope
from ..checkbox_group import CheckBoxGroup
from ..guizero_base import GuiZeroBase

SORT_OPTS = [
    ["By Name", 0],
    ["By TMCC ID", 1],
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
            size=self._gui.s_20,
            grid=[0, 1, 2, 1],
            options=SORT_OPTS,
            horizontal=True,
            align="top",
            width=int(self._width / 2.2),
        )

        # catalog
        self._catalog = lb = ListBox(
            catalog_box,
            items=[],
            scrollbar=True,
            command=self.on_select,
        )
        lb.text_size = self._gui.s_24

        tk_listbox = lb.children[0].tk
        tk_listbox.config(width=21, height=10)

        tk_scrollbar = lb.children[1].tk
        tk_scrollbar.config(width=40)  # pixels

    def update(self, scope: CommandScope) -> None:
        if self._scope != scope:
            self._catalog.clear()
            for state in self._state_store.get_all(scope):
                self._catalog.append(state.name)
        self._scope = scope

    @property
    def title(self) -> str:
        return self._scope.plural if self._scope else "N/A"

    def on_select(self, item: str) -> None:
        print(f"Selected {item}")
