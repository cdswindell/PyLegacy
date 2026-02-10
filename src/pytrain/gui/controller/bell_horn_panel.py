#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box, Text

from .engine_gui_conf import CYCLE_KEY, PLAY_KEY, PLAY_PAUSE_KEY
from ...utils.path_utils import find_file


class BellHornPanel:
    def __init__(self, gui):
        self._gui = gui
        self._overlay = None

    @property
    def overlay(self) -> Box:
        if self._overlay is None:
            # noinspection PyProtectedMember
            self._overlay = self._gui._popup.create_popup("Bell/Horn Options", self.build)
        return self._overlay

    def configure(self, state):
        pass

    def build(self, body: Box):
        host = self._gui
        cs = host.button_size
        height = int(2.5 * cs)
        overlay = Box(
            body,
            layout="grid",
            align="top",
            border=1,
            height=height,
            width=6 * cs,
        )

        bt = Text(overlay, text="Bell: ", grid=[0, 0], align="left")
        bt.text_size = host.s_20
        bt.text_bold = True

        _, bc = host.make_keypad_button(
            overlay,
            CYCLE_KEY,
            0,
            1,
            align="left",
            command=host.on_engine_command,
            args=["CYCLE_BELL_TONE"],
        )
        _, bp = host.make_keypad_button(
            overlay,
            PLAY_PAUSE_KEY,
            0,
            2,
            align="left",
            command=host.on_engine_command,
            args=["RING_BELL"],
        )
        _, bon = host.make_keypad_button(
            overlay,
            "On",
            0,
            3,
            align="left",
            command=host.on_engine_command,
            args=["BELL_ON"],
        )
        _, boff = host.make_keypad_button(
            overlay,
            "Off",
            0,
            4,
            align="left",
            command=host.on_engine_command,
            args=["BELL_OFF"],
        )
        host.cache(bt)
        host.cache(bc)
        host.cache(bp)
        host.cache(bon)
        host.cache(boff)

        ht = Text(overlay, text="Horn: ", grid=[0, 1])
        ht.text_size = host.s_20
        ht.text_bold = True

        _, hc = host.make_keypad_button(
            overlay,
            CYCLE_KEY,
            1,
            1,
            align="left",
            command=host.on_engine_command,
            args=["CYCLE_HORN_TONE"],
        )
        _, hp = host.make_keypad_button(
            overlay,
            PLAY_KEY,
            1,
            2,
            align="left",
            command=host.on_engine_command,
            args=["BLOW_HORN_ONE"],
        )
        _, hrc = host.make_keypad_button(
            overlay,
            "",
            1,
            3,
            image=find_file("rail_crossing.jpg"),
            align="left",
            command=host.on_engine_command,
            args=["GRADE_CROSSING_SEQ"],
        )

        host.cache(ht)
        host.cache(hc)
        host.cache(hp)
        host.cache(hrc)
