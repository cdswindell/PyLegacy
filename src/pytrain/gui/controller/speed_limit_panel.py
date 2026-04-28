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
from .state_info_overlay import StateInfoOverlay
from ..components.hold_button import HoldButton
from ...db.engine_state import EngineState

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class SpeedLimitPanel(OverlayPanel):
    def __init__(self, host: "EngineGui", title: str = "Set/Clear Speed Limit") -> None:
        super().__init__(host, title)
        self._cur_speed_limit = None
        self._clear_btn = None

    def build(self, body: Box):
        host = self._gui

        # cab light
        parent = Box(body, layout="grid", border=1)
        aw = host.width
        parent.tk.config(width=aw)

        # first row, display current speed limit and clear button
        lbl = Text(parent, text="Current Limit:", grid=[0, 0], align="right")
        lbl.text_size = host.s_20
        host.cache(lbl)

        _, self._cur_speed_limit = StateInfoOverlay.make_field(
            host=host,
            parent=parent,
            title=" ",
            grid=[1, 0],
            max_cols=3,
            center=True,
            text_size=host.s_20,
        )

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

        for i in range(3):
            parent.tk.grid_columnconfigure(i, weight=1, uniform="speed_limit")

    def configure(self, state: EngineState) -> None:
        _, _, sl, _ = state.speeds
        self._cur_speed_limit.value = f"{sl}" if sl is not None else "Not Set"
        self._clear_btn.enabled = sl and sl > 0
