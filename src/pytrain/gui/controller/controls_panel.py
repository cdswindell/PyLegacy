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
# this is what actually decides where a line breaks. 320 clears the longest current
# string ("Boost / brake speed  (repeats)", measured at 276px) with room for a wider font
# than the one this was measured on.
#
# This is the fallback, for the same reason ROWS_PER_COLUMN is one: build() replaces it
# with a budget divided out of the width the display actually has. As the only answer it
# let every column ask for whatever its longest line wanted, and on the Deck the three
# together asked for more than the 1280px it has.
ACTION_WRAP_PX = 320
# What the middle column gives up, as a fraction of an even share of the page. The
# columns used to be sized by their content, and the middle one -- the engine commands,
# which carry the longest action strings on the screen -- took the most: the three
# together came out wider than the Deck's display, and because the overlay is gridded
# from its left edge the excess is not scaled or scrolled but cut, taking the far side of
# the last column and the Close button at the end of the title band with it. Widths are
# handed out here instead, so the total is the display's by construction. The middle
# column is the one trimmed because its rows are the ones that can afford to wrap, and
# what it gives up is split evenly between the two beside it.
CENTER_COLUMN_TRIM = 0.15
# A floor for a derived action budget, for the same reason MIN_ROWS_PER_COLUMN is one: a
# column too narrow for its keycaps should cost the page its width budget, not wrap every
# row into a stack of single words.
MIN_ACTION_WRAP_PX = 140
# Per-row chrome between a column's edges and the two strings it draws: the keycap's
# border and grid padding, the action's, and the section frame's border. Measured at
# 41-44px across the bundled sections and rounded up -- overstating it wraps a line early,
# understating it lets a column outgrow the share it was given, which is the whole bug.
ENTRY_CHROME_PX = 48
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


def keycap_text(entry: ControlEntry) -> str:
    """The input column as drawn: the input, spaced out into a keycap.

    A function rather than an f-string at the point of drawing, because the width budget
    has to measure the same string the renderer will draw -- a keycap measured a space
    narrower than it is drawn is a column that overflows by a space.
    """
    return f" {entry.input} "


