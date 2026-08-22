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
from .overlay_panel import OverlayPanel
from .steam_deck_input import ControlProfile

if TYPE_CHECKING:
    from .engine_gui import EngineGui

log = logging.getLogger(__name__)

CONTROLS_TITLE = "Controls"
# Sections are laid out in this many columns per page. The panel spans the whole window
# rather than one pane (see full_window), so there is room for four columns across the
# Deck's 1280px rather than the three a 632px pane allowed.
COLUMNS = 4
# Rows a single column can show before the next section starts a new column. A section
# header costs one row on top of its entries. Sized so the bundled profile lands on a
# single page -- at 15 its last one-entry section spilled onto a second page, which
# looks broken even though it paginates correctly.
ROWS_PER_COLUMN = 18


class ControlsPanel(OverlayPanel):
    def __init__(self, gui: "EngineGui", profile: ControlProfile | None):
        # The profile is passed in rather than looked up: it belongs to the hosting
        # SteamDeckGui, and an EngineGui pane has no reference back to its host.
        super().__init__(gui, CONTROLS_TITLE)
        self._profile = profile
        self._page = 0
        self._pages: tuple[tuple[tuple[ControlSection, ...], ...], ...] = ()
        self._page_box = None
        self._page_label = None

    @property
    def profile(self) -> ControlProfile | None:
        return self._profile

    @property
    def full_window(self) -> bool:
        # A pane is half the screen; a two-column table of every binding is cramped in
        # it. This is a reference table, not a pane-scoped control, so it spans both.
        return True

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
                size=self.gui.s_10,
            )

    def _render_column(self, parent: Box, sections: tuple[ControlSection, ...], column: int) -> None:
        host = self.gui
        holder = Box(parent, grid=[column, 0], align="top", layout="auto")
        for section in sections:
            title = section.title if not section.fixed else f"{section.title} *"
            tb = TitleBox(holder, text=title, layout="grid", align="top", width="fill")
            tb.text_size = host.s_10
            for row, entry in enumerate(section.entries):
                name = Text(tb, text=entry.input, grid=[0, row], align="left", size=host.s_10)
                name.text_bold = True
                action = entry.action if not entry.note else f"{entry.action}  ({entry.note})"
                Text(tb, text=action, grid=[1, row], align="left", size=host.s_10)
            host.cache(tb)

    @property
    def has_footer(self) -> bool:
        return True

    def build_footer(self, footer: Box) -> None:
        # "*" marks the sections a custom profile cannot change: the D-pad and the
        # context-sensitive remaps are handled by DeckInputRouter, not the profile.
        note = Text(footer, text="* fixed, not set by the controller profile", align="left")
        note.text_size = self.gui.s_10
        self.gui.cache(note)
