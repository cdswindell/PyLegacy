#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from typing import Iterable, Literal, Mapping

from guizero import ButtonGroup, CheckBox

from ..guizero_base import LIONEL_BLUE

BORDER_COLOR = "#9a9a9a"
LIGHT_GRAY = "#cfcfcf"
WHITE = "#ffffff"
# The row the gamepad is pointing at. A pale wash of the FOCUS_COLOR (#3B82F6) that already
# marks the focused pane and the focus arrow, so "where the pad is" says the same thing one
# level down rather than inventing a fourth color. It has to stay light: the row's text is
# systemTextColor and its indicator ring is drawn in black, so a saturated fill fights both.
CURSOR_BG = "#BFDBFE"

# How large the painted indicator is drawn, as a multiple of the row's own text size -- and
# one number for both styles, because what limits it is the row's text box, which the font
# decides and which says nothing about whether a square or a ring is drawn in it.
#
# A row is painted with indicatoron=False, so it carries a background *and a frame* of its
# own, and macOS draws that frame 3px inside the row's edge; the row's height is the font's
# linespace plus its border, and the indicator is centered in it. The ring used to be 1.5x,
# which at the LCS panel's 18pt is 27px of a 28px text box -- so its own filled ground landed
# on the frame and painted it out, top and bottom, wherever a list is packed tight enough to
# have no padding to spare. The Sensor Track's ten actions are that list; the Pi and the Deck
# never showed it, because X11 draws no frame on these rows at all.
#
# 1.33 is the ceiling, measured on macOS off screenshots of such a row at every size the app
# draws rows at, 12pt through 27pt: at or under it the frame comes through untouched, above
# it the indicator paints over it. Coming down costs no height anywhere -- a row is as tall
# as its text at every ratio from 1.5 down to 0.9 -- and the indicator is still drawn half
# again the size of the one Tk would draw itself.
INDICATOR_SCALE = 1.3

# What a painted row spends on itself before its text begins, in pixels, over and above the
# indicator: the padding either side of the row's contents, the frame it is drawn with, and
# the gap between the indicator and the words beside it.
#
# Measured rather than added up. A row was painted at 14, 18, 21 and 27pt and its requested
# width compared with what Tk says its text alone measures; the difference came to the
# indicator plus 78px at every one of them -- the indicator grows with the font and the rest
# of this does not. Rounded up by 2, and generous on X11 either way, which draws a narrower
# frame than macOS: a caller that leaves a row too little room breaks a line early, and one
# that leaves it too much runs the row off the edge of the screen.
ROW_CHROME_PX = 80

# The font a row is drawn in. Named here because two things have to agree about it: what
# decorate_checkbox paints with, and what fit_row_size measures with.
ROW_FONT = "TkDefaultFont"