class ControlsPanel:
    """Content of the controls help screen.

    Deliberately *not* an OverlayPanel: those are built by PopupManager, which belongs to
    an EngineGui and can only parent an overlay inside that pane. This panel spans both
    panes, so SteamDeckGui owns its overlay and calls build() to fill it.
    """

    # Width budget per column, once build() has been told how wide the display is. Empty
    # until then, and in a headless run: with no width to divide up, every column sizes to
    # its own content and the action text gets the fallback budget. Declared on the class
    # so a panel built without __init__ -- which is how the pagination tests reach
    # paginate() -- still reads a budget rather than an AttributeError.
    _column_px: tuple[int, ...] = ()

    def __init__(self, gui: "GuiZeroBase", profile: ControlProfile | None):
        self._gui = gui
        self._profile = profile
        self._page = 0
        self._pages: tuple[tuple[tuple[ControlSection, ...], ...], ...] = ()
        self._page_box = None
        self._page_label = None
        # All three are replaced in build(), which has a widget to measure with and is told
        # how much room the columns have been left.
        self._ruler = ESTIMATED_RULER
        self._rows_per_column = ROWS_PER_COLUMN
        self._column_px = ()

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

    @property
    def column_px(self) -> tuple[int, ...]:
        """The width budget in force: derived in build(), empty (content-sized) until then."""
        return self._column_px

    @staticmethod
    def column_widths(width_px: int) -> tuple[int, ...]:
        """How wide each column of a page may be, given the room the page has.

        Even shares, less a trim off the middle column which is split between the two
        beside it. The total never exceeds ``width_px`` -- which is the point of dividing
        the width up rather than letting each column ask for what its longest line wants.
        ``width_px`` of 0 means the caller does not know, and returns no budget at all.
        """
        if width_px <= 0:
            return ()
        even = width_px // COLUMNS
        # Nothing to trim in favour of when there is no column beside the middle one.
        trim = int(even * CENTER_COLUMN_TRIM) if COLUMNS > 1 else 0
        widths = [even + trim // (COLUMNS - 1) for _ in range(COLUMNS)] if COLUMNS > 1 else [even]
        widths[COLUMNS // 2] = even - trim
        return tuple(widths)

    def action_wrap_px(self, section: ControlSection, column_px: int = 0) -> int:
        """Pixels the action text of ``section`` may use in a column ``column_px`` wide.

        Per section rather than per column, because what is left of a column is whatever
        its keycaps do not take: "Right stick \u2195" leaves a good deal less room than "A".
        ``column_px`` of 0 -- no width budget -- falls back to ACTION_WRAP_PX, which is
        what a headless run gets.
        """
        if column_px <= 0:
            return ACTION_WRAP_PX
        keycap = max((self._ruler.width(keycap_text(entry)) for entry in section.entries), default=0)
        return max(MIN_ACTION_WRAP_PX, column_px - keycap - ENTRY_CHROME_PX)

    def _column_wrap_px(self, section: ControlSection, column: int) -> int:
        """The action budget for ``section`` drawn in the ``column``-th column packed.

        Counted per column because the columns are no longer the same width: the same
        section wraps into more rows in the narrow middle one than beside it, and packing
        that guessed one width for all three either overflowed the short column or spilled
        the page onto a second one for rows the wide columns never needed.
        """
        if not self._column_px:
            return ACTION_WRAP_PX
        return self.action_wrap_px(section, self._column_px[column % len(self._column_px)])

    @staticmethod
    def note_wrap_px(column_px: int = 0) -> int:
        """Pixels a section's note may use in a column ``column_px`` wide.

        The whole column less its chrome, not what an entry's action gets: the note spans
        both of the section's columns, so no keycap comes off its width.
        """
        if column_px <= 0:
            return ACTION_WRAP_PX
        return max(MIN_ACTION_WRAP_PX, column_px - ENTRY_CHROME_PX)

    def _narrowest_wrap_px(self, section: ControlSection) -> int:
        """The action budget for ``section`` wherever it lands: the narrowest column's.

        For the one decision taken before a section has a column -- whether it is too tall
        for any column and has to be split. The narrowest column is the safe answer there:
        every wider one wraps the same text into no more rows, so a chunk that fits this
        budget fits the column it ends up in.
        """
        return self.action_wrap_px(section, min(self._column_px, default=0))

    def paginate(self) -> tuple[tuple[tuple[ControlSection, ...], ...], ...]:
        """Group sections into columns, and columns into pages.

        A custom profile can bind far more than the bundled one, so the screen has to
        cope with overflowing rather than silently dropping the tail: sections fill
        columns, ``COLUMNS`` columns make a page, and the D-pad moves between pages.

        Filling is greedy, so where one column ends and the next begins follows from the
        row budget -- which is derived from the display and therefore not the same number
        everywhere. A section that has to head a column says so (``starts_column``) rather
        than relying on the rows before it happening to add up.

        A section costs what it costs *in the column it is being packed into*: the middle
        column is the narrow one, so it wraps text the outer two do not.
        """
        profile = self.profile
        if profile is None:
            return ()
        budget = self._rows_per_column
        columns: list[list[ControlSection]] = [[]]
        used = 0
        for section in self._split_to_fit(controls_summary(profile), budget, self._ruler, self._narrowest_wrap_px):
            cost = self.section_rows(section, self._ruler, self._column_wrap_px(section, len(columns) - 1))
            if used and (section.starts_column or used + cost > budget):
                columns.append([])
                used = 0
                # Priced again: the column it moved to may not be as wide as the one it
                # would not fit, or may be wider.
                cost = self.section_rows(section, self._ruler, self._column_wrap_px(section, len(columns) - 1))
            columns[-1].append(section)
            used += cost
        pages = [
            tuple(tuple(column) for column in columns[start : start + COLUMNS])
            for start in range(0, len(columns), COLUMNS)
        ]
        return tuple(pages)

    @staticmethod
    def entry_rows(entry: ControlEntry, ruler: TextRuler | None = None, wrap_px: int = ACTION_WRAP_PX) -> int:
        """Rows an entry will occupy once Tk has wrapped its action text within ``wrap_px``."""
        return (ruler or ESTIMATED_RULER).wrapped_rows(entry_text(entry), wrap_px)

    @staticmethod
    def note_rows(
        section: ControlSection,
        ruler: TextRuler | None = None,
        wrap_px: int = ACTION_WRAP_PX,
    ) -> int:
        """Rows a section's note occupies, 0 for a section without one.

        Charged against the same budget its entries are, because it is drawn inside the
        same frame and takes the same room off the bottom of the column. Priced with the
        entry font and the entry's share of the width, though the note is drawn smaller and
        given more room than that: both errors are in the safe direction, and a budget that
        decides what runs off the display should never promise more room than it has.
        """
        if not section.note:
            return 0
        return (ruler or ESTIMATED_RULER).wrapped_rows(section.note, wrap_px)

    @classmethod
    def section_rows(
        cls,
        section: ControlSection,
        ruler: TextRuler | None = None,
        wrap_px: int = ACTION_WRAP_PX,
    ) -> int:
        """Rows a section occupies: its header, its (possibly wrapped) entries, its note."""
        rows = 1 + sum(cls.entry_rows(entry, ruler, wrap_px) for entry in section.entries)
        return rows + cls.note_rows(section, ruler, wrap_px)

    @staticmethod
    def _split_to_fit(
        sections: tuple[ControlSection, ...],
        rows_per_column: int = ROWS_PER_COLUMN,
        ruler: TextRuler | None = None,
        wrap_px: Callable[[ControlSection], int] | None = None,
    ) -> list[ControlSection]:
        """Break any section taller than a column into continuation chunks.

        Without this, a custom profile that binds every button produces one section
        taller than the screen and the tail is simply clipped -- a silent cap, and the
        worst kind, because a clipped help screen looks complete.
        """
        chunks: list[ControlSection] = []
        for section in sections:
            # Measured against the narrowest column a section could land in, so a chunk
            # that fits here fits wherever it is packed.
            budget = ACTION_WRAP_PX if wrap_px is None else wrap_px(section)
            if ControlsPanel.section_rows(section, ruler, budget) <= rows_per_column:
                chunks.append(section)
                continue
            # The header takes a row, and the note -- which the last chunk carries -- takes
            # what it takes. Charged to every chunk rather than to the one that ends up
            # with it, which is not known until the entries have been dealt out: the cost
            # is a row on a section long enough to be split in the first place.
            capacity = rows_per_column - 1 - ControlsPanel.note_rows(section, ruler, budget)
            # Accumulate by rendered height, not entry count: a wrapped entry is two rows.
            batch: list[ControlEntry] = []
            used = 0
            # Only the first chunk carries the section's column break; the rest start a
            # column anyway, by being a full column's worth.
            first = True
            for entry in section.entries:
                rows = ControlsPanel.entry_rows(entry, ruler, budget)
                if batch and used + rows > capacity:
                    chunks.append(
                        ControlSection(section.title, tuple(batch), section.fixed, first and section.starts_column)
                    )
                    batch, used, first = [], 0, False
                batch.append(entry)
                used += rows
            if batch:
                # The note goes on the last chunk: it qualifies the rows above it, and the
                # rows it qualifies end here.
                chunks.append(
                    ControlSection(
                        section.title,
                        tuple(batch),
                        section.fixed,
                        first and section.starts_column,
                        section.note,
                    )
                )
        # Mark every chunk after the first as a continuation of its section.
        seen: set[str] = set()
        marked: list[ControlSection] = []
        for chunk in chunks:
            if chunk.title in seen:
                marked.append(ControlSection(f"{chunk.title} (cont.)", chunk.entries, chunk.fixed, note=chunk.note))
            else:
                seen.add(chunk.title)
                marked.append(chunk)
        return marked

    def build(self, body: Box, height_px: int = 0, width_px: int = 0) -> None:
        """Fill ``body`` with the help columns.

        ``height_px`` is the vertical room the caller has left for them and ``width_px``
        the horizontal, each with the caller's own chrome already deducted; 0 means it
        does not know, and the fallbacks stand -- the calibrated row budget, and columns
        that size themselves to their content.
        """
        self._ruler = TextRuler.measured(body)
        self._rows_per_column = self._rows_that_fit(height_px)
        self._column_px = self.column_widths(width_px)
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
        holders = [self._render_column(box, column, index) for index, column in enumerate(self._pages[self._page])]
        self._match_outer_columns(box)
        if self.page_count > 1:
            self._page_label = Text(
                box,
                text=f"Page {self._page + 1} of {self.page_count}   (D-pad up/down)",
                grid=[0, 1, COLUMNS, 1],
                size=FOOTNOTE_SIZE,
                color=FOOTNOTE_FG,
            )
        # Last of all, once nothing more will be added to this box: guizero re-grids every
        # child of a grid container each time another one is added, from that child's align
        # -- so a sticky set on a column is undone by the next column, and by the page label
        # after them. The column widths above survive it (they are set on the container, not
        # its children); this does not.
        self._fill_columns(holders)

    def _match_outer_columns(self, box: Box) -> None:
        """Make the first and last column the same width, and no column wider than it needs.

        The width budget is a limit, not an allowance: it decides where the text wraps, and
        so keeps the page inside the display, but a column that then uses less than its
        share must not hold the difference open -- that reads as a gap before the next
        column rather than as a column that came out narrow.

        So the columns size themselves to their content, and only the outer two are pinned,
        to the wider of the two, because three columns whose outer pair are visibly
        different widths read as a mistake. Tk is asked how wide they came out rather than
        told, because Tk is what laid the text out; where it cannot say -- a fake render in
        the tests -- every column simply keeps its own width.

        The width a column is pinned to it then has to spend, which is _fill_columns' half
        of this: pinned but not filled, the narrower column is centred in the difference,
        and the half of it that lands on the inside is the gap this was meant to close.
        """
        try:
            box.tk.update_idletasks()  # grid sizes the columns at idle; ask after that
            holders = box.tk.winfo_children()
            widest = max(holders[0].winfo_reqwidth(), holders[-1].winfo_reqwidth())
            for index in (0, COLUMNS - 1):
                box.tk.grid_columnconfigure(index, minsize=widest)
        except (AttributeError, IndexError, TclError) as exception:
            log.debug("Column widths unavailable (%s); leaving each column its own", exception)

    def _fill_columns(self, holders: list[Box]) -> None:
        """Have each column spend the whole width of the cell it was given.

        align="top" grids a column sticky="N", which centres it in a cell wider than its
        content: the outer column that was widened to match the other one then draws at its
        own width in the middle of the difference, half of it showing as blank before the
        next column. "new" hands that width to the sections instead, which are packed to
        fill, so the two outer columns really are one width and each column's frames end
        where its neighbour's begin.

        The section headings and their rows stay left, so a column with room to spare shows
        it as space inside its frames rather than as a gap between them.
        """
        for holder in holders:
            try:
                holder.tk.grid_configure(sticky="new")
            except (AttributeError, TclError) as exception:  # pragma: no cover - no display
                log.debug("Column %s cannot be filled (%s); leaving it centred", holder, exception)

    def _render_column(self, parent: Box, sections: tuple[ControlSection, ...], column: int) -> Box:
        host = self.gui
        width_px = self._column_px[column] if column < len(self._column_px) else 0
        holder = Box(parent, grid=[column, 0], align="top", layout="auto")
        for section in sections:
            title = section.title if not section.fixed else f"{section.title} *"
            tb = TitleBox(holder, text=title, layout="grid", align="top", width="fill")
            tb.text_size = SECTION_SIZE
            tb.text_color = SECTION_FG
            tb.text_bold = True
            wrap_px = self.action_wrap_px(section, width_px)
            for row, entry in enumerate(section.entries):
                self._render_entry(tb, entry, row, wrap_px)
            if section.note:
                self._render_note(tb, section.note, len(section.entries), width_px)
            host.cache(tb)
        return holder

    def _render_note(self, parent: TitleBox, text: str, row: int, column_px: int = 0) -> None:
        """Draw a section's note under its rows, across the width of the section.

        Footnote-sized and grey, like the "*" line under the columns: it says something
        about the rows above it rather than being one of them, so an eye scanning keycaps
        should pass over it. Spanned across both of the section's columns because it belongs
        to the section and not to any one input -- there is no keycap to draw beside it.

        Unbolded for the same reason, and it has to be said rather than left alone: the
        section's TitleBox sets bold on everything drawn inside it, so a note left to
        inherit comes out as emphatic as the rows it qualifies -- where the page's other
        footnote, which sits outside any section, does not.
        """
        note = Text(parent, text=text, grid=[0, row, 2, 1], align="left", size=FOOTNOTE_SIZE)
        note.text_color = FOOTNOTE_FG
        note.text_bold = False
        note.tk.config(wraplength=self.note_wrap_px(column_px), justify="left")
        note.tk.grid_configure(padx=(4, 6), pady=(0, 2), sticky="w")
        self.gui.cache(note)

    def _render_entry(self, parent: TitleBox, entry, row: int, wrap_px: int = ACTION_WRAP_PX) -> None:
        # The input is drawn as a raised keycap so the eye can find "L1" or "View"
        # without reading the whole line -- this is a reference table, scanned rather
        # than read.
        name = Text(parent, text=keycap_text(entry), grid=[0, row], align="left", size=ENTRY_SIZE)
        name.text_bold = True
        name.text_color = KEYCAP_FG
        name.bg = KEYCAP_BG
        name.tk.config(relief="raised", borderwidth=1)
        name.tk.grid_configure(padx=(4, 8), pady=2, sticky="w")

        action = Text(parent, text=entry_text(entry), grid=[1, row], align="left", size=ENTRY_SIZE)
        action.text_color = ENTRY_FG
        # wraplength wraps instead of truncating or forcing the column wider. justify
        # keeps the second line aligned under the first rather than centred.
        action.tk.config(wraplength=wrap_px, justify="left")
        action.tk.grid_configure(padx=(0, 6), pady=2, sticky="w")
        self.gui.cache(name, action)
