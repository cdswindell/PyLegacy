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
    def __init__(self, gui: GuiZeroBase):
        self._gui = gui
        self._sync_watcher = None
        self._sync_state = None
        self._reload_btn = None

    # noinspection PyTypeChecker
    def build(self, body: Box):
        """Builds the 2-column grid layout for the admin popup."""
        admin_box = Box(body, layout="grid", border=1)
        for i in range(2):
            admin_box.tk.grid_columnconfigure(i, weight=1, uniform="stateinfo")

        aw, _ = self._gui.calc_image_box_size()
        admin_box.tk.config(width=aw)

        col_width = int(aw / 2)

        # noinspection PyTypeChecker
        tb = TitleBox(
            admin_box,
            text="Base 3 Database",
            layout="grid",  # use grid INSIDE the TitleBox
            grid=[0, 0],
            width="fill",
            align="top",
        )
        tb.text_size = self._gui.s_10
        tb.tk.grid_configure(column=0, row=0, columnspan=1, rowspan=1, sticky="ew")
        tb.tk.config(width=col_width)
        tb.tk.pack_propagate(False)

        # Let the internal grid column stretch so the TextBox can fill
        tb.tk.grid_columnconfigure(0, weight=1)

        self._sync_state = pb = PushButton(admin_box, text="Loaded", grid=[0, 0], width="fill")
        pb.bg = "green" if self._gui.sync_state.is_synchronized else "white"
        pb.text_bold = True
        pb.text_size = self._gui.s_18
        pb.tk.config(justify="center", anchor="n", width=col_width)  # borderless

        self._reload_btn = HoldButton(
            tb,
            text="Reload",
            grid=[1, 0],
            on_hold=(self._gui.do_tmcc_request, [TMCC1SyncCommandEnum.RESYNC]),
            text_bold=True,
            text_size=self._gui.s_18,
            enabled=self._gui.sync_state.is_synchronized,
        )

        # setup sync watcher to manage button state
        self._sync_watcher = StateWatcher(self._gui.sync_state, self._on_sync_state)

    def _on_sync_state(self) -> None:
        if self._gui.sync_state.is_synchronized:
            self._sync_state.text = "Loaded"
            self._sync_state.bg = "green"
            self._reload_btn.enable()
        elif self._gui.sync_state.is_synchronizing:
            self._sync_state.text = "Loading..."
            self._sync_state.bg = "white"
            self._reload_btn.disable()