class CheckBoxGroup(ButtonGroup):
    @staticmethod
    def indicator_size_for(size: int, style: Literal["checkbox", "radio"]) -> int:
        """How big the painted indicator is for a row of text size size.

        style is taken and deliberately not read: the answer is how much room the row's text
        box has, which is the same either way. It stays in the signature because every caller
        has the style to hand and reads better saying which indicator it means -- and because
        a style whose shape wants less of that room can then be given less of it. See
        INDICATOR_SCALE for where the number comes from.
        """
        return int(size * INDICATOR_SCALE)

    @classmethod
    def row_chrome_for(cls, size: int, style: Literal["checkbox", "radio"] = "radio") -> int:
        """How much of a row's width is spent before its text, at text size size.

        The indicator, which grows with the font, and everything around it, which does not;
        see ROW_CHROME_PX. What a caller sizing or wrapping a row has to take off the width it
        has before asking whether the words fit.
        """
        return cls.indicator_size_for(size, style) + ROW_CHROME_PX

    @classmethod
    def fit_row_size(
        cls,
        master,
        texts: Iterable[str],
        width: int,
        ceiling: int,
        floor: int = None,
        style: Literal["checkbox", "radio"] = "radio",
    ) -> int:
        """The largest size, at or below ceiling, at which every one of texts fits width.

        A list is drawn at the size its caller asks for wherever there is room for it, and a
        step down at a time where there is not -- rather than at a size chosen for one screen
        and hoped for on the others. The same list of modes is 666px wide on a Pi and 400 on a
        Deck pane; the ceiling is what the caller would like, and this is what the screen in
        front of it can actually hold.

        Measured with the font the rows are painted in (see ROW_FONT), on the machine drawing
        them, so it needs to know nothing about that machine: a display whose fonts render
        wider simply settles a size lower. A screen that cannot be measured at all keeps the
        ceiling -- the answer it would have had before anything asked -- and the wrap a caller
        sets from row_chrome_for is what keeps that honest.

        floor is where stepping down stops, and it is a real answer rather than a failure: at
        that point the words are better broken onto a second line than shrunk further.
        """
        ceiling = int(ceiling)
        bottom = ceiling if floor is None else min(int(floor), ceiling)
        wanted = [str(text) for text in texts if str(text)]
        if not wanted:
            return ceiling
        root = getattr(master, "tk", master)
        for size in range(ceiling, bottom - 1, -1):
            budget = int(width) - cls.row_chrome_for(size, style)
            try:
                font = tkfont.Font(root=root, font=(ROW_FONT, size))
                if all(font.measure(text) <= budget for text in wanted):
                    return size
            except (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError):
                return ceiling
        return bottom

    @classmethod
    def indicator_images(
        cls,
        widget,
        indicator_size: int,
        style: Literal["checkbox", "radio"] = "checkbox",
        thickness: int = 2,
        border_color: str = "black",
        check_color: str = LIONEL_BLUE,
        background: str = WHITE,
    ):
        """The (unselected, selected) indicator pair for one row, painted on background.

        Kept on the widget so Tk does not collect the images, and cached there so a row is
        painted once rather than per press. background is part of the key: the pair is
        *filled* with it rather than drawn over a transparent ground, so two backgrounds on one
        widget -- which is what a tinted cursor row is -- need two pairs. Sharing one would show
        whichever ground was painted first as a patch around the ring on the other.
        """
        # IMPORTANT: keep refs so Tk doesn't GC the images
        if not hasattr(widget, "_pytrain_images"):
            widget._pytrain_images = {}

        key = (style, indicator_size, background)
        pair = widget._pytrain_images.get(key)
        if pair is not None:
            return pair

        unsel = tk.PhotoImage(width=indicator_size, height=indicator_size)
        sel = tk.PhotoImage(width=indicator_size, height=indicator_size)

        # Start transparent, then paint background (optional; looks cleaner)
        _fill(unsel, background)
        _fill(sel, background)

        if style == "checkbox":
            # Unchecked: empty square
            _draw_rect_outline(unsel, border_color, thickness=max(1, thickness), inset=1)

            # Checked: same square + checkmark
            _draw_rect_outline(sel, border_color, thickness=max(1, thickness), inset=1)
            _draw_checkmark(sel, check_color, thickness=max(2, indicator_size // 6))

        else:  # "radio"
            # Unchecked: ring
            _draw_circle_outline(unsel, border_color, thickness=max(1, thickness), inset=1)

            # Checked: ring + filled dot
            _draw_circle_outline(sel, border_color, thickness=max(1, thickness), inset=1)
            _draw_circle_filled(sel, check_color, radius_frac=0.35)

        pair = (unsel, sel)
        widget._pytrain_images[key] = pair
        return pair

    @classmethod
    def decorate_checkbox(
        cls,
        widget,
        size: int,
        width: int,
        padx: int = 18,
        pady: int = 6,
        style: Literal["checkbox", "radio"] = "checkbox",
        thickness: int = 2,
        border_color: str = "black",
        check_color: str = LIONEL_BLUE,
        background: str = WHITE,
        wrap: int = 0,
    ) -> None:
        # GuiZero CheckBox wraps Tk Checkbutton
        if isinstance(widget, CheckBox):
            widget = widget.tk

        indicator_size = cls.indicator_size_for(size, style)

        options = {
            "font": (ROW_FONT, size),
            "padx": padx,
            "pady": pady,
            "anchor": "w",
            "width": width,
        }
        if wrap:
            # Where a label is longer than the row it is drawn in, the row is made taller
            # rather than the label cut: a row runs off the right edge of a narrow pane
            # silently, and what it takes with it is the end of the line -- which on the LCS
            # panel's mode rows is the block of TMCC IDs the row is chosen for. justify keeps
            # the second line under the first rather than centered against it, so a wrapped
            # row still reads from the same left edge as the rows above and below it.
            options["wraplength"] = wrap
            options["justify"] = "left"
        widget.config(**options)

        unsel, sel = cls.indicator_images(
            widget,
            indicator_size,
            style=style,
            thickness=thickness,
            border_color=border_color,
            check_color=check_color,
            background=background,
        )

        widget.config(
            image=unsel,
            selectimage=sel,
            compound="left",
            indicatoron=False,
        )

    def __init__(
        self,
        master,
        size: int = 22,
        width: int = None,
        style: Literal["checkbox", "radio"] = "checkbox",
        thickness: int = 2,
        cursor: bool = False,
        cursor_bg: str = CURSOR_BG,
        stretch: bool = False,
        row_leads: Mapping[str, int] = None,
        wrap: int = 0,
        **kwargs,
    ):
        # Recorded before the parent class is initialized, because it builds the rows from its
        # own __init__ -- through _refresh_options, which paints whatever rows it finds.
        self._padx = kwargs.pop("padx", 18)
        self._pady = kwargs.pop("pady", 6)
        self._dis_width = width
        self._row_size = size
        self._row_style = style
        self._row_thickness = thickness
        self._stretch = stretch
        self._row_wrap = int(wrap or 0)
        self._row_leads = self._as_leads(row_leads)
        # The tinted row, named here rather than only in _init_cursor: a group without a cursor
        # never gets that far, and the property reads better answering None than not existing.
        self._cursor: str | None = None
        if stretch:
            # The frame has to fill its container before the rows can fill the frame, and
            # guizero packs a container with fill=X only when its own width is the string
            # "fill" -- see Container._pack_widget. Not the width argument above: that one is
            # the width of a row, and stretch_rows says why a row is not given one.
            kwargs["width"] = "fill"
        super().__init__(master, **kwargs)

        # Again after the parent class has finished: its own __init__ resizes the group once
        # the rows exist, and a row given an explicit width there loses the one set below.
        # Repainting is cheap -- the indicator images are cached on the row.
        self.decorate_rows()
        self.stretch_rows()
        self.lead_rows()

        # Opt-in, and deliberately so: this component is shared with the Admin panel, the
        # catalog's sort radios and the AMC2 page selector, and a cursor -- or the selectcolor
        # change that goes with it -- appearing on those would be a change nobody asked for.
        if cursor:
            self._init_cursor(
                [(rbutton.value, rbutton.tk) for rbutton in self._rbuttons],
                self.indicator_size_for(size, style),
                style=style,
                thickness=thickness,
                cursor_bg=cursor_bg,
            )

    def _refresh_options(self) -> None:
        """Paint the rows guizero has just rebuilt.

        Every change to a group's options -- clear, append, insert, remove --
        routes through here, and the parent class *destroys* its rows and creates plain
        Tk radiobuttons in their place: default font, native indicator, no padding. So a group
        whose options are replaced at runtime silently lost everything decorate_checkbox
        installs, which is why the LCS panel's mode radios came out as dots barely visible
        beside its module radios -- those are built once and never rebuilt.

        Called from ButtonGroup.__init__ as well, where the rows are first created.
        """
        super()._refresh_options()
        self.decorate_rows()
        self.stretch_rows()
        self.lead_rows()
        self._rearm_cursor()

    def resize(self, width, height) -> None:
        """Stretch the rows again once the parent class has resized them.

        ButtonGroup.append resizes the group *after* rebuilding its rows, and a resize
        hands the group's own width to every row -- which for a filling group means setting a
        row's width to "fill", and guizero re-displays a container whenever that happens. That
        re-grid drops the sticky stretch_rows sets, so the stretch has to follow the resize
        as well as the rebuild -- and with it the leads, which are grid options of the same kind.
        """
        super().resize(width, height)
        self.stretch_rows()
        self.lead_rows()

    def decorate_rows(self) -> None:
        """Give every row of the group the indicator, font and padding it was asked for.

        Guarded, because _refresh_options is reachable before this class has recorded what to
        paint with -- a subclass, or a group built by __new__ as the cursor tests build one --
        and a group that has said nothing about its rows wants them left alone.
        """
        if not hasattr(self, "_row_style"):
            return
        for widget in self.tk.winfo_children():
            self.decorate_checkbox(
                widget,
                self._row_size,
                self._dis_width,
                self._padx,
                self._pady,
                style=self._row_style,
                thickness=self._row_thickness,
                wrap=getattr(self, "_row_wrap", 0),
            )

    def stretch_rows(self) -> None:
        """Give every row of a stretch group the full width of the group's frame.

        Opt-in, because it is a change of appearance and this component is shared with the
        Admin panel, the catalog's sort radios and the AMC2 page selector. guizero grids a
        row from its align="left", i.e. sticky="W", so each row is only as wide as its own
        label: "ACC TMCC ID 1" comes out visibly shorter than the row above it, which
        goes unnoticed until the rows are painted -- decorate_checkbox draws them with
        indicatoron=False, and a row then carries a background of its own that shows exactly
        where it ends. Handing the row's column the frame's spare width and stretching each
        row across it makes them one width, and that width is the containing box's, since a
        stretch group's frame fills its container.

        Deliberately not an explicit row width: a Checkbutton showing an image reads -width
        in pixels and *drops* the row's padx with it (306 px at width=300 whatever the padx),
        which would pull every indicator flush against the row's left edge.

        Re-applied after every rebuild and every resize rather than set once, because neither
        leaves a grid option standing -- see _refresh_options and resize. Guarded like
        decorate_rows, and for the same reason: both are reachable before this class has
        recorded anything.
        """
        if not getattr(self, "_stretch", False):
            return
        for row in getattr(self, "_rbuttons", None) or ():
            try:
                # A vertical group stacks its rows down column 0; a horizontal one lays them
                # along row 0 from column 1, so the column is the row's own to say.
                grid = getattr(row, "grid", None)
                self.tk.grid_columnconfigure(grid[0] if grid else 0, weight=1)
                row.tk.grid_configure(sticky="ew")
            except (AttributeError, IndexError, RuntimeError, tk.TclError, TypeError, ValueError):
                continue

    @staticmethod
    def _as_leads(leads: Mapping[str, int] = None) -> dict[str, int]:
        """The leads as this class holds them: option values as strings, pixels as ints.

        Values, because that is what a row answers with -- _rbuttons carries no index -- and
        strings, because guizero stores whatever it was handed and answers in kind.
        """
        return {str(value): int(pixels) for value, pixels in (leads or {}).items()}

    @property
    def row_leads(self) -> dict[str, int]:
        """How far each named row is held off the row above it, in pixels.

        Whitespace *between groups of rows* rather than between every pair of them, which is
        what pady already sets: the LCS panel's mode radios list two accessory modes and then
        two switch modes, and the operator reading them needs to see two lists rather than
        one of four. A row not named here is packed as tight against the row above it as
        every other, so a group that says nothing about its rows is untouched.

        Grid padding, so it lands outside the row's own painted background and reads as a gap
        between two blocks rather than as a taller row; see lead_rows() for why it has to be
        re-applied rather than set once.
        """
        return dict(getattr(self, "_row_leads", None) or {})

    @row_leads.setter
    def row_leads(self, leads: Mapping[str, int]) -> None:
        self._row_leads = self._as_leads(leads)
        self.lead_rows()

    def lead_rows(self) -> None:
        """Hold every row named in row_leads off the row above it.

        Re-applied after every rebuild and every resize, like stretch_rows and for the same
        reason: guizero re-grids a container's children from the options it recorded, and
        grid padding is not among them. Every row is configured rather than only those
        named, so a group whose rows are replaced with a differently grouped list -- which
        is what choosing another LCS module does -- cannot leave a gap standing above a row
        that no longer begins anything.

        Guarded like decorate_rows: both are reachable before this class has recorded
        anything, and a group that has said nothing about its rows wants them left alone.
        A hidden row is left alone as well: Tk's grid configure *manages* a widget the grid
        has forgotten, so padding one would put it back on screen.
        """
        if not hasattr(self, "_row_leads"):
            return
        leads = self._row_leads
        for row in getattr(self, "_rbuttons", None) or ():
            if not getattr(row, "visible", True):
                continue
            lead = leads.get(str(getattr(row, "value", "")), 0)
            try:
                row.tk.grid_configure(pady=(lead, 0))
            except (AttributeError, RuntimeError, tk.TclError, TypeError, ValueError):
                continue

    def _rearm_cursor(self) -> None:
        """Arm the cursor again over rows guizero has just replaced.

        A cursor is armed over the *widgets* a group holds, and a rebuild destroys every one
        of them: without this the tint would be reapplied to a dead widget, which is a
        TclError rather than a lost highlight. The LCS panel's mode rows are the list this
        happens to -- they are replaced whenever the module or the address changes -- and the
        component knows when its rows go, so it is the component that re-arms.

        Nothing happens for a group that never armed one, which is every other group in the
        app. The tinted row is asked for again afterwards and comes back only if the new list
        holds it: a rebuild that replaces one module's modes with another's is a rebuild the
        pad's position no longer means anything on, and clear() empties the list outright, so
        the pair of calls a replacement is made of drops it. Where the pad then steps from is
        the reader's business; see LcsConfigPanel.pad_cursor.
        """
        if getattr(self, "_cursor_rows", None) is None:
            # Not an opting group -- and reachable before __init__ has armed one at all, since
            # ButtonGroup builds its rows from its own constructor.
            return
        tinted = self._cursor
        self._init_cursor(
            [(rbutton.value, rbutton.tk) for rbutton in self._rbuttons],
            self._cursor_indicator_size,
            style=self._cursor_style,
            thickness=self._cursor_thickness,
            cursor_bg=self._cursor_bg,
        )
        self.cursor = tinted

    def _init_cursor(
        self,
        rows,
        indicator_size: int,
        style: Literal["checkbox", "radio"] = "checkbox",
        thickness: int = 2,
        cursor_bg: str = CURSOR_BG,
    ) -> None:
        """Arms the row cursor over rows, a sequence of (value, tk widget) pairs.

        Separate from __init__ because everything the cursor needs is these rows and the
        numbers used to paint them: the logic is then reachable without a display, which is
        how it is tested. Nothing is drawn here -- the tinted images are painted on demand and
        cached -- so arming the cursor costs one config per row and no images at all.
        """
        self._cursor_rows = list(rows)
        self._cursor_indicator_size = indicator_size
        self._cursor_style = style
        self._cursor_thickness = thickness
        self._cursor_bg = cursor_bg
        self._cursor = None
        for _value, widget in self._cursor_rows:
            widget._pytrain_row_bg = widget.cget("background")
            self._neutralise_select_color(widget)

    @staticmethod
    def _neutralise_select_color(widget) -> None:
        """Stops Tk painting its own bar across the selected row.

        These rows are drawn with indicatoron=False, and Tk documents that for a borderless
        indicator selectColor is used as the background of the *entire* widget while it is
        selected. Nothing here ever set it, so it is still Tk's own default -- #b03060, a
        filled maroon bar. That is about the strongest "this is set" signal the panel can
        produce, and with the cursor now owning the filled bar there must be only one of them:
        two, meaning opposite things, would be worse than the confusion being fixed.

        The row's own background is the value that says "no bar"; selectcolor="" is Tk's
        documented "no special color" form and is the fallback where a platform refuses a
        color there.
        """
        try:
            widget.config(selectcolor=widget.cget("background"))
        except tk.TclError:
            widget.config(selectcolor="")

    @property
    def row_values(self) -> tuple[str, ...]:
        """The value of every row, in the order they are drawn.

        What a caller stepping the cursor needs and has no other way to ask for: options
        answers with whatever it was handed, while a row answers with the string Tk holds --
        which is what value and cursor are both read and written as. Read off the rows for
        that reason, as row_leads is.
        """
        return tuple(str(getattr(row, "value", "")) for row in getattr(self, "_rbuttons", None) or ())

    @property
    def cursor(self) -> str | None:
        """The value of the row currently tinted, or None. Never the selection.

        The pad's position, as against value, which is what the device is set to. The two are
        deliberately independent: neither setter moves the other, so an option stepped over
        cannot read as an option chosen.
        """
        return getattr(self, "_cursor", None)

    @property
    def cursor_row(self):
        """The widget of the row the cursor is on, or None where nothing is tinted.

        What a caller has to have to bring that row into view when the list is longer than
        the room it is drawn in -- see ScrollBox.show_widget. The widget rather than its
        index, because the rows are rebuilt at runtime and an index outlives the row it
        named; this is read out of the same pairs the tint itself is painted through, so it
        cannot come to point at a row that is gone.
        """
        current = self._cursor
        for row_value, widget in getattr(self, "_cursor_rows", None) or ():
            if row_value == current:
                return widget
        return None

    @cursor.setter
    def cursor(self, value) -> None:
        rows = getattr(self, "_cursor_rows", None)
        if rows is None:
            # Not an opting group: nothing to tint, and silently so, since the caller that set
            # this is the one that asked for the group without a cursor.
            return
        target = None if value is None else str(value)
        if target is not None and not any(target == row_value for row_value, _ in rows):
            # A value the list does not hold clears the tint rather than raising: the same
            # reading the selection gets, where guizero answers with whatever string it was
            # handed -- "None" among them.
            target = None
        current = self._cursor
        if target == current:
            return
        self._cursor = target
        for row_value, widget in rows:
            # Two rows are reconfigured -- the one it leaves and the one it lands on -- rather
            # than the whole group repainted.
            if row_value == current:
                self._paint_cursor(widget, False)
            elif row_value == target:
                self._paint_cursor(widget, True)

    def _paint_cursor(self, widget, tinted: bool) -> None:
        background = self._cursor_bg if tinted else getattr(widget, "_pytrain_row_bg", WHITE)
        unsel, sel = self.indicator_images(
            widget,
            self._cursor_indicator_size,
            style=self._cursor_style,
            thickness=self._cursor_thickness,
            background=self._cursor_bg if tinted else WHITE,
        )
        widget.config(
            background=background,
            activebackground=background,
            selectcolor=background,
            image=unsel,
            selectimage=sel,
        )

    #
    # def show(self):
    #     super().show()
    #     if self.visible and not self.tk.winfo_ismapped():
    #         print("forcing display...")
    #         self.hide()
    #         super().show()


def _fill(img, color: str) -> None:
    w, h = img.width(), img.height()
    img.put(color, to=(0, 0, w, h))


def _draw_rect_outline(img, color: str, thickness: int = 2, inset: int = 1) -> None:
    w, h = img.width(), img.height()
    x0, y0 = inset, inset
    x1, y1 = w - 1 - inset, h - 1 - inset
    t = max(1, thickness)

    for k in range(t):
        # top
        img.put(color, to=(x0 + k, y0 + k, x1 - k + 1, y0 + k + 1))
        # bottom
        img.put(color, to=(x0 + k, y1 - k, x1 - k + 1, y1 - k + 1))
        # left
        img.put(color, to=(x0 + k, y0 + k, x0 + k + 1, y1 - k + 1))
        # right
        img.put(color, to=(x1 - k, y0 + k, x1 - k + 1, y1 - k + 1))


def _draw_line(img, color: str, x0: int, y0: int, x1: int, y1: int, thickness: int = 2) -> None:
    # Simple Bresenham-ish line with thickness (good enough for tiny icons)
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    w, h = img.width(), img.height()
    t = max(1, thickness)
    r = t // 2

    while True:
        for yy in range(y0 - r, y0 - r + t):
            if 0 <= yy < h:
                for xx in range(x0 - r, x0 - r + t):
                    if 0 <= xx < w:
                        img.put(color, to=(xx, yy, xx + 1, yy + 1))

        if x0 == x1 and y0 == y1:
            break

        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy


def _draw_checkmark(img, color: str, thickness: int = 3) -> None:
    # Tuned proportions for small squares
    w, h = img.width(), img.height()
    # Start lower-left, bend near centers, end upper-right
    x_a, y_a = int(w * 0.22), int(h * 0.55)
    x_b, y_b = int(w * 0.42), int(h * 0.72)
    x_c, y_c = int(w * 0.78), int(h * 0.28)

    _draw_line(img, color, x_a, y_a, x_b, y_b, thickness)
    _draw_line(img, color, x_b, y_b, x_c, y_c, thickness)


def _draw_circle_outline(img, color: str, thickness: int = 2, inset: int = 1) -> None:
    w, h = img.width(), img.height()
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    r_outer = min(w, h) / 2.0 - inset
    r_inner = max(0.0, r_outer - thickness)

    # Draw ring: pixels with distance in [r_inner, r_outer]
    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            d2 = dx * dx + dy * dy
            if (r_inner * r_inner) <= d2 <= (r_outer * r_outer):
                img.put(color, to=(x, y, x + 1, y + 1))


def _draw_circle_filled(img, color: str, radius_frac: float = 0.35) -> None:
    w, h = img.width(), img.height()
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    r = min(w, h) * radius_frac
    r2 = r * r

    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            # Fills circle pixels within radius
            if (dx * dx + dy * dy) <= r2:
                img.put(color, to=(x, y, x + 1, y + 1))
