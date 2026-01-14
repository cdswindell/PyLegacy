#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from guizero import Box, PushButton, TitleBox

from ...db.state_watcher import StateWatcher
from ...protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum
from ..guizero_base import GuiZeroBase
from ..hold_button import HoldButton


class AdminPanel:
    def __init__(self, gui: GuiZeroBase, width: int, height: int):
        self._gui = gui
        self._width = width
        self._height = height
        self._sync_watcher = None
        self._sync_state = None
        self._reload_btn = None

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def build(self, body: Box):
        """Builds the 2-column grid layout for the admin popup."""
        admin_box = Box(body, border=1, align="top", layout="grid")
        admin_box.tk.config(width=self._width)

        # noinspection PyTypeChecker
        tb = TitleBox(
            admin_box,
            text="Base 3 Database",
            layout="grid",  # use grid INSIDE the TitleBox
            align="top",
            grid=[0, 0, 2, 1],
            width=self._width,
            height=self._gui.button_size,
        )
        tb.text_size = self._gui.s_10
        tb.tk.grid_configure(column=0, row=0, columnspan=2, rowspan=1)
        tb.tk.config(width=self._width)
        tb.tk.pack_propagate(False)
        tb.tk.grid_columnconfigure(0, weight=1)

        self._sync_state = pb = PushButton(
            tb,
            text="Loaded",
            grid=[0, 0],
            width=10,
            padx=self._gui.text_pad_x,
            pady=self._gui.text_pad_y,
        )
        pb.bg = "green" if self._gui.sync_state.is_synchronized else "white"
        pb.text_bold = True
        pb.text_size = self._gui.s_18

        self._reload_btn = pb = HoldButton(
            tb,
            text="Reload",
            grid=[1, 0],
            on_hold=(self._gui.do_tmcc_request, [TMCC1SyncCommandEnum.RESYNC]),
            width=10,
            text_bold=True,
            text_size=self._gui.s_18,
            enabled=self._gui.sync_state.is_synchronized,
            padx=self._gui.text_pad_x,
            pady=self._gui.text_pad_y,
        )
        pb.tk.config(
            borderwidth=3,
            relief="raised",
            highlightthickness=1,
            highlightbackground="black",
            activebackground="#e0e0e0",
            background="#f7f7f7",
        )

        # setup sync watcher to manage button state
        self._sync_watcher = StateWatcher(self._gui.sync_state, self._on_sync_state)

    def _on_sync_state(self) -> None:
        if self._gui.sync_state.is_synchronized:
            self._sync_state.text = "Loaded"
            self._sync_state.bg = "green"
            self._reload_btn.enable()
        elif self._gui.sync_state.is_synchronizing:
            self._sync_state.text = "Reloading..."
            self._sync_state.bg = "white"
            self._reload_btn.disable()
