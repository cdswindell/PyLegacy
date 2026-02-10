#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box

from .engine_gui_conf import RR_SPEED_LAYOUT
from ...db.engine_state import EngineState


class RrSpeedPanel:
    def __init__(self, gui):
        self._gui = gui
        self._rr_speed_btns = set()
        self._overlay = None

    @property
    def overlay(self) -> Box:
        if self._overlay is None:
            # noinspection PyProtectedMember
            self._overlay = self._gui._popup.create_popup("Official Rail Road Speeds", self.build)
        return self._overlay

    def configure(self, state: EngineState):
        rr_speed = state.rr_speed if state else ""
        for btn in self._rr_speed_btns:
            if rr_speed and btn.rr_speed.endswith(rr_speed.name):
                btn.bg = "green"
            else:
                btn.bg = "white"

    def build(self, body: Box):
        host = self._gui
        keypad_box = Box(body, layout="grid", border=1)
        width = int(3 * host.button_size)

        for r, kr in enumerate(RR_SPEED_LAYOUT):
            for c, op in enumerate(kr):
                label = ""
                dialog = None

                if isinstance(op, tuple):
                    if op[1].startswith("Emergency"):
                        label = op[1]
                        dialog = "EMERGENCY_CONTEXT_DEPENDENT"
                    else:
                        label = op[1] + ("\nSpeed" if op[0] != "SPEED_STOP_HOLD" else "")
                        dialog = "TOWER_" + op[0]

                cell, nb = host.make_keypad_button(
                    keypad_box,
                    label,
                    r,
                    c,
                    bolded=True,
                    size=host.s_18,
                    command=host.on_speed_command,
                    args=[op[0]],
                )
                nb.hold_threshold = 0.5

                cell.tk.config(width=width)
                nb.tk.config(width=width)

                if label.startswith("Emergency"):
                    nb.text_color = "white"
                    nb.bg = "red"
                else:
                    self._rr_speed_btns.add(nb)
                    nb.rr_speed = op[0]

                if dialog:
                    nb.on_hold = (host.on_speed_command, [f"{dialog}, {op[0]}"])
