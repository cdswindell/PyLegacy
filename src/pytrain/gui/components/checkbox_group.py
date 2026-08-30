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
        **kwargs,
    ):
        # now initialize parent class
        self._padx = kwargs.pop("padx", 18)
        self._pady = kwargs.pop("pady", 6)
        self._dis_width = width
        super().__init__(master, **kwargs)

        # indicator_size = int(size * scale_by)
        for widget in self.tk.winfo_children():
            self.decorate_checkbox(
                widget,
                size,
                self._dis_width,
                self._padx,
                self._pady,
                style=style,
                thickness=thickness,
            )

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
