#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box, Text

from .engine_gui_conf import AUX2_KEY, CAB_KEY, DIESEL_LIGHTS, STEAM_LIGHTS
from ..components.hold_button import HoldButton
from ...db.engine_state import EngineState


class LightingPanel:
    def __init__(self, gui):
        self._gui = gui
        self._diesel_opts = None
        self._steam_opts = None
        self._overlay = None

    @property
    def overlay(self) -> Box:
        if self._overlay is None:
            # noinspection PyProtectedMember
            self._overlay = self._gui._popup.create_popup("Lighting", self.build)
        return self._overlay

    def configure(self, state: EngineState):
        if state and state.is_steam:
            self._steam_opts.show()
            self._diesel_opts.hide()
        else:
            self._diesel_opts.show()
            self._steam_opts.hide()

    def build(self, body: Box):
        host = self._gui

        # cab light
        master_box = Box(body, layout="grid", border=1)
        aw, _ = self._gui.calc_image_box_size()
        master_box.tk.config(width=aw)

        cell = Box(master_box, layout="auto", grid=[0, 0], align="bottom", visible=True)
        cell.tk.configure(
            width=host.button_size,
            height=host.button_size,
        )
        cell.tk.pack_propagate(False)
        master_box.tk.grid_columnconfigure(0, weight=1, minsize=host.button_size + 20)

        btn = HoldButton(
            cell,
            text=AUX2_KEY,
            text_size=host.s_18,
            text_bold=True,
            command=host.on_engine_command,
            args=["AUX2_OPTION_ONE"],
        )
        btn.tk.config(
            height=host.button_size,
            width=host.button_size,
            borderwidth=1,
            compound="center",
            anchor="center",
            padx=0,
            pady=0,
            bd=1,
            relief="solid",
            highlightthickness=1,
        )
        host.cache(btn)

        cell = Box(master_box, layout="auto", grid=[1, 0], align="bottom", visible=True)
        cell.tk.configure(
            width=host.button_size,
            height=host.button_size,
        )
        cell.tk.pack_propagate(False)
        _ = Text(cell, text=" ")

        cell = Box(master_box, layout="auto", grid=[2, 0], align="bottom", visible=True)
        cell.tk.configure(
            width=host.button_size,
            height=host.button_size,
        )
        cell.tk.pack_propagate(False)
        master_box.tk.grid_columnconfigure(2, weight=1, minsize=host.button_size + 20)

        btn = HoldButton(
            cell,
            text=CAB_KEY,
            text_size=host.s_18,
            text_bold=True,
            command=host.on_engine_command,
            args=[("CAB_AUTO", "AUX2_OPT_ONE")],
        )

        btn.tk.config(
            height=host.button_size,
            width=host.button_size,
            borderwidth=1,
            compound="center",
            anchor="center",
            padx=0,
            pady=0,
            bd=1,
            relief="solid",
            highlightthickness=1,
        )
        host.cache(btn)

        # diesel options
        self._diesel_opts = host.make_combo_panel(body, DIESEL_LIGHTS)

        # steam options
        self._steam_opts = host.make_combo_panel(body, STEAM_LIGHTS)
        self._steam_opts.hide()
