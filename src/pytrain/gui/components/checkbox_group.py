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
from typing import Literal

from guizero import ButtonGroup, CheckBox

from ..guizero_base import LIONEL_BLUE

BORDER_COLOR = "#9a9a9a"
LIGHT_GRAY = "#cfcfcf"
WHITE = "#ffffff"
# The row the gamepad is pointing at. A pale wash of the FOCUS_COLOR (#3B82F6) that already
# marks the focused pane and the focus arrow, so "where the pad is" says the same thing one
# level down rather than inventing a fourth colour. It has to stay light: the row's text is
# systemTextColor and its indicator ring is drawn in black, so a saturated fill fights both.
CURSOR_BG = "#BFDBFE"


class CheckBoxGroup(ButtonGroup):
    @staticmethod
    def indicator_size_for(size: int, style: Literal["checkbox", "radio"]) -> int:
        """How big the painted indicator is for a row of text size ``size``."""
        return int(size * 1.5) if style == "radio" else int(size * 1.3)

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
        """The (unselected, selected) indicator pair for one row, painted on ``background``.

        Kept on the widget so Tk does not collect the images, and cached there so a row is
        painted once rather than per press. ``background`` is part of the key: the pair is
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
    ) -> None:
        # GuiZero CheckBox wraps Tk Checkbutton
        if isinstance(widget, CheckBox):
            widget = widget.tk

        indicator_size = cls.indicator_size_for(size, style)

        widget.config(
            font=("TkDefaultFont", size),
            padx=padx,
            pady=pady,
            anchor="w",
            width=width,
        )

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

        Every change to a group's options -- ``clear``, ``append``, ``insert``, ``remove`` --
        routes through here, and the parent class *destroys* its rows and creates plain
        Tk radiobuttons in their place: default font, native indicator, no padding. So a group
        whose options are replaced at runtime silently lost everything ``decorate_checkbox``
        installs, which is why the LCS panel's mode radios came out as dots barely visible
        beside its module radios -- those are built once and never rebuilt.

        Called from ``ButtonGroup.__init__`` as well, where the rows are first created.
        """
        super()._refresh_options()
        self.decorate_rows()
        self.stretch_rows()

    def resize(self, width, height) -> None:
        """Stretch the rows again once the parent class has resized them.

        ``ButtonGroup.append`` resizes the group *after* rebuilding its rows, and a resize
        hands the group's own width to every row -- which for a filling group means setting a
        row's width to "fill", and guizero re-displays a container whenever that happens. That
        re-grid drops the sticky ``stretch_rows`` sets, so the stretch has to follow the resize
        as well as the rebuild.
        """
        super().resize(width, height)
        self.stretch_rows()

    def decorate_rows(self) -> None:
        """Give every row of the group the indicator, font and padding it was asked for.

        Guarded, because ``_refresh_options`` is reachable before this class has recorded what
        to paint with -- a subclass, or a group built by ``__new__`` as the cursor tests build
        one -- and a group that has said nothing about its rows wants them left alone.
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
            )

    def stretch_rows(self) -> None:
        """Give every row of a ``stretch`` group the full width of the group's frame.

        Opt-in, because it is a change of appearance and this component is shared with the
        Admin panel, the catalog's sort radios and the AMC2 page selector. guizero grids a
        row from its align="left", i.e. sticky="W", so each row is only as wide as its own
        label: "ACCessory, 1 TMCC ID" comes out visibly shorter than the row above it, which
        goes unnoticed until the rows are painted -- ``decorate_checkbox`` draws them with
        indicatoron=False, and a row then carries a background of its own that shows exactly
        where it ends. Handing the row's column the frame's spare width and stretching each
        row across it makes them one width, and that width is the containing box's, since a
        stretch group's frame fills its container.

        Deliberately not an explicit row width: a Checkbutton showing an image reads -width
        in pixels and *drops* the row's padx with it (306 px at width=300 whatever the padx),
        which would pull every indicator flush against the row's left edge.

        Re-applied after every rebuild and every resize rather than set once, because neither
        leaves a grid option standing -- see ``_refresh_options`` and ``resize``. Guarded like
        ``decorate_rows``, and for the same reason: both are reachable before this class has
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

    def _init_cursor(
        self,
        rows,
        indicator_size: int,
        style: Literal["checkbox", "radio"] = "checkbox",
        thickness: int = 2,
        cursor_bg: str = CURSOR_BG,
    ) -> None:
        """Arms the row cursor over ``rows``, a sequence of ``(value, tk widget)`` pairs.

        Separate from ``__init__`` because everything the cursor needs is these rows and the
        numbers used to paint them: the logic is then reachable without a display, which is
        how it is tested. Nothing is drawn here -- the tinted images are painted on demand and
        cached -- so arming the cursor costs one ``config`` per row and no images at all.
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

        These rows are drawn with ``indicatoron=False``, and Tk documents that for a borderless
        indicator ``selectColor`` is used as the background of the *entire* widget while it is
        selected. Nothing here ever set it, so it is still Tk's own default -- ``#b03060``, a
        filled maroon bar. That is about the strongest "this is set" signal the panel can
        produce, and with the cursor now owning the filled bar there must be only one of them:
        two, meaning opposite things, would be worse than the confusion being fixed.

        The row's own background is the value that says "no bar"; ``selectcolor=""`` is Tk's
        documented "no special colour" form and is the fallback where a platform refuses a
        colour there.
        """
        try:
            widget.config(selectcolor=widget.cget("background"))
        except tk.TclError:
            widget.config(selectcolor="")

    @property
    def cursor(self) -> str | None:
        """The value of the row currently tinted, or None. Never the selection.

        The pad's position, as against ``value``, which is what the device is set to. The two
        are deliberately independent: neither setter moves the other, so an option stepped over
        cannot read as an option chosen.
        """
        return getattr(self, "_cursor", None)

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
