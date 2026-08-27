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
#
# ENTRY_SIZE is a ceiling rather than the size drawn: _fit_text gives points back, down to
# MIN_ENTRY_SIZE, on a display whose font is too wide to hold its rows on one line. 16 is
# the ceiling because it is the largest size the three columns fit the Deck's 1274px at on
# any font that could be measured here -- 1250px of it, where 17pt wants 1345 -- so a
# higher one would only ever be handed straight back. Height is not what limits it: a row
# is as tall as the taller of its own text and a SECTION_SIZE heading, and the heading wins
# up to 17pt, so the derived budget stays at the 22 rows the Deck's height buys against the
# 19 the bundled sections need.
#
# A wider font pays nothing for the ceiling being here rather than a point lower: on the
# Deck's own -- some 6-12% wider than a desk machine's at the same point size -- 16pt wants
# 1313-1380px, so _fit_text settles at 15 or below there exactly as it did when 15 was
# written here. The alternative to that shrink was cutting words out of "Boost / brake
# speed  (repeats)" and the two "Throw thru / out LEFT/RIGHT" rows, which are what the
# middle and last columns are measured against, and the wording is worth more than the
# point.
TITLE_SIZE = 24
SECTION_SIZE = 14
ENTRY_SIZE = 16
FOOTNOTE_SIZE = 12
# How far the entry text may shrink when a display cannot hold its rows at ENTRY_SIZE, a
# point at a time -- see _fit_text. A floor rather than one fixed size because the font a
# display draws in is not knowable from here: the same 16pt rows measure 6-12% wider on the
# Deck than on a desk machine, which is the difference between a screen of single lines and
# three broken rows. Three points is as far as it goes; below that the screen is being read
# at arm's length and something else has to give.
MIN_ENTRY_SIZE = 16

