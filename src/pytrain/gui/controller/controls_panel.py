#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The controls help screen: what every button, stick and chord currently does.

Content comes from the loaded :class:`ControlProfile`, so a user who passes
``-controller_profile`` to ``make_gui`` sees their own bindings rather than the bundled
ones. See :mod:`control_labels` for how a binding becomes English.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from guizero import Box, Text, TitleBox

from .control_labels import ControlSection, controls_summary
from .steam_deck_input import ControlProfile

if TYPE_CHECKING:
    from ..guizero_base import GuiZeroBase

log = logging.getLogger(__name__)

CONTROLS_TITLE = "Controls"
# Sections are laid out in this many columns per page. The overlay spans both panes (it
# is gridded across the whole of SteamDeckGui.body), so four columns fit the Deck's
# 1280px where three was all a 632px pane allowed.
COLUMNS = 4
# Rows a single column can show before the next section starts a new column. A section
# header costs one row on top of its entries. Retuned when the text grew to ENTRY_SIZE:
# rows are ~1.6x taller, so fewer fit. Sized so the bundled profile fits one page *and*
# its 14-entry Buttons section is not split into a 2-row continuation.
ROWS_PER_COLUMN = 15

# Text sizes. The Deck GUI is built with scale_by=1.0, so these are points as written.
# Entries were s_10, which was legible on a desk and not at arm's length on a handheld.
TITLE_SIZE = 24
SECTION_SIZE = 14
ENTRY_SIZE = 16
FOOTNOTE_SIZE = 12

# Palette. Kept in the app's existing family: FOCUS_COLOR (#3B82F6) is the Deck GUI's
# accent, and the greys match the popup chrome PopupManager already uses.
KEYCAP_BG = "#E2E8F0"
KEYCAP_FG = "#1D4ED8"
ENTRY_FG = "#1F2937"
SECTION_FG = "#334155"
FOOTNOTE_FG = "#6B7280"


class ControlsPanel:
    """Content of the controls help screen.

    Deliberately *not* an OverlayPanel: those are built by PopupManager, which belongs to
    an EngineGui and can only parent an overlay inside that pane. This panel spans both
    panes, so SteamDeckGui owns its overlay and calls build() to fill it.
    """

    def __init__(self, gui: "GuiZeroBase", profile: ControlProfile | None):
        self._gui = gui
        self._profile = profile
        self._page = 0
        self._pages: tuple[tuple[tuple[ControlSection, ...], ...], ...] = ()
        self._page_box = None
        self._page_label = None

    @property
    def gui(self) -> "GuiZeroBase":
        return self._gui

    @property
    def profile(self) -> ControlProfile | None:
        return self._profile

    @property
    def page_count(self) -> int:
        return len(self._pages)

    @property
    def page(self) -> int:
        return self._page

    def paginate(self) -> tuple[tuple[tuple[ControlSection, ...], ...], ...]:
        """Group sections into columns, and columns into pages.

        A custom profile can bind far more than the bundled one, so the screen has to
        cope with overflowing rather than silently dropping the tail: sections fill
        columns, ``COLUMNS`` columns make a page, and the D-pad moves between pages.
        """
        profile = self.profile
        if profile is None:
            return ()
        columns: list[list[ControlSection]] = [[]]
        used = 0
        for section in self._split_to_fit(controls_summary(profile)):
            cost = len(section.entries) + 1  # header row
            if used and used + cost > ROWS_PER_COLUMN:
                columns.append([])
                used = 0
            columns[-1].append(section)
            used += cost
        pages = [
            tuple(tuple(column) for column in columns[start : start + COLUMNS])
            for start in range(0, len(columns), COLUMNS)
        ]
        return tuple(pages)

    @staticmethod
    def _split_to_fit(sections: tuple[ControlSection, ...]) -> list[ControlSection]:
        """Break any section taller than a column into continuation chunks.

        Without this, a custom profile that binds every button produces one section
        taller than the screen and the tail is simply clipped -- a silent cap, and the
        worst kind, because a clipped help screen looks complete.
        """
        capacity = ROWS_PER_COLUMN - 1  # the header takes a row
        chunks: list[ControlSection] = []
        for section in sections:
            entries = section.entries
            if len(entries) <= capacity:
                chunks.append(section)
                continue
            for start in range(0, len(entries), capacity):
                title = section.title if start == 0 else f"{section.title} (cont.)"
                chunks.append(ControlSection(title, entries[start : start + capacity], section.fixed))
        return chunks

    def build(self, body: Box) -> None:
        self._pages = self.paginate()
        self._page = min(self._page, max(0, self.page_count - 1))
        self._page_box = Box(body, align="top", layout="grid")
        self._render_page()
        # "*" marks the sections a custom profile cannot change: the D-pad and the
        # context-sensitive remaps are handled by DeckInputRouter, not the profile.
        note = Text(body, text="* fixed, not set by the controller profile", align="top")
        note.text_size = FOOTNOTE_SIZE
        note.text_color = FOOTNOTE_FG
        self.gui.cache(note)

    def turn_page(self, forward: bool = True) -> None:
        """Move a page and redraw. Wraps, so paging never dead-ends."""
        if self.page_count <= 1:
            return
        self._page = (self._page + (1 if forward else -1)) % self.page_count
        self._render_page()

    def _render_page(self) -> None:
        box = self._page_box
        if box is None:
            return
        for child in list(box.children):
            child.destroy()
        if not self._pages:
            Text(box, text="No controller profile loaded.", grid=[0, 0], size=self.gui.s_12)
            return
        for index, column in enumerate(self._pages[self._page]):
            self._render_column(box, column, index)
        if self.page_count > 1:
            self._page_label = Text(
                box,
                text=f"Page {self._page + 1} of {self.page_count}   (D-pad up/down)",
                grid=[0, 1, COLUMNS, 1],
                size=FOOTNOTE_SIZE,
                color=FOOTNOTE_FG,
            )

    def _render_column(self, parent: Box, sections: tuple[ControlSection, ...], column: int) -> None:
        host = self.gui
        holder = Box(parent, grid=[column, 0], align="top", layout="auto")
        for section in sections:
            title = section.title if not section.fixed else f"{section.title} *"
            tb = TitleBox(holder, text=title, layout="grid", align="top", width="fill")
            tb.text_size = SECTION_SIZE
            tb.text_color = SECTION_FG
            tb.text_bold = True
            for row, entry in enumerate(section.entries):
                self._render_entry(tb, entry, row)
            host.cache(tb)

    def _render_entry(self, parent: TitleBox, entry, row: int) -> None:
        # The input is drawn as a raised keycap so the eye can find "L1" or "View"
        # without reading the whole line -- this is a reference table, scanned rather
        # than read.
        name = Text(parent, text=f" {entry.input} ", grid=[0, row], align="left", size=ENTRY_SIZE)
        name.text_bold = True
        name.text_color = KEYCAP_FG
        name.bg = KEYCAP_BG
        name.tk.config(relief="raised", borderwidth=1)
        name.tk.grid_configure(padx=(4, 8), pady=2, sticky="w")

        text = entry.action if not entry.note else f"{entry.action}  ({entry.note})"
        action = Text(parent, text=text, grid=[1, row], align="left", size=ENTRY_SIZE)
        action.text_color = ENTRY_FG
        action.tk.grid_configure(padx=(0, 6), pady=2, sticky="w")
        self.gui.cache(name, action)
