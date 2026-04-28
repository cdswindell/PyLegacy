#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from typing import TYPE_CHECKING

from guizero import Box, Text

from .overlay_panel import OverlayPanel
from ..components.hold_button import HoldButton
from ..components.spinner import Spinner
from ...db.engine_state import EngineState

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class SpeedLimitPanel(OverlayPanel):
    def __init__(self, host: "EngineGui", title: str = "Set/Clear Speed Limit") -> None:
        super().__init__(host, title)
        self._cur_speed_limit = self._new_speed_limit = None
        self._clear_btn = self._set_btn = None

    def build(self, body: Box):
        host = self._gui

        # controls
        sp = Box(body, border=0)
        sp.tk.config(height=host.button_size // 5)
        host.cache(sp)

        parent = Box(body, layout="grid", border=0)
        aw = host.width
        parent.tk.config(width=aw)

        # first row, display current speed limit and clear button
        lbl = Text(parent, text="Current Limit:", grid=[0, 0], align="right")
        lbl.text_size = host.s_20
        host.cache(lbl)

        self._cur_speed_limit = csl = Text(parent, "", grid=[1, 0])
        csl.text_size = host.s_20
        csl.tk.grid_configure(sticky="")  # centered in cell
        csl.tk.config(justify="center", anchor="center")

        self._clear_btn = btn = HoldButton(parent, text="Clear", grid=[2, 0], align="bottom")
        btn.text_size = host.s_20
        btn.tk.config(
            borderwidth=3,
            relief="raised",
            highlightthickness=1,
            highlightbackground="black",
            padx=6,
            pady=4,
            activebackground="#e0e0e0",
            background="#f7f7f7",
        )
        btn.tk.grid_configure(padx=20, pady=20)

        # second row, set the new speed limit
        lbl = Text(parent, text="New Limit:", grid=[0, 1], align="right")
        lbl.text_size = host.s_20
        host.cache(lbl)

        self._new_speed_limit = nsl = Spinner(parent, grid=[1, 1], text_size=host.s_20, min_value=1, max_value=199)
        nsl.tk.grid_configure(sticky="")  # centered in cell

        for i in range(3):
            parent.tk.grid_columnconfigure(i, weight=1, uniform="speed_limit")

    def configure(self, state: EngineState) -> None:
        sp, _, sl, _ = state.speeds
        self._cur_speed_limit.value = f"{sl}" if sl is not None else "Not Set"
        self._clear_btn.enabled = sl and sl > 0
        self._new_speed_limit.value = sp

        if state.is_legacy:
            self._new_speed_limit.configure(min_value=1, max_value=199)
        else:
            self._new_speed_limit.configure(min_value=1, max_value=31)
