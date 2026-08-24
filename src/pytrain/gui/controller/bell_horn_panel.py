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

from .engine_gui_conf import CYCLE_KEY, PLAY_KEY, PLAY_PAUSE_KEY, PLAY_PAUSE_KEY_COMPACT
from .overlay_panel import OverlayPanel
from ...utils.path_utils import find_file

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class BellHornPanel(OverlayPanel):
    def __init__(self, gui: "EngineGui", title: str = "Bell/Horn Options"):
        super().__init__(gui, title)

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
        compact = bool(getattr(host, "compact", False))
        _, bp = host.make_keypad_button(
            overlay,
            # Two glyphs for one button: U+23F8 is claimed by a color emoji font on the Deck. See
            # the note beside these constants.
            PLAY_PAUSE_KEY_COMPACT if compact else PLAY_PAUSE_KEY,
            0,
            2,
            # The only key on either row that needs its size named. It is four characters wide
            # against one for every other key, and at the shared s_30 that _build_keypad_button
            # would otherwise pick it filled its cell edge to edge -- a cell being a fixed square
            # with pack_propagate off, so the label had no margin left and nowhere to grow into.
            # Compact only: portrait's glyph is a character shorter and fits at the shared size,
            # and passing nothing leaves that path exactly as it was.
            size=host.s_24 if compact else None,
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
