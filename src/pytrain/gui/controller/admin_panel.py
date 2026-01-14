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
from ..guizero_base import GuiZeroBase


class AdminPanel:
    def __init__(self, gui: GuiZeroBase):
        self._gui = gui
        self._sync_watcher = None
        self._sync_state = None

    def build(self, body: Box):
        """Builds the 2-column grid layout for the admin popup."""
        admin_box = Box(body, layout="grid", border=1)
        for i in range(2):
            admin_box.tk.grid_columnconfigure(i, weight=1, uniform="stateinfo")

        aw, _ = self._gui.calc_image_box_size()
        admin_box.tk.config(width=aw)

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
        self._sync_state = pb = PushButton(tb, text="Loaded", grid=[0, 0])
        pb.bg = "green" if self._gui.sync_state.is_synchronized else "white"
        pb.text_bold = True
        pb.text_size = self._gui.s_18

        # setup sync watcher to manage button state
        self._sync_watcher = StateWatcher(self._gui.sync_state, self._on_sync_state)

    def _on_sync_state(self) -> None:
        if self._gui.sync_state.is_synchronized:
            self._sync_state.text = "Loaded"
            self._sync_state.bg = "green"
        elif self._gui.sync_state.is_synchronizing:
            self._sync_state.text = "Loading..."
            self._sync_state.bg = "white"
