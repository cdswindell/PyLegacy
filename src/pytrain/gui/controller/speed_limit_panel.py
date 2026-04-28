#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from typing import TYPE_CHECKING

from guizero import Box

from .overlay_panel import OverlayPanel
from .state_info_overlay import StateInfoOverlay
from ..components.hold_button import HoldButton
from ...db.engine_state import EngineState

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class SpeedLimitPanel(OverlayPanel):
    def __init__(self, host: "EngineGui", title: str = "Speed Limit") -> None:
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
        _, self._cur_speed_limit = StateInfoOverlay.make_field(
            host=host,
            parent=parent,
            title="Current",
            grid=[0, 0],
            max_cols=2,
            center=True,
        )

        self._clear_btn = btn = HoldButton(parent, text="Clear", grid=[1, 0], align="bottom")
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
        for i in range(2):
            parent.tk.grid_columnconfigure(i, weight=1, uniform="speed_limit")

    def configure(self, state: EngineState) -> None:
        print(state)
        self._cur_speed_limit.value = state.speed_limit if state else ""
        self._clear_btn.enabled = state and state.speed_limit is not None and state.speed_limit > 0
