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

from .guizero_base import LIONEL_BLUE

BORDER_COLOR = "#9a9a9a"
LIGHT_GRAY = "#cfcfcf"
WHITE = "#ffffff"


class CheckBoxGroup(ButtonGroup):
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

        indicator_size = int(size * 1.5) if style == "radio" else int(size * 1.3)

        widget.config(
            font=("TkDefaultFont", size),
            padx=padx,
            pady=pady,
            anchor="w",
            width=width,
        )

        # IMPORTANT: keep refs so Tk doesn't GC the images
        if not hasattr(widget, "_pytrain_images"):
            widget._pytrain_images = {}

        unsel = widget._pytrain_images.get(("unsel", style, indicator_size))
        sel = widget._pytrain_images.get(("sel", style, indicator_size))

        if unsel is None or sel is None:
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
                _draw_circle_filled(sel, check_color, radius_frac=0.28)

            widget._pytrain_images[("unsel", style, indicator_size)] = unsel
            widget._pytrain_images[("sel", style, indicator_size)] = sel

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


def _draw_circle_filled(img, color: str, radius_frac: float = 1) -> None:
    w, h = img.width(), img.height()
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    r = min(w, h) * radius_frac
    r2 = r * r

    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            if (dx * dx + dy * dy) <= r2:
                print(x, y, dx, dy, r2)
                img.put(color, to=(x, y, x + 1, y + 1))
