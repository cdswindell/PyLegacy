#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The controls help screen: what every button, stick, and chord currently does.

Content comes from the loaded :class:`ControlProfile`, so a user who passes
``-controller_profile`` to ``make_gui`` sees their own bindings rather than the bundled
ones. See :mod:`control_labels` for how a binding becomes English.
"""

from __future__ import annotations

import logging
import re
from tkinter import TclError
from tkinter import font as tkfont
from typing import TYPE_CHECKING, Callable

from guizero import Box, Text, TitleBox

from .control_labels import ControlEntry, ControlSection, controls_summary
from .steam_deck_input import ControlProfile

if TYPE_CHECKING:
    from ..guizero_base import GuiZeroBase

log = logging.getLogger(__name__)

CONTROLS_TITLE = "Controls"
# Sections are laid out in this many columns per page. Four overflowed the Deck's 1280px
# -- the overlay grew wider than the window, so its last column was clipped and its
# centre (and therefore the title and Close button) sat off screen. Three fits.
COLUMNS = 3
# Rows a single column can show before the next section starts a new column. A section
# header costs one row on top of its entries, and a wrapped entry costs two -- see
# entry_rows.
#
# This is the fallback. build() replaces it with a budget divided out of the room the
# display actually leaves, because as a constant it was only ever right for the machine
# it was calibrated on: 20 was measured by eye against a 1280x800 Deck, and a column that
# came out a row taller than that had the row taken out of whatever the packer placed
# last -- which was the Close button. It stays as the answer for when there is no Tk to
# measure with, chiefly headless tests.
ROWS_PER_COLUMN = 20
# A floor for the derived budget: a bad height measurement should cost the layout its
# balance, not shred every section into continuation chunks.
MIN_ROWS_PER_COLUMN = 4

# Text sizes. The Deck GUI is built with scale_by=1.0, so these are points as written.
# Entries were s_10, which was legible on a desk and not at arm's length on a handheld.
TITLE_SIZE = 24
SECTION_SIZE = 14
ENTRY_SIZE = 16
FOOTNOTE_SIZE = 12

# Width budget for an entry's action text, in pixels -- handed to Tk as wraplength, so
# this is what actually decides where a line breaks. Raising it past ~300 costs no extra
# width: at that point every column is already sized by its longest line or its section
# heading rather than by this budget. 320 clears the longest current string ("Boost /
# brake speed  (repeats)", measured at 276px) with room for a wider font than the one
# this was measured on.
ACTION_WRAP_PX = 320
# Rendered width of one character at ENTRY_SIZE, for predicting wraps. Measured across
# the real strings at 9.2-10.5 px/char; the high end is deliberate, because
# under-estimating means budgeting one row for a line Tk will wrap onto two -- which
# overflows the column. Over-estimating only leaves slack.
APPROX_CHAR_PX = 10.0
# Characters that fit in the budget. Derived, not written down separately: as independent
# constants they drifted apart, and a predictor that said "fits" while Tk wrapped anyway
# is exactly how a 29-character line ended up on two rows with no extra row reserved.
WRAP_CHARS = int(ACTION_WRAP_PX / APPROX_CHAR_PX)

# Vertical padding _render_entry puts on every row: pady=2, above and below.
ROW_PADDING_PX = 4
# A section heading is a TitleBox -- a Tk LabelFrame -- so it costs its label's height
# plus the frame's border, top and bottom.
TITLE_BOX_BORDER_PX = 4
# Lines under the columns that are not help rows: the "*" footnote and the page label.
# Counted against the height budget rather than left to be squeezed out of it.
FOOTER_LINES = 2
# The named font guizero's widgets inherit here: nothing in this GUI sets a family, and
# guizero's text_size keeps the family it finds -- so this is what actually gets drawn.
DEFAULT_FONT_NAME = "TkDefaultFont"
# Raised when there is no display, no interpreter, or a stand-in widget in place of a real
# one. Measuring is an improvement on estimating, never a requirement for drawing.
MEASURE_EXCEPTIONS = (AttributeError, RuntimeError, TclError, TypeError)
# A word and the whitespace before it, so a candidate line is measured with the spacing it
# will be drawn with -- "action  (note)" carries two spaces.
WORD = re.compile(r"\s*\S+")

# Palette. Kept in the app's existing family: FOCUS_COLOR (#3B82F6) is the Deck GUI's
# accent, and the greys match the popup chrome PopupManager already uses.
KEYCAP_BG = "#E2E8F0"
KEYCAP_FG = "#1D4ED8"
ENTRY_FG = "#1F2937"
SECTION_FG = "#334155"
FOOTNOTE_FG = "#6B7280"


class TextRuler:
    """How wide, and how tall, this screen's text really renders.

    Pagination has to know how many rows a column will take before a word of it is drawn,
    and it used to answer by counting characters: WRAP_CHARS fit, longer wraps. That
    predictor under-counted -- a 29-character line was budgeted one row and Tk wrapped it
    onto two -- and every row it under-counted came out of whatever was packed after the
    content. Tk can measure the exact string it is about to draw, so ask it.

    The character count survives as the fallback: a headless test still has to paginate,
    and a screen that cannot measure its font can still draw one.
    """

    def __init__(
        self,
        measure: Callable[[str], int] | None = None,
        row_px: int = 0,
        footnote_px: int = 0,
    ) -> None:
        self._measure = measure
        self._row_px = row_px
        self._footnote_px = footnote_px

    @classmethod
    def measured(cls, widget) -> "TextRuler":
        """A ruler backed by Tk's own metrics, or an estimating one if Tk cannot be asked."""
        try:
            root = getattr(widget, "tk", widget)
            family = tkfont.nametofont(DEFAULT_FONT_NAME, root=root).actual("family")
            entry = tkfont.Font(root=root, family=family, size=ENTRY_SIZE)
            heading = tkfont.Font(root=root, family=family, size=SECTION_SIZE, weight="bold")
            footnote = tkfont.Font(root=root, family=family, size=FOOTNOTE_SIZE)
            # One height for both kinds of row, and the taller of the two: the row model
            # charges a heading a single row, so charging it the shorter height would let a
            # column of headings run off the bottom of the display.
            row_px = max(entry.metrics("linespace"), heading.metrics("linespace") + TITLE_BOX_BORDER_PX)
            return cls(entry.measure, row_px + ROW_PADDING_PX, footnote.metrics("linespace"))
        except MEASURE_EXCEPTIONS as exception:
            log.debug("Controls screen cannot measure its font (%s); estimating instead", exception)
            return cls()

    @property
    def exact(self) -> bool:
        """Whether these are Tk's measurements rather than the character-count estimate."""
        return self._measure is not None and self._row_px > 0

    @property
    def footnote_px(self) -> int:
        """Height of one footer line, or 0 when unmeasured -- see rows_in."""
        return self._footnote_px

    def width(self, text: str) -> int:
        """Rendered width of ``text``, in pixels."""
        if self._measure is None:
            return int(len(text) * APPROX_CHAR_PX)
        return self._measure(text)

    def rows_in(self, height_px: int) -> int:
        """Help rows that fit in ``height_px``, or the calibrated fallback if unmeasured."""
        if not self.exact or height_px <= 0:
            return ROWS_PER_COLUMN
        return max(MIN_ROWS_PER_COLUMN, height_px // self._row_px)

    def wrapped_rows(self, text: str, budget: int = ACTION_WRAP_PX) -> int:
        """Rows Tk's word wrap will break ``text`` into within ``budget`` pixels."""
        rows = 1
        line = ""
        for match in WORD.finditer(text):
            word = match.group()
            if line and self.width(line + word) > budget:
                rows += 1
                line = word.lstrip()
            else:
                line += word
            if self.width(line) > budget:
                # A word too wide for a line of its own: Tk breaks it mid-word rather than
                # letting it overflow the column.
                rows += -(-self.width(line) // budget) - 1
                line = ""
        return rows


# Used wherever there is no widget to measure with, so the row helpers below stay callable
# without a display -- which is how the pagination tests reach them.
ESTIMATED_RULER = TextRuler()


def entry_text(entry: ControlEntry) -> str:
    """The action column as drawn: the action, with its note in parentheses."""
    return entry.action if not entry.note else f"{entry.action}  ({entry.note})"


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
        # Both are replaced in build(), which has a widget to measure with and is told how
        # much room the columns have been left.
        self._ruler = ESTIMATED_RULER
        self._rows_per_column = ROWS_PER_COLUMN

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

    @property
    def rows_per_column(self) -> int:
        """The row budget in force: derived in build(), ROWS_PER_COLUMN until then."""
        return self._rows_per_column

    def paginate(self) -> tuple[tuple[tuple[ControlSection, ...], ...], ...]:
        """Group sections into columns, and columns into pages.

        A custom profile can bind far more than the bundled one, so the screen has to
        cope with overflowing rather than silently dropping the tail: sections fill
        columns, ``COLUMNS`` columns make a page, and the D-pad moves between pages.
        """
        profile = self.profile
        if profile is None:
            return ()
        budget = self._rows_per_column
        columns: list[list[ControlSection]] = [[]]
        used = 0
        for section in self._split_to_fit(controls_summary(profile), budget, self._ruler):
            cost = self.section_rows(section, self._ruler)
            if used and used + cost > budget:
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
    def entry_rows(entry: ControlEntry, ruler: TextRuler | None = None) -> int:
        """Rows an entry will occupy once Tk has wrapped its action text."""
        return (ruler or ESTIMATED_RULER).wrapped_rows(entry_text(entry))

    @classmethod
    def section_rows(cls, section: ControlSection, ruler: TextRuler | None = None) -> int:
        """Rows a section occupies: its header plus its (possibly wrapped) entries."""
        return 1 + sum(cls.entry_rows(entry, ruler) for entry in section.entries)

    @staticmethod
    def _split_to_fit(
        sections: tuple[ControlSection, ...],
        rows_per_column: int = ROWS_PER_COLUMN,
        ruler: TextRuler | None = None,
    ) -> list[ControlSection]:
        """Break any section taller than a column into continuation chunks.

        Without this, a custom profile that binds every button produces one section
        taller than the screen and the tail is simply clipped -- a silent cap, and the
        worst kind, because a clipped help screen looks complete.
        """
        capacity = rows_per_column - 1  # the header takes a row
        chunks: list[ControlSection] = []
        for section in sections:
            if ControlsPanel.section_rows(section, ruler) <= rows_per_column:
                chunks.append(section)
                continue
            # Accumulate by rendered height, not entry count: a wrapped entry is two rows.
            batch: list[ControlEntry] = []
            used = 0
            for entry in section.entries:
                rows = ControlsPanel.entry_rows(entry, ruler)
                if batch and used + rows > capacity:
                    title = section.title if not chunks or chunks[-1].title != section.title else section.title
                    chunks.append(ControlSection(title, tuple(batch), section.fixed))
                    batch, used = [], 0
                batch.append(entry)
                used += rows
            if batch:
                chunks.append(ControlSection(section.title, tuple(batch), section.fixed))
        # Mark every chunk after the first as a continuation of its section.
        seen: set[str] = set()
        marked: list[ControlSection] = []
        for chunk in chunks:
            if chunk.title in seen:
                marked.append(ControlSection(f"{chunk.title} (cont.)", chunk.entries, chunk.fixed))
            else:
                seen.add(chunk.title)
                marked.append(chunk)
        return marked

    def build(self, body: Box, height_px: int = 0) -> None:
        """Fill ``body`` with the help columns.

        ``height_px`` is the vertical room the caller has left for them, its own chrome
        already deducted; 0 means it does not know, and the fallback budget stands.
        """
        self._ruler = TextRuler.measured(body)
        self._rows_per_column = self._rows_that_fit(height_px)
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

    def _rows_that_fit(self, height_px: int) -> int:
        """The row budget for one column, given the room the caller left it.

        The derivation is the point of measuring: a budget taller than the display is a
        column that runs off the bottom of it, and something down there gets clipped.
        """
        # The footnote and the page label sit under the columns, so they come off the
        # budget here rather than being squeezed out of it at the bottom of the screen.
        return self._ruler.rows_in(height_px - FOOTER_LINES * self._ruler.footnote_px)

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

        action = Text(parent, text=entry_text(entry), grid=[1, row], align="left", size=ENTRY_SIZE)
        action.text_color = ENTRY_FG
        # wraplength wraps instead of truncating or forcing the column wider. justify
        # keeps the second line aligned under the first rather than centred.
        action.tk.config(wraplength=ACTION_WRAP_PX, justify="left")
        action.tk.grid_configure(padx=(0, 6), pady=2, sticky="w")
        self.gui.cache(name, action)
