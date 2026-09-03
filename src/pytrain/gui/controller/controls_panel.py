#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The controls help screen: what every button, stick, and chord currently does.

Content comes from the loaded ControlProfile, so a user who passes
-controller_profile to make_gui sees their own bindings rather than the bundled
ones. See control_labels.py for how a binding becomes English.
"""

from __future__ import annotations

import logging
import re
from tkinter import Frame, Label, TclError
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
# center (and therefore the title and Close button) sat off screen. Three fits.
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
# ENTRY_SIZE is the size the rows are drawn at, on every display: MIN_ENTRY_SIZE below is
# the same number, so _fit_text has one size to try and never gives a point back. 16 is
# that number because it is the largest the three columns hold the Deck's 1274px at on the
# font that could be measured here -- 1229px of it, where 17pt wants 1321. Height is not
# what limits it: a row is as tall as the taller of its own text and a SECTION_SIZE
# heading, and the heading wins up to 17pt, so the derived budget stays at the rows the
# Deck's height buys (24 here, 21 on a font 12% wider) against the 19 the bundled sections
# need.
#
# On a font wider than this machine's the size no longer moves and the page does. The Deck
# draws these strings some 6-12% wider, where the columns ask for 1290-1423px of the 1274
# there are. Less of that is lost than it sounds: a budget is what a column may use, and
# the page draws its content, which is narrower -- rendered at 17pt and 18pt as stand-ins
# for those two ends, the page comes out 1269px and 1278px, so nothing is cut at the narrow
# end and 4px at the wide one. It was 1255px and 1304px before the notes came down to
# NOTE_SIZE and the section outlines to SECTION_BORDER, so what those two bought was 26px
# of the 30 that used to be cut off the right-hand side of the Close button. Survivable in
# any case, because Close is also X on the gamepad.
#
# That is the trade this screen is asked to make: a broken row costs a reader more than a
# page that runs over. It replaced giving points back until the rows fit, which answered a
# display too narrow for the screen with a screen too small to read at arm's length.
TITLE_SIZE = 24
SECTION_SIZE = 14
ENTRY_SIZE = 16
FOOTNOTE_SIZE = 12
# The size a row's parenthesised note is drawn at -- "(repeats)", "(hold: w dialog)",
# "(w focus)". FOOTNOTE_SIZE, so every aside on the screen is one size: the same as the "*"
# line under the columns and a section's own note, which is what these are -- something
# said about the row rather than part of it.
#
# It is also the width this screen had left to find. Eight notes are drawn on the bundled
# page and seven of them are in the middle column, which is the one that prices the page: at
# NOTE_SIZE that column's need drops 21px, from 441 to 420, and it stops being the widest.
# The last column saves nothing (its longest row, "Throw thru / out RIGHT", carries no note)
# and neither does the first, whose one note -- the catalog row's, which used to be spelled out
# inside its label -- sits on a row far shorter than "HALT - emergency stop" above it. So
# this is not a general economy; it is the one column it had to come out of.
NOTE_SIZE = FOOTNOTE_SIZE
# The floor _fit_text may give points back to, and it is ENTRY_SIZE itself: the size is
# settled, not fitted. It was 14, and those two points bought exactly one thing -- the
# columns back inside a display too narrow for them at 16 -- at a price paid by every
# reader of the screen. The columns are let past the edge of the display instead
# (_shared_widths).
#
# The two halves go together, and lowering this alone would not undo it: the columns now
# take what their rows need, so the rows fit them on the first pass and _fit_text never
# reaches a second size. It stays a loop rather than an assignment because the floor is
# where a display too small for 16pt would be answered, and that is a decision worth being
# able to move rather than a leftover.
MIN_ENTRY_SIZE = 16

# Width budget for an entry's action and its note, in pixels -- what is left of it after the
# note is handed to Tk as the action's wraplength, so this is what actually decides where a
# line breaks. 320 clears the longest current row ("Boost / brake speed" at 182px beside its
# "(repeats)" at 69px, measured at ENTRY_SIZE and NOTE_SIZE) with room for a wider font than
# the one this was measured on.
#
# This is the fallback, for the same reason ROWS_PER_COLUMN is one: build() replaces it
# with a budget measured off the rows the column actually holds. As the only answer it let
# every column ask for whatever its longest line wanted with nothing measuring the total,
# which is not the same thing as what the measured path now does deliberately -- that one
# knows what it is spending and how far past the display it goes.
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
#
# It is also the only place the promise above still holds. A screen that can measure its
# own rows hands each column what its rows need and lets the total run past the display if
# it must, because the cut that costs is the one through the middle of a line of text.
CENTER_COLUMN_TRIM = 0.15
# A floor for a derived action budget, for the same reason MIN_ROWS_PER_COLUMN is one: a
# column too narrow for its keycaps should cost the page its width budget, not wrap every
# row into a stack of single words.
MIN_ACTION_WRAP_PX = 140
# How many times build() may pack the page and re-measure the columns before their widths
# stand -- see _fitted_column_widths. More than one because the two decisions feed each
# other: which sections share a column follows from the width they were packed to, and
# what a column needs follows from the sections in it. One pass was enough while the
# widths were held to the display, since a section that moved could only cost the wrap it
# would have had anyway; now that a column can take what it needs, a section that moves
# into one measured without it wraps there, so the passes run until no column is under its
# need. Four is a cap on the work, not an expectation: the bundled screen settles on the
# second, and the passes only ever widen a column, so each one can only remove wraps.
WIDTH_PASSES = 4
# Per-row chrome between a column's edges and the strings it draws: the keycap's border and
# grid padding, the action's, and the section frame's border. Measured at 41-44px across the
# bundled sections and rounded up -- overstating it wraps a line early, understating it lets
# a column outgrow the share it was given, which is the whole bug. Two of those pixels went
# when the frames came down to SECTION_BORDER, and a row's note carries its own padding
# (NOTE_CHROME_PX) rather than being charged here, where every row would pay for it.
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

# Vertical room the row model allows a row beyond its own text: what pady=2 above and below
# would take. Allowed rather than drawn -- see ControlsPanel._place_row, which records why
# the rows carry no grid padding -- so this is slack in the height budget, and slack is the
# safe direction: a column of rows shorter than the budget thinks cannot run off the bottom
# of the display.
ROW_PADDING_PX = 4
# Width the note column is allowed beyond the note itself. Charged where a note is drawn
# rather than folded into ENTRY_CHROME_PX, which every row pays whether it has one or not,
# and -- like ROW_PADDING_PX -- allowed rather than drawn (see _place_row): a column
# budgeted 6px wider than its notes need is a column that cannot wrap one.
NOTE_CHROME_PX = 6
# Grid columns a row is drawn in: the keycap, the action, and the note beside it. A
# section's own note spans all three -- it belongs to the section rather than to any one
# input, so there is no keycap to draw beside it.
ENTRY_COLUMNS = 3
# The outline every section is drawn with, and the gap that used to sit between the
# columns. A TitleBox is a Tk LabelFrame, and guizero draws one with a 2px border in Tk's
# default groove relief -- which is a dark line and a light line. So between the text of
# one column and the next there were four pixels: dark, light, light, dark. The two light
# ones read as a gap between columns that are in fact flush (the grid cells are padx=0 and
# every section is packed fill="x"), which is what made it look like padding somebody could
# take out.
#
# A 1px solid outline draws one line per column, so two neighbors meet in a single 2px
# rule with no white in it. Worth 6px of page width, measured -- the small half of what
# closing the gap bought.
SECTION_BORDER = 1
SECTION_RELIEF = "solid"
# A section heading is a TitleBox -- a Tk LabelFrame -- so it costs its label's height
# plus the frame's border, top and bottom: SECTION_BORDER of each.
TITLE_BOX_BORDER_PX = 2 * SECTION_BORDER
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
# will be drawn with.
WORD = re.compile(r"\s*\S+")
# A section heading's parenthesised qualifier -- "(w focus)", "(cont.)" -- and whatever
# trails it, which is the "*" a fixed section carries. Split off so the qualifier can be
# drawn a size down: the panel type is what an eye scanning the headings comes back to,
# where "(w focus)" is read once and then known. Greedy, so a continued section's
# "(w focus) (cont.)" goes small as one piece -- both are parentheses, and both say when
# rather than what.
HEADING_QUALIFIER = re.compile(r"^(?P<head>[^(]*?)\s*(?P<qualifier>\(.*\))(?P<rest>.*)$")

# Palette. Kept in the app's existing family: FOCUS_COLOR (#3B82F6) is the Deck GUI's
# accent, and the grays match the popup chrome PopupManager already uses.
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

    Every answer is remembered, because the same question is asked over and over: the page
    is packed once per pass of _fitted_column_widths, again by rows_fit_their_columns and
    again by build, and each pass re-measured what the last one had already measured. On the
    bundled screen that was 2495 measurements of 140 distinct strings, each one a round trip
    into the Tcl interpreter; it is now 140. Measured, that took the fitting and packing
    phase from 24ms to 2.3ms. A ruler is built per point size and thrown away with it (see
    _fit_text), so what it remembers cannot go stale: one font, one size, one weight.
    """

    def __init__(
        self,
        measure: Callable[[str], int] | None = None,
        row_px: int = 0,
        footnote_px: int = 0,
        keycap_measure: Callable[[str], int] | None = None,
        note_measure: Callable[[str], int] | None = None,
        family: str = DEFAULT_FONT_NAME,
    ) -> None:
        self._measure = measure
        self._row_px = row_px
        self._footnote_px = footnote_px
        self._keycap_measure = keycap_measure
        self._note_measure = note_measure
        self._family = family
        # What has already been measured, per kind of text -- three fonts, so three memos.
        self._widths: dict[str, int] = {}
        self._keycap_widths: dict[str, int] = {}
        self._note_widths: dict[str, int] = {}
        # And where a string breaks within a budget, which is the expensive one: a wrap is
        # decided word by word, so one row of one section costs a measurement per word twice
        # over, and the packer asks about the same row in every column it might land in.
        self._wrapped: dict[tuple[str, int], int] = {}

    @classmethod
    def measured(cls, widget, entry_size: int = ENTRY_SIZE) -> "TextRuler":
        """A ruler backed by Tk's own metrics, or an estimating one if Tk cannot be asked.

        entry_size is the point size the rows are to be drawn at, which _fit_text
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
            # A row's note is drawn a size down, and measured in the size it is drawn in for
            # the reason the keycap is: what the note takes of a column is what the action
            # beside it does not get, and measured at the entry size it is charged 17-29px
            # more than it spends. Capped at the row's own size, since _fit_text can in
            # principle bring the rows below it (see MIN_ENTRY_SIZE) and a note drawn larger
            # than the action it qualifies is no longer an aside.
            note = tkfont.Font(root=root, family=family, size=min(NOTE_SIZE, entry_size))
            # One height for both kinds of row, and the taller of the two: the row model
            # charges a heading a single row, so charging it the shorter height would let a
            # column of headings run off the bottom of the display.
            row_px = max(entry.metrics("linespace"), heading.metrics("linespace") + TITLE_BOX_BORDER_PX)
            return cls(
                entry.measure,
                row_px + ROW_PADDING_PX,
                footnote.metrics("linespace"),
                keycap.measure,
                note.measure,
                family,
            )
        except MEASURE_EXCEPTIONS as exception:
            log.debug("Controls screen cannot measure its font (%s); estimating instead", exception)
            return cls()

    @property
    def exact(self) -> bool:
        """Whether these are Tk's measurements rather than the character-count estimate."""
        return self._measure is not None and self._row_px > 0

    @property
    def family(self) -> str:
        """The font family these measurements are of, and so the one the rows are drawn in.

        Handed to the renderer (ControlsPanel._row_font) rather than looked up again there,
        so a row is drawn in the font it was measured in by construction. Where there was
        nothing to ask, this is the named font itself: Tk reads it as a family it does not
        have and substitutes its own default, which is what an unmeasured screen drew in
        before.
        """
        return self._family

    @property
    def footnote_px(self) -> int:
        """Height of one footer line, or 0 when unmeasured -- see rows_in."""
        return self._footnote_px

    def width(self, text: str) -> int:
        """Rendered width of text, in pixels. Measured once per string -- see the class."""
        hit = self._widths.get(text)
        if hit is None:
            hit = int(len(text) * APPROX_CHAR_PX) if self._measure is None else self._measure(text)
            self._widths[text] = hit
        return hit

    def keycap_width(self, text: str) -> int:
        """Rendered width of a keycap, which is drawn a weight heavier than the rest.

        The estimate cannot tell the two apart -- one character count, one pixel figure --
        and does not need to: it is deliberately generous, so it already covers the bold.
        """
        if self._keycap_measure is None:
            return self.width(text)
        hit = self._keycap_widths.get(text)
        if hit is None:
            hit = self._keycap_widths[text] = self._keycap_measure(text)
        return hit

    def note_width(self, text: str) -> int:
        """Rendered width of a row's note, which is drawn a size down from the row.

        Falls back to the entry width for the same reason keycap_width falls the other way:
        an unmeasured ruler has one figure for a character and both errors it can make with
        it are in the safe direction -- a note charged full size is a column budgeted wider
        than its rows need, never narrower.
        """
        if self._note_measure is None:
            return self.width(text)
        hit = self._note_widths.get(text)
        if hit is None:
            hit = self._note_widths[text] = self._note_measure(text)
        return hit

    def rows_in(self, height_px: int) -> int:
        """Help rows that fit in height_px, or the calibrated fallback if unmeasured."""
        if not self.exact or height_px <= 0:
            return ROWS_PER_COLUMN
        return max(MIN_ROWS_PER_COLUMN, height_px // self._row_px)

    def wrapped_rows(self, text: str, budget: int = ACTION_WRAP_PX) -> int:
        """Rows Tk's word wrap will break text into within budget pixels."""
        hit = self._wrapped.get((text, budget))
        if hit is not None:
            return hit
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
        self._wrapped[(text, budget)] = rows
        return rows


# Used wherever there is no widget to measure with, so the row helpers below stay callable
# without a display -- which is how the pagination tests reach them.
ESTIMATED_RULER = TextRuler()


def note_text(entry: ControlEntry) -> str:
    """The note column as drawn: the entry's note, parenthesised. Empty without one.

    A column of its own rather than the tail of the action string it used to be, which is
    what lets it be drawn a size down -- one Tk label is one font. The parentheses then
    also line up down a section instead of ragging along behind actions of different
    lengths.
    """
    return f"({entry.note})" if entry.note else ""


def heading_parts(title: str) -> tuple[str, str, str]:
    """A section heading split into what is scanned, what qualifies it, and what marks it.

    "Catalog Panel (w focus) *" -> ("Catalog Panel", "(w focus)", "*"), for a heading drawn
    in two sizes -- see ControlsPanel._render_heading. The "*" is kept out of the
    qualifier: it points at the footnote under the columns rather than saying anything
    itself, so it stays the size of the heading it marks.

    A heading with no parentheses comes back whole, which is what most of them are.
    """
    match = HEADING_QUALIFIER.match(title)
    if match is None:
        return title, "", ""
    return match.group("head"), match.group("qualifier"), match.group("rest").strip()


def keycap_text(entry: ControlEntry) -> str:
    """The input column as drawn: the input, spaced out into a keycap.

    A function rather than an f-string at the point of drawing, because the width budget
    has to measure the same string the renderer will draw. A keycap measured a space
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
    def note_size(self) -> int:
        """The point size a row's note is drawn at: NOTE_SIZE, never over the row's own.

        Capped because _fit_text can in principle bring the rows below it (see
        MIN_ENTRY_SIZE), and a note drawn larger than the action it qualifies is not an
        aside any more. The ruler caps its note measure the same way, so what is charged is
        what is drawn.
        """
        return min(NOTE_SIZE, self._entry_size)

    @property
    def column_px(self) -> tuple[int, ...]:
        """The width budget in force: derived in build(), empty (content-sized) until then."""
        return self._column_px

    @staticmethod
    def column_widths(width_px: int) -> tuple[int, ...]:
        """How wide each column of a page may be, given the room the page has.

        Even shares, less a trim off the middle column which is split between the two
        beside it. The total never exceeds width_px, which is the whole of what this
        answer has over letting each column ask for what its longest line wants -- and it
        is the fallback for exactly that reason: a screen that can measure its own rows
        lets them ask (_shared_widths). width_px of 0 means the caller does not know and
        returns no budget at all.
        """
        if width_px <= 0:
            return ()
        even = width_px // COLUMNS
        # Nothing to trim in favor of when there is no column beside the middle one.
        trim = int(even * CENTER_COLUMN_TRIM) if COLUMNS > 1 else 0
        widths = [even + trim // (COLUMNS - 1) for _ in range(COLUMNS)] if COLUMNS > 1 else [even]
        widths[COLUMNS // 2] = even - trim
        return tuple(widths)

    @staticmethod
    def _shared_widths(width_px: int, needs: tuple[int, ...]) -> tuple[int, ...]:
        """How wide each column of a page may be, given what its own rows need.

        What each column asks for, and never less. A column handed less than its rows
        measure is a column with a broken line in it, and this screen is a reference table
        scanned at arm's length: a wrapped row costs its reader more than a page that runs
        past the edge of the display. So when the three between them want more than the
        page has, they get it anyway and the page overruns -- taking the far side of the
        last column and the Close button in the title band off a display that cannot
        afford it, which is survivable only because Close is also X on the gamepad.

        That is a reversal, and a deliberate one. The shortfall used to be paid for out of
        the reading: first by trimming the columns that would not fit whatever they were
        given (a flat CENTER_COLUMN_TRIM before that), then by _fit_text giving back a
        point of text size, down to a floor two points under the size the screen is meant
        to be read at. Both bought a page inside the display at the price of the page.

        Slack, where the page has any, is handed out rather than held back: an unspent
        budget is not drawn as a gap (the columns size themselves to their content), so
        keeping it back buys nothing and spending it covers ENTRY_CHROME_PX guessing a
        pixel low.

        Unequal columns are safe to hand out because _match_outer_columns will not pin the
        outer pair to a width the page cannot afford -- pinning charges the wider one's
        width to both -- and on an overrunning page it never can.
        """
        if width_px <= 0 or not needs:
            return ()
        spare = width_px - sum(needs)
        if spare < 0:
            return tuple(needs)
        share = spare // len(needs)
        return tuple(need + share for need in needs)

    def _note_px(self, entry: ControlEntry) -> int:
        """Width a row's note takes off its column, its own padding included; 0 without one.

        Measured at note_size, which is what it is drawn at. That is the whole point of
        giving it a widget of its own: inside the action's label it was charged 17-29px more
        than it spends, on the one column that could least afford it.
        """
        if not entry.note:
            return 0
        return self._ruler.note_width(note_text(entry)) + NOTE_CHROME_PX

    def section_px(self, section: ControlSection) -> int:
        """Width section needs to draw every row of it on one line.

        The width counterpart of section_rows. The keycap column is as wide as the section's
        widest keycap, so that is where the action text starts on every row of it and not
        just on the row that keycap belongs to; what follows is whatever the widest row needs
        for its action and its note together.

        Which is priced exactly as Tk will lay it out, and the arithmetic is the point.
        Charging every row the widest action *and* the widest note would cost a section the
        two put together even when they are on different rows -- 75px on the bundled Global
        section, whose widest action ("HALT - emergency stop") carries no note and whose only
        note is on a short one. So a row with no note spans the note column instead of
        leaving it empty (see _render_entry), and only the rows that have one are charged for
        it: the notes still line up down the section, and the section is no wider than its
        longest row.

        A *section's* note is a different thing and is not counted. It is drawn a size down
        and wraps as an aside rather than as a row, so a long one should cost the column
        rows -- which the packer already charges it -- and not the width its rows need.
        """
        keycap = max((self._ruler.keycap_width(keycap_text(entry)) for entry in section.entries), default=0)
        noted = [entry for entry in section.entries if entry.note]
        # The two grid columns a noted row uses: as wide as the widest of each, which is what
        # lines the parentheses up and what Tk therefore demands of them.
        annotated = max((self._ruler.width(entry.action) for entry in noted), default=0) + max(
            (self._note_px(entry) for entry in noted), default=0
        )
        # And the rows with no note, which span both of them.
        plain = max((self._ruler.width(entry.action) for entry in section.entries if not entry.note), default=0)
        return keycap + max(annotated, plain) + ENTRY_CHROME_PX

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

        Which sections share a column follows from the width they were packed to, and what
        a column needs follows from the sections in it, so this goes round: the needs are
        read off a pass laid out to the even split -- what a screen with no font to measure
        still draws -- and the page is packed again to what comes out of it. That repacking
        has to be followed up rather than accepted now that a column can take more than an
        even share, because a wider column takes more sections and a section that lands in
        one measured without it wraps there: modeled at 17pt on a font 12% wider than this
        machine's, the second pass moved five rows into columns some 50px too narrow for
        them.

        So each pass widens any column its own packing outran, and never narrows one --
        growth can only remove a wrap, so a row that fits on a line stays on it -- until no
        column is under its need. WIDTH_PASSES caps the work; the bundled screen settles on
        the second pass, and a page that has not settled by the last is drawn with whatever
        wrapping is left, which the packer has counted rows for.

        With nothing to measure with -- a headless run, a stand-in widget -- the even
        split stands, as ROWS_PER_COLUMN does for the row budget.
        """
        widths = self.column_widths(width_px)
        if not widths or not self._ruler.exact or self.profile is None:
            return widths
        self._column_px = widths
        widths = self._shared_widths(width_px, self._column_needs())
        for _ in range(WIDTH_PASSES - 1):
            self._column_px = widths
            needs = self._column_needs()
            if all(need <= width for need, width in zip(needs, widths)):
                break
            widths = tuple(max(width, need) for width, need in zip(widths, needs))
        else:
            log.debug("Controls columns unsettled after %d passes; some rows may wrap", WIDTH_PASSES)
        return widths

    def action_wrap_px(self, section: ControlSection, column_px: int = 0) -> int:
        """Pixels a row of section may use in a column column_px wide.

        What is left of the column once the keycaps and the chrome are off it, for the action
        and its note between them -- a row with no note has the lot, and a row with one has
        this less its own note (see entry_rows and _render_entry, which both take it from
        here).

        Per section rather than per column, because what is left of a column is whatever its
        keycaps do not take: "Right stick \u2195" leaves a good deal less room than "A".
        column_px of 0 -- no width budget -- falls back to ACTION_WRAP_PX, which is
        what a headless run gets.
        """
        if column_px <= 0:
            return ACTION_WRAP_PX
        keycap = max((self._ruler.keycap_width(keycap_text(entry)) for entry in section.entries), default=0)
        return max(MIN_ACTION_WRAP_PX, column_px - keycap - ENTRY_CHROME_PX)

    def _column_wrap_px(self, section: ControlSection, column: int) -> int:
        """The action budget for section drawn in the column-th column packed.

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
        """Pixels a section's note may use in a column column_px wide.

        The whole column less its chrome, not what an entry's action gets: the note spans
        both of the section's columns, so no keycap comes off its width.
        """
        if column_px <= 0:
            return ACTION_WRAP_PX
        return max(MIN_ACTION_WRAP_PX, column_px - ENTRY_CHROME_PX)

    def _narrowest_wrap_px(self, section: ControlSection) -> int:
        """The action budget for section wherever it lands: the narrowest column's.

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
        columns, COLUMNS columns make a page, and the D-pad moves between pages.

        Filling is greedy, so where one column ends and the next begins follows from the
        row budget -- which is derived from the display and therefore not the same number
        everywhere. A section that has to head a column says so (starts_column) rather
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
        """Rows an entry will occupy once Tk has wrapped it within wrap_px.

        wrap_px is the whole of what the row has (action_wrap_px), so what the action
        gets is that less this row's own note -- drawn beside it, at note_size, and never
        wrapped. The row then comes out as tall as the taller of the two, which is the
        action.

        Pricing the pair coherently is what keeps splitting the note off from costing a page
        rather than saving one: measured as "action  (note)" at the entry size, against a
        budget that no longer holds the note at that size, rows that fit on one line are
        counted as two -- and the prototype of this change went to two pages with a column of
        white space on the first.
        """
        ruler = ruler or ESTIMATED_RULER
        note_px = ruler.note_width(note_text(entry)) + NOTE_CHROME_PX if entry.note else 0
        return ruler.wrapped_rows(entry.action, max(wrap_px - note_px, MIN_ACTION_WRAP_PX))

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
        """Fill body with the help columns.

        height_px is the vertical room the caller has left for them and width_px the
        horizontal, each with the caller's own chrome already deducted; 0 means it does
        not know, and the fallbacks stand -- the calibrated row budget, and columns that
        size themselves to their content.
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

        One size, as the constants stand: MIN_ENTRY_SIZE is ENTRY_SIZE, so the loop runs
        once and the rows are drawn at 16pt whatever the display's font measures. Giving a
        point back is what a display too narrow for its rows used to be answered with, and
        it is answered with width now -- the columns take what their rows need and the page
        overruns the display if it must (_shared_widths).

        The loop stays because the floor is a decision worth being able to move rather than
        a leftover. Both halves would have to move together, though: with the columns
        taking what they need, rows_fit_their_columns() is satisfied on the first pass and
        there is nothing left for a second size to fix.

        With nothing to measure with the first size stands, as it does for the row and
        width budgets.
        """
        for size in range(ENTRY_SIZE, MIN_ENTRY_SIZE - 1, -1):
            self._entry_size = size
            self._ruler = TextRuler.measured(body, size)
            self._rows_per_column = self._rows_that_fit(height_px)
            # After the row budget: _fitted_column_widths packs a first pass against it.
            self._column_px = self._fitted_column_widths(width_px)
            if not self._ruler.exact or not self._column_px or self.rows_fit_their_columns():
                return
        # Nothing left to try, and with the floor at the ceiling there was only ever the
        # one size -- so this says the columns could not be widened into fitting either
        # (see rows_fit_their_columns for the two ways that happens). The size stands and
        # what still does not fit wraps, which the packer has counted the rows for.
        log.debug("Controls rows do not fit at %dpt; drawing at the floor", self._entry_size)

    def rows_fit_their_columns(self) -> bool:
        """Whether every column is wide enough to draw its rows on one line.

        Asked of the needs rather than of the rows themselves because they are the same
        question: a column at least as wide as its widest row's keycap, action and chrome
        wraps none of them.

        On a screen that can measure itself this is now an invariant rather than an open
        question -- the columns are handed what they need and the page overruns the display
        rather than trim them -- so a False here means one of the two things that can still
        go wrong: a page that had not settled by the last of WIDTH_PASSES, or a column so
        narrow that MIN_ACTION_WRAP_PX floored its budget.

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
        """Make the first and last column the same width and no column wider than it needs.

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
        of this: pinned but not filled, the narrower column is centered in the difference,
        and the half of it that lands on the inside is the gap this was meant to close.

        And it is only done when the page can afford it. Pinning widens the narrower of the
        two by the difference between them, which has to come out of the room the columns
        left over; charged to a page that has none, it pushes the far side of the last
        column and the Close button further off the display. Tidiness is not worth that, so
        an unaffordable pin is skipped, and the columns keep their own widths.

        On a page that already overruns -- which is what a display too narrow for these
        rows now gets, rather than a smaller font -- there is by definition nothing to
        afford it with, so the pin is simply never taken there. Outer columns of visibly
        different widths read as a mistake; another column's worth of rows pushed past the
        right edge is one.
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

    @staticmethod
    def _fill_columns(holders: list[Box]) -> None:
        """Have each column spend the whole width of the cell it was given.

        align="top" grids a column sticky="N", which centers it in a cell wider than its
        content: the outer column that was widened to match the other one then draws at its
        own width in the middle of the difference, half of it showing as blank before the
        next column. "new" hands that width to the sections instead, which are packed to
        fill, so the two outer columns really are one width and each column's frames end
        where its neighbor's begin.

        The section headings and their rows stay left, so a column with room to spare shows
        it as space inside its frames rather than as a gap between them.
        """
        for holder in holders:
            try:
                holder.tk.grid_configure(sticky="new")
            except (AttributeError, TclError) as exception:  # pragma: no cover - no display
                log.debug("Column %s cannot be filled (%s); leaving it centered", holder, exception)

    def _render_column(self, parent: Box, sections: tuple[ControlSection, ...], column: int) -> Box:
        host = self.gui
        width_px = self._column_px[column] if column < len(self._column_px) else 0
        holder = Box(parent, grid=[column, 0], align="top", layout="auto")
        for section in sections:
            title = section.title if not section.fixed else f"{section.title} *"
            tb = TitleBox(holder, text=title, layout="grid", align="top", width="fill", border=SECTION_BORDER)
            # One call rather than four. guizero's three text properties each read the widget's
            # font back out and ask it for its option list before setting anything, and nothing
            # inherits from this frame any more -- the rows gridded inside it are plain Tk
            # labels, which take their font from _row_font. The relief goes in the same breath:
            # a single line rather than guizero's default groove, which is two (see
            # SECTION_BORDER for what that cost the space between the columns).
            tb.tk.config(
                font=self._row_font(SECTION_SIZE, bold=True),
                foreground=SECTION_FG,
                relief=SECTION_RELIEF,
            )
            self._render_heading(tb, title)
            # Asked once per section and handed to every row of it: what a section frame is
            # drawn in is what the labels inside it have to be told (see _row_label).
            background = self._section_background(tb)
            wrap_px = self.action_wrap_px(section, width_px)
            for row, entry in enumerate(section.entries):
                self._render_entry(tb, entry, row, wrap_px, background)
            if section.note:
                self._render_note(tb, section.note, len(section.entries), width_px, background)
            host.cache(tb)
        return holder

    @staticmethod
    def _section_background(box: TitleBox) -> str:
        """The color a section's frame is drawn in, or "" if it cannot be asked.

        A guizero widget takes its master's background when it is created; a plain Tk label
        does not, and comes out in the system's own window color -- a gray block behind the
        text of a white section. So the frame is asked, once, and every row is told.
        """
        try:
            return box.tk.cget("background")
        except MEASURE_EXCEPTIONS as exception:
            log.debug("Controls section background unavailable (%s); leaving the rows Tk's own", exception)
            return ""

    def _row_font(self, size: int, bold: bool = False) -> tuple:
        """The font one cell of a row is drawn in: the ruler's own family, at size.

        Taken from the ruler rather than looked up again here, so the screen is drawn in the
        font it was measured in by construction -- including the weight, which is the one
        thing the two could disagree about and cost four rows on the Deck when they did.
        """
        return (self._ruler.family, size, "bold") if bold else (self._ruler.family, size)

    def _row_label(
        self,
        parent: TitleBox,
        text: str,
        size: int,
        *,
        bold: bool = False,
        color: str = ENTRY_FG,
        background: str = "",
        **options,
    ) -> Label:
        """One cell of one row, built in a single call.

        A plain Tk label rather than a guizero Text, and this is very nearly the whole of
        what the help screen costs to build. guizero reads every option back off a new widget
        to remember its defaults, then re-applies seven inherited text properties, and each
        of those asks the widget for its option list again -- some 200 round trips into Tcl
        for a one-line label, against the two this makes. Measured on the bundled page: 0.93ms
        a label against 0.07ms, which is 85ms of a 92-label page against 6ms, and the reason
        the prewarm read as a stutter on the Deck.

        Nothing about the drawn row changes, but two things guizero said on the panel's
        behalf have to be said here: the font, including the weight the ruler measured the
        string in, and the background, which a Tk label does not inherit (see
        _section_background). Everything else is what the row was always configured with,
        passed in the constructor rather than set afterwards.
        """
        if background:
            options["background"] = background
        return Label(parent.tk, text=text, font=self._row_font(size, bold), foreground=color, **options)

    @staticmethod
    def _place_row(label: Label, row: int, column: int, span: int = 1) -> None:
        """Grid one cell of a row: where it sits, left-aligned, and nothing else.

        No padx and no pady, which is not an oversight but the geometry this screen has always
        been drawn in -- and worth writing down, because the old renderer asked for padding on
        every row and got it on almost none. guizero re-grids every child of a container each
        time another one joins it, from that child's grid and align alone, so the pady=2 and
        padx=(4, 8) each row set after it was created were thrown away by the next row added
        to the same section. Only the last row of a section kept them.

        Which is why they stay off. Honoring them costs 12px a row across the keycap and
        action columns -- measured, 48px on the page and 52px past the right edge of the Deck
        at the widest font it draws, against 4px today. A keycap is spaced into its own gap
        (keycap_text) and the row model treats the padding as slack it does not spend
        (ROW_PADDING_PX), so what is lost by leaving it off is nothing that was ever drawn.
        """
        label.grid(row=row, column=column, columnspan=span, sticky="w")

    def _render_heading(self, box: TitleBox, title: str) -> None:
        """Draw title with its parenthesised qualifier a size down, where it has one.

        A LabelFrame's own title is one string in one font, so two sizes means handing it a
        labelwidget: a frame of plain Tk labels, packed in reading order. Raw Tk rather than
        guizero widgets because the label of a LabelFrame is managed by the frame itself --
        a guizero child would be gridded in among the section's rows, which is where the
        entries go.

        Worth nothing in width, and that is not what it is for: section_px does not count
        headings, and every one of them measures 100-200px narrower than its own rows -- the
        widest, "Catalog Panel (w focus) *" at ~245px, sits in a column whose rows need 425.
        It is for the reading. "(w focus)" is read once and then known, where the panel type
        is what an eye scanning the headings comes back to, and it is the same aside the rows
        below now draw a size down.

        A heading with no parentheses is left exactly as it was, which is most of them. So is
        every heading on a screen with no Tk to build widgets with: the frame keeps the plain
        title it was created with, and the only thing lost is the size difference.
        """
        head, qualifier, rest = heading_parts(title)
        if not qualifier:
            return
        try:
            background = box.tk.cget("background")
            frame = Frame(box.tk, background=background)
            # Bold and SECTION_FG throughout: the qualifier is part of the heading, not a
            # footnote to it, and 12pt unbolded gray is close to invisible at arm's length on
            # a handheld. Only the size says "read this once".
            for text, size, pad in (
                (head, SECTION_SIZE, 0),
                (qualifier, self.note_size, 4),
                (rest, SECTION_SIZE, 4),
            ):
                if not text:
                    continue
                label = Label(
                    frame,
                    text=text,
                    font=self._row_font(size, bold=True),
                    foreground=SECTION_FG,
                    background=background,
                )
                label.pack(side="left", padx=(pad, 0))
            box.tk.config(labelwidget=frame)
        except MEASURE_EXCEPTIONS as exception:
            log.debug("Controls heading %r cannot be split (%s); drawing it in one size", title, exception)

    def _render_note(self, parent: TitleBox, text: str, row: int, column_px: int = 0, background: str = "") -> None:
        """Draw a section's note under its rows, across the width of the section.

        Footnote-sized and gray, like the "*" line under the columns: it says something
        about the rows above it rather than being one of them, so an eye scanning keycaps
        should pass over it. Spanned across all of the section's columns because it belongs
        to the section and not to any one input -- there is no keycap to draw beside it.

        In the plain weight, which is the point of an aside: the page's other footnote, which
        sits outside any section, is drawn the same way. It used to have to say so twice over
        because a guizero widget inherits the bold its section frame sets on everything inside
        it; a Tk label inherits nothing, so the weight is simply what _row_font is asked for.
        """
        note = self._row_label(
            parent,
            text,
            FOOTNOTE_SIZE,
            color=FOOTNOTE_FG,
            background=background,
            wraplength=self.note_wrap_px(column_px),
            justify="left",
        )
        self._place_row(note, row, 0, ENTRY_COLUMNS)
        self.gui.cache(note)

    def _render_entry(
        self,
        parent: TitleBox,
        entry,
        row: int,
        wrap_px: int = ACTION_WRAP_PX,
        background: str = "",
    ) -> None:
        # The input is drawn as a raised keycap so the eye can find "L1" or "View"
        # without reading the whole line -- this is a reference table, scanned rather
        # than read.
        name = self._row_label(
            parent,
            keycap_text(entry),
            self._entry_size,
            bold=True,
            color=KEYCAP_FG,
            background=KEYCAP_BG,
            relief="raised",
            borderwidth=1,
        )
        self._place_row(name, row, 0)

        # The action in the plain weight against the keycap's bold, which is the one job that
        # bold has: being found without reading the row. Drawn in the weight the budget was
        # measured in, too -- an action as emphatic as its keycap is also about 7% wider than
        # a budget measured light, which is what broke four rows on the Deck.
        #
        # wraplength wraps instead of truncating or forcing the column wider. justify
        # keeps the second line aligned under the first rather than centered. wrap_px is
        # the whole row's share, so the note beside it comes off first -- the same sum
        # entry_rows does, or the packer counts a row the renderer then breaks.
        action = self._row_label(
            parent,
            entry.action,
            self._entry_size,
            background=background,
            wraplength=max(wrap_px - self._note_px(entry), MIN_ACTION_WRAP_PX),
            justify="left",
        )
        # A row with no note spans the note column rather than leaving it empty, so a section
        # is only charged for the notes it has and on the rows that have them -- see
        # section_px, where doing otherwise cost the Global section 75px.
        self._place_row(action, row, 1, 1 if entry.note else 2)
        self.gui.cache(name, action)
        if entry.note:
            self._render_entry_note(parent, entry, row, background)

    def _render_entry_note(self, parent: TitleBox, entry: ControlEntry, row: int, background: str = "") -> None:
        """Draw a row's note beside its action, a size down, in a column of its own.

        "(repeats)", "(hold: w dialog)", "(w focus)": what the note says qualifies the action
        rather than being part of it, and inside the action's own label it was read at full
        size and priced at full width -- 17-29px a row, all of it in the middle column, which
        is the one that decides how wide the page is. A column of its own also lines the
        parentheses up down the section instead of leaving them to rag along behind actions
        of different lengths, which costs nothing because the rows with no note span it (see
        _render_entry).

        Kept the same color as the action, unlike the section note beside which it is drawn:
        the two words in here are sometimes the whole of what a row is telling you ("hold"),
        and graying them as well as shrinking them puts them past reading on a handheld.

        No wraplength, unlike the action: the note's column was measured to hold the widest
        note in the section (section_px), so there is nothing for Tk to break -- and a note
        broken over two lines would cost the row a second one to say the same words.
        """
        note = self._row_label(parent, note_text(entry), self.note_size, background=background)
        self._place_row(note, row, 2)
        self.gui.cache(note)
