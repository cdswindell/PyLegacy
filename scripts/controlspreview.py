#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Draw the controls help screen on its own, at Deck size, with no PyTrain behind it.

SteamDeckGui builds that screen inside a running GUI that needs a base, a state store and
a controller; none of that changes a word of what the help screen says. So this rebuilds
just the overlay -- the same header band, Close button and height budget as
SteamDeckGui._build_controls_overlay -- and hands the body to the real ControlsPanel with
the real bundled profile. What appears is what appears on the Deck, which is the point:
edits to the section order, the titles or the row budget can be looked at without a layout
or a train.

Run it from the repo:

    ../bin/python scripts/controlspreview.py

Close closes it. Up/Down page, standing in for the D-pad, should a profile ever grow past
one page. The line it prints -- band, body height, rows per column, page count -- is the
pagination arithmetic the columns were laid out to.
"""

import os
import sys

# PyTrain uses a ``src`` layout, so ``pytrain`` is not importable when it is not
# pip-installed into the interpreter running this script (the usual case here, launched
# straight out of a checkout as ``../bin/python scripts/controlspreview.py``). Put the
# repo's ``src`` on the path so the preview shows this checkout's help screen rather than
# whatever version happens to be installed.
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if os.path.isdir(os.path.join(_SRC_DIR, "pytrain")) and _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from guizero import App, Box, PushButton, Text

from pytrain.gui.controller.controls_panel import CONTROLS_TITLE, ControlsPanel
from pytrain.gui.controller.steam_deck_gui import (
    CONTROLS_BG,
    CONTROLS_BORDER_PX,
    CONTROLS_CLOSE_TEXT,
    CONTROLS_HEADER_BG,
    CONTROLS_HEADER_FALLBACK_PX,
    CONTROLS_HEADER_FG,
    CONTROLS_TITLE_SIZE,
    STEAM_DECK_HEIGHT,
    STEAM_DECK_WIDTH,
)
from pytrain.gui.controller.steam_deck_input import ControlProfile


class PreviewHost:
    """All ControlsPanel asks of its host: a widget cache and one font size."""

    s_12 = 12

    def cache(self, *widgets) -> None:
        pass


def main() -> None:
    app = App(
        title="PyTrain Controls (preview)",
        width=STEAM_DECK_WIDTH,
        height=STEAM_DECK_HEIGHT,
        layout="auto",
        bg=CONTROLS_BG,
    )

    overlay = Box(app, align="top", layout="auto")
    overlay.bg = CONTROLS_BG
    overlay.tk.config(relief="raised", borderwidth=CONTROLS_BORDER_PX)

    header = Box(overlay, align="top", width="fill")
    header.bg = CONTROLS_HEADER_BG
    close = PushButton(header, text=CONTROLS_CLOSE_TEXT, align="right", command=app.destroy)
    close.text_size = 20
    close.tk.config(
        borderwidth=3,
        relief="raised",
        highlightthickness=1,
        highlightbackground="black",
        padx=6,
        pady=4,
        activebackground="#e0e0e0",
        background="#f7f7f7",
    )
    close.tk.pack_configure(padx=(0, 12), pady=6)
    title = Text(
        header,
        text=f"{CONTROLS_TITLE}   preview",
        align="top",
        bold=True,
        size=CONTROLS_TITLE_SIZE,
        color=CONTROLS_HEADER_FG,
    )
    title.tk.config(padx=16, pady=6)

    # The row budget the columns are laid out to, derived exactly as the real screen
    # derives it: the display less the title band and the overlay's border.
    header.tk.update_idletasks()
    band = max(CONTROLS_HEADER_FALLBACK_PX, header.tk.winfo_reqheight())
    height_px = max(0, STEAM_DECK_HEIGHT - band - 2 * CONTROLS_BORDER_PX)

    body = Box(overlay, align="top", layout="auto")
    panel = ControlsPanel(PreviewHost(), ControlProfile.load(None))
    panel.build(body, height_px=height_px)
    print(
        f"band={band}px body={height_px}px rows_per_column={panel.rows_per_column} pages={panel.page_count}",
        flush=True,
    )
    # The columns the packer produced, so a section that was meant to move can be checked
    # against the row budget that produced it without reading the window.
    for page, columns in enumerate(panel.paginate()):
        for index, column in enumerate(columns):
            titles = ", ".join(section.title for section in column)
            print(f"  page {page + 1} column {index + 1}: {titles}", flush=True)

    # The D-pad pages the real screen; arrow keys stand in for it here. Bound on Tk
    # rather than through guizero's when_key_pressed, which reports the character typed --
    # and an arrow key types nothing.
    app.tk.bind("<Down>", lambda event: panel.turn_page(True))
    app.tk.bind("<Up>", lambda event: panel.turn_page(False))
    app.display()


if __name__ == "__main__":
    main()