# Width budget for an entry's action text, in pixels -- handed to Tk as wraplength, so
# this is what actually decides where a line breaks. 320 clears the longest current
# string ("Boost / brake speed  (repeats)", measured at 276px at the 16pt ENTRY_SIZE
# names) with room for a wider font than the one this was measured on.
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
#
# This is the fallback, for the same reason ROWS_PER_COLUMN and ACTION_WRAP_PX are:
# build() re-cuts the shares to what each column's own rows measure (_shared_widths). As
# the only answer a flat trim was the wrong shape for columns that are not alike -- it
# took 15% off the column holding "Boost / brake speed (repeats)", the longest string on
# the screen, and gave it to the column with the shortest rows, which wrapped rows while
# ~130px of the Deck's display went unspent.
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
# overflows the column. Over-estimating only leaves slack. Measured at 16pt, which is what
# ENTRY_SIZE says again, so the estimate and the size it estimates for agree.
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
        keycap_measure: Callable[[str], int] | None = None,
    ) -> None:
        self._measure = measure
        self._row_px = row_px
        self._footnote_px = footnote_px
        self._keycap_measure = keycap_measure

    @classmethod
    def measured(cls, widget, entry_size: int = ENTRY_SIZE) -> "TextRuler":
        """A ruler backed by Tk's own metrics, or an estimating one if Tk cannot be asked.

        ``entry_size`` is the point size the rows are to be drawn at, which _fit_text
        varies: a ruler is only worth having if it measures the size it is asked about.
        """
        try:
            root = getattr(widget, "tk", widget)
            family = tkfont.nametofont(DEFAULT_FONT_NAME, root=root).actual("family")
            entry = tkfont.Font(root=root, family=family, size=entry_size)
            # Keycaps are drawn bold, and bold is about 7% wider in this family -- 11px on
            # " Right stick \u2195 / \u2194 ". Measured in the weight it is drawn in because
            # the keycap's width is what the action text beside it does not get: measuring
            # it light hands the action a budget the row does not have, and Tk then wraps a
            # line the packer counted as one.
            keycap = tkfont.Font(root=root, family=family, size=entry_size, weight="bold")
            heading = tkfont.Font(root=root, family=family, size=SECTION_SIZE, weight="bold")
            footnote = tkfont.Font(root=root, family=family, size=FOOTNOTE_SIZE)
            # One height for both kinds of row, and the taller of the two: the row model
            # charges a heading a single row, so charging it the shorter height would let a
            # column of headings run off the bottom of the display.
            row_px = max(entry.metrics("linespace"), heading.metrics("linespace") + TITLE_BOX_BORDER_PX)
            return cls(entry.measure, row_px + ROW_PADDING_PX, footnote.metrics("linespace"), keycap.measure)
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

    def keycap_width(self, text: str) -> int:
        """Rendered width of a keycap, which is drawn a weight heavier than the rest.

        The estimate cannot tell the two apart -- one character count, one pixel figure --
        and does not need to: it is deliberately generous, so it already covers the bold.
        """
        if self._keycap_measure is None:
            return self.width(text)
        return self._keycap_measure(text)

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
    # The room the whole page was given, kept for the one decision taken after the columns
    # are drawn rather than before: whether the outer pair can afford to be pinned to each
    # other. 0 means the caller did not say, and nothing is capped.
    _width_px: int = 0
    # The point size the rows are drawn at, which _fit_text settles against the room there
    # is. ENTRY_SIZE until it has run, which is what a headless run draws at.
    _entry_size: int = ENTRY_SIZE

    def __init__(self, gui: "GuiZeroBase", profile: ControlProfile | None):
        self._gui = gui
        self._profile = profile
        self._page = 0
        self._pages: tuple[tuple[tuple[ControlSection, ...], ...], ...] = ()
        self._page_box = None
        self._page_label = None
        # All of these are settled in build(), which has a widget to measure with and is
        # told how much room the columns have been left.
        self._ruler = ESTIMATED_RULER
        self._rows_per_column = ROWS_PER_COLUMN
        self._column_px = ()
        self._width_px = 0
        self._entry_size = ENTRY_SIZE

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
    def entry_size(self) -> int:
        """The point size the rows are drawn at: settled in build(), ENTRY_SIZE until then."""
        return self._entry_size

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

    @staticmethod
    def _shared_widths(width_px: int, needs: tuple[int, ...]) -> tuple[int, ...]:
        """How wide each column of a page may be, given what its own rows need.

        What each column asks for, when the page can afford all of them, with the slack
        handed out rather than held back: an unspent budget is not drawn as a gap (the
        columns size themselves to their content), so keeping it back buys nothing and
        spending it covers ENTRY_CHROME_PX guessing a pixel low.

        When the columns between them want more than the page has, the ones that fit an
        even share keep what they need and the rest divide what is left -- so a column
        with short rows is never trimmed on behalf of one whose rows will not fit anyway,
        which is exactly what a flat CENTER_COLUMN_TRIM did. Repeated until no column is
        under its share, because handing a share back can bring another column inside
        its own.

        Unequal columns are only safe because _match_outer_columns will not pin the outer
        pair to a width the page cannot afford: pinning charges the wider one's width to
        both, which is how the far side of the last column ends up off the display.
        """
        if width_px <= 0 or not needs:
            return ()
        spare = width_px - sum(needs)
        if spare >= 0:
            share = spare // len(needs)
            return tuple(need + share for need in needs)
        widths, room, short = [0] * len(needs), width_px, list(range(len(needs)))
        while short:
            share = room // len(short)
            fits = [index for index in short if needs[index] <= share]
            if not fits:  # nothing fits its share: divide what is left evenly
                for index in short:
                    widths[index] = share
                break
            for index in fits:
                widths[index] = needs[index]
                room -= needs[index]
            short = [index for index in short if index not in fits]
        return tuple(widths)

    def section_px(self, section: ControlSection) -> int:
        """Width ``section`` needs to draw every row of it on one line.

        The width counterpart of section_rows, and the figure action_wrap_px works back
        from: the keycap column is as wide as the section's widest keycap, so that is
        where the action text starts on every row of it, not just on the row that keycap
        belongs to.

        A section's note is not counted. It is drawn a size down and wraps as an aside
        rather than as a row, so a long one should cost the column rows -- which the
        packer already charges it -- and not the width its rows need.
        """
        keycap = max((self._ruler.keycap_width(keycap_text(entry)) for entry in section.entries), default=0)
        action = max((self._ruler.width(entry_text(entry)) for entry in section.entries), default=0)
        return keycap + action + ENTRY_CHROME_PX

    def _column_needs(self) -> tuple[int, ...]:
        """What each column position needs to draw the rows packed into it on one line.

        Per position rather than per column, because columns run on across pages and the
        width belongs to the place on the page -- the same rule _column_wrap_px follows.
        """
        needs = [0] * COLUMNS
        for page in self.paginate():
            for index, column in enumerate(page):
                for section in column:
                    needs[index % COLUMNS] = max(needs[index % COLUMNS], self.section_px(section))
        return tuple(needs)

    def _fitted_column_widths(self, width_px: int) -> tuple[int, ...]:
        """The page's width, cut to what its columns measure rather than into even shares.

        Measured, so the shares hold on the display this is running on rather than on the
        one they were calibrated against: the Deck's font draws these strings about 15%
        wider than the desk machine's does, which is the whole difference between a row
        fitting and a row wrapping.

        With nothing to measure with -- a headless run, a stand-in widget -- the even
        split stands, as ROWS_PER_COLUMN does for the row budget.
        """
        widths = self.column_widths(width_px)
        if not widths or not self._ruler.exact or self.profile is None:
            return widths
        # Which sections share a column follows from the width they were packed to, so the
        # needs are read off a first pass laid out to the even split -- today's answer --
        # and build() packs the page again to what comes out of it. One refinement rather
        # than a loop to a fixed point: the total is inside the display in either pass by
        # construction, so the worst a section moved by the second pass can cost is the
        # wrap it would have had anyway.
        self._column_px = widths
        return self._shared_widths(width_px, self._column_needs())

    def action_wrap_px(self, section: ControlSection, column_px: int = 0) -> int:
        """Pixels the action text of ``section`` may use in a column ``column_px`` wide.

        Per section rather than per column, because what is left of a column is whatever
        its keycaps do not take: "Right stick \u2195" leaves a good deal less room than "A".
        ``column_px`` of 0 -- no width budget -- falls back to ACTION_WRAP_PX, which is
        what a headless run gets.
        """
        if column_px <= 0:
            return ACTION_WRAP_PX
        keycap = max((self._ruler.keycap_width(keycap_text(entry)) for entry in section.entries), default=0)
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
        self._width_px = width_px
        self._fit_text(body, height_px, width_px)
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

    def _fit_text(self, body: Box, height_px: int, width_px: int) -> None:
        """Settle the size the rows are drawn at, and the budgets that follow from it.

        ENTRY_SIZE if the columns can hold their rows on one line at it, and a point less
        at a time down to MIN_ENTRY_SIZE if they cannot. The size cannot simply be written
        down because the room a row takes is not knowable from here: the Deck draws the
        same point size some 6-12% wider than a desk machine does, which was the whole of
        what was left of the wrapping once the width was being divided by measurement. A
        screen that measures its own rows does not have to be told.

        Down rather than up: ENTRY_SIZE is already the largest size these columns fit the
        Deck's width at on any font that could be measured here, so there is nothing above
        it worth trying -- this gives a point back to save a row and never spends one it
        does not have to. With nothing to measure with the first size stands, as it does for
        the row and width budgets.
        """
        for size in range(ENTRY_SIZE, MIN_ENTRY_SIZE - 1, -1):
            self._entry_size = size
            self._ruler = TextRuler.measured(body, size)
            self._rows_per_column = self._rows_that_fit(height_px)
            # After the row budget: _fitted_column_widths packs a first pass against it.
            self._column_px = self._fitted_column_widths(width_px)
            if not self._ruler.exact or not self._column_px or self.rows_fit_their_columns():
                return
        # Out of points to give back. The smallest tried stands: the rows that still do not
        # fit wrap, and the packer has counted the rows they wrap into.
        log.debug("Controls rows do not fit at %dpt; drawing at the floor", self._entry_size)

    def rows_fit_their_columns(self) -> bool:
        """Whether every column is wide enough to draw its rows on one line.

        Asked of the needs rather than of the rows themselves because they are the same
        question: a column at least as wide as its widest row's keycap, action and chrome
        wraps none of them.

        Public because it is the question a reader of this screen has about it, and the one
        scripts/controlspreview.py is run to answer on a display this cannot measure.
        """
        return all(need <= width for need, width in zip(self._column_needs(), self._column_px))

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

        And it is only done when the page can afford it. Pinning widens the narrower of the
        two by the difference between them, which has to come out of the room the columns
        left over; charged to a page that has none, it pushes the far side of the last
        column and the Close button off the display -- the whole failure the width budget
        exists to prevent. Tidiness is not worth that, so an unaffordable pin is skipped
        and the columns keep their own widths.
        """
        try:
            box.tk.update_idletasks()  # grid sizes the columns at idle; ask after that
            holders = box.tk.winfo_children()
            drawn = [holder.winfo_reqwidth() for holder in holders[:COLUMNS]]
            widest = max(drawn[0], drawn[-1])
            cost = 2 * widest - drawn[0] - drawn[-1]
            if self._width_px and cost > self._width_px - sum(drawn):
                log.debug("No room to match the outer columns (%dpx short); leaving each its own", cost)
                return
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
        name = Text(parent, text=keycap_text(entry), grid=[0, row], align="left", size=self._entry_size)
        name.text_bold = True
        name.text_color = KEYCAP_FG
        name.bg = KEYCAP_BG
        name.tk.config(relief="raised", borderwidth=1)
        name.tk.grid_configure(padx=(4, 8), pady=2, sticky="w")

        action = Text(parent, text=entry_text(entry), grid=[1, row], align="left", size=self._entry_size)
        action.text_color = ENTRY_FG
        # Said rather than left alone, as the section note also has to say it: the row's
        # TitleBox bolds everything drawn inside it, so an action left to inherit came out
        # exactly as emphatic as the keycap beside it -- which cost the keycap the one job
        # the bold is there for, and cost every row about 7% of its width, wrapping four of
        # them on the Deck against a budget measured in the lighter weight.
        action.text_bold = False
        # wraplength wraps instead of truncating or forcing the column wider. justify
        # keeps the second line aligned under the first rather than centred.
        action.tk.config(wraplength=wrap_px, justify="left")
        action.tk.grid_configure(padx=(0, 6), pady=2, sticky="w")
        self.gui.cache(name, action)
