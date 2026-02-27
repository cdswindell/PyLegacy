#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only

from __future__ import annotations

import math
import tkinter as tk
from typing import Callable, Any

from guizero import Box


class AnalogGaugeWidget(Box):
    """
    A guizero widget (Box) containing a Tk Canvas analog gauge.

    - Black-on-white analog gauge face (optimized for 120x120).
    - set_value(0..100) updates needle.
    - Tap/click triggers `command(current_value)` on release.
    - Press feedback: inverts colors while pressed.

    Usage:
        g = AnalogGaugeWidget(parent, label="Fuel", size=120, command=...)
        g.set_value(73)
    """

    def __init__(
        self,
        master,
        label: str,
        size: int = 150,
        command: Callable | None = None,  # callable(int)->None
        args: list[Any] | None = None,
        start_deg: float = 210.0,
        end_deg: float = -30.0,
        align=None,
        grid=None,
        visible=True,
        **kwargs,
    ):
        super().__init__(
            master,
            width=size,
            height=size,
            align=align,
            grid=grid,
            visible=visible,
            **kwargs,
        )

        self.size = int(size)
        self.label = label
        self._command = command
        self._args = args
        self.start_deg = float(start_deg)
        self.end_deg = float(end_deg)
        self.value = 0

        self._inverted = False

        # Track items by how they should be recolored
        self._stroke_items: list[int] = []  # arcs + border rectangles (outline)
        self._line_items: list[int] = []  # tick lines + needle (fill)
        self._text_items: list[int] = []  # E/F + label (fill)
        self._knockout_items: list[int] = []  # rectangles behind E/F (fill=bg)

        self._border_id: int | None = None
        self._needle_id: int | None = None
        self._hub_id: int | None = None

        self.canvas = tk.Canvas(
            self.tk,
            width=self.size,
            height=self.size,
            bg="white",
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.tk.pack_propagate(False)
        self.canvas.pack(expand=True)

        self._draw_static()
        self.set_value(0)

        # Touch/mouse behavior: invert on press, trigger on release.
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    @property
    def command(self) -> Callable | None:
        return self._command

    @command.setter
    def command(self, callback: Callable | None) -> None:
        self._command = callback

    @property
    def args(self) -> list[Any] | None:
        return self._args

    @args.setter
    def args(self, args: list[Any] | None) -> None:
        self._args = args

    def _map_value_to_deg(self, value_0_100: float) -> float:
        v = max(0.0, min(100.0, float(value_0_100)))
        t = v / 100.0
        return self.start_deg + t * (self.end_deg - self.start_deg)

    # ----------------------------
    # Theme / press feedback
    # ----------------------------
    def _apply_theme(self) -> None:
        fg = "white" if self._inverted else "black"
        bg = "black" if self._inverted else "white"

        self.canvas.config(bg=bg)

        # Arcs + border: outline only, never fill
        for item in self._stroke_items:
            try:
                self.canvas.itemconfig(item, outline=fg)
                self.canvas.itemconfig(item, fill="")  # keep transparent
            except tk.TclError:
                pass

        # Lines: fill controls color
        for item in self._line_items:
            try:
                self.canvas.itemconfig(item, fill=fg)
            except tk.TclError:
                pass

        # Text: fill controls color
        for item in self._text_items:
            try:
                self.canvas.itemconfig(item, fill=fg)
            except tk.TclError:
                pass

        # Knockouts: match background
        for item in self._knockout_items:
            try:
                self.canvas.itemconfig(item, fill=bg)
            except tk.TclError:
                pass

        # Hub: filled shape
        if self._hub_id is not None:
            self.canvas.itemconfig(self._hub_id, fill=fg, outline=fg)

        # Needle already in _line_items, but if recreated after theme toggle this keeps it consistent
        if self._needle_id is not None:
            self.canvas.itemconfig(self._needle_id, fill=fg)

    # ----------------------------
    # Draw static face
    # ----------------------------
    def _draw_static(self) -> None:
        s = self.size

        self.canvas.delete("all")
        self._stroke_items.clear()
        self._line_items.clear()
        self._text_items.clear()
        self._knockout_items.clear()
        self._border_id = None

        # Gauge geometry tuned for 120x120 cells
        cx, cy = s / 2, s * 0.50
        r_outer = s * 0.38
        r_inner = s * 0.33
        r_tick = s * 0.30
        rim_w = max(2, int(s * 0.025))

        # Arc bbox derived from r_outer
        x0, y0 = cx - r_outer, cy - r_outer
        x1, y1 = cx + r_outer, cy + r_outer

        # Normalize arc sweep for Tk
        arc_start = self.start_deg
        arc_extent = self.end_deg - self.start_deg
        if arc_extent < 0:
            arc_start = self.end_deg
            arc_extent = -arc_extent

        # Outer + inner rim arcs (stroke items)
        arc1 = self.canvas.create_arc(
            x0, y0, x1, y1, start=arc_start, extent=arc_extent, style="arc", width=rim_w, outline="black"
        )
        self._stroke_items.append(arc1)

        xi0, yi0 = cx - r_inner, cy - r_inner
        xi1, yi1 = cx + r_inner, cy + r_inner
        arc2 = self.canvas.create_arc(
            xi0,
            yi0,
            xi1,
            yi1,
            start=arc_start,
            extent=arc_extent,
            style="arc",
            width=max(1, rim_w - 1),
            outline="black",
        )
        self._stroke_items.append(arc2)

        # Ticks (line items)
        majors = {0, 5, 10}
        for i in range(0, 11):
            v = i / 10.0
            ang = math.radians(self._map_value_to_deg(v * 100))
            is_major = i in majors

            tick_len = s * (0.060 if is_major else 0.032)
            tick_w = 2 if is_major else 1

            x1t = cx + (r_tick - tick_len) * math.cos(ang)
            y1t = cy - (r_tick - tick_len) * math.sin(ang)
            x2t = cx + r_tick * math.cos(ang)
            y2t = cy - r_tick * math.sin(ang)

            tid = self.canvas.create_line(x1t, y1t, x2t, y2t, width=tick_w, fill="black")
            self._line_items.append(tid)

        # E / F: larger, more inward, bigger knockout
        ef_font = ("TkDefaultFont", max(10, int(s * 0.095)), "bold")
        ef_r = r_inner * 0.52
        ef_margin_deg = 22.0

        e_ang = math.radians(self._map_value_to_deg(0) + ef_margin_deg)
        f_ang = math.radians(self._map_value_to_deg(100) - ef_margin_deg)

        ex = cx + ef_r * math.cos(e_ang)
        ey = cy - ef_r * math.sin(e_ang)
        fx = cx + ef_r * math.cos(f_ang)
        fy = cy - ef_r * math.sin(f_ang)

        e_id = self.canvas.create_text(ex, ey, text="E", font=ef_font, fill="black")
        f_id = self.canvas.create_text(fx, fy, text="F", font=ef_font, fill="black")
        self._text_items.extend([e_id, f_id])

        # Knockout rectangles behind E/F (fill matches bg on invert)
        pad = 3
        for tid in (e_id, f_id):
            xk0, yk0, xk1, yk1 = self.canvas.bbox(tid)
            rid = self.canvas.create_rectangle(xk0 - pad, yk0 - pad, xk1 + pad, yk1 + pad, fill="white", outline="")
            self._knockout_items.append(rid)
            self.canvas.lift(tid, rid)  # ensure letter sits above its knockout

        # Label: slightly larger and lowered a bit from the gauge
        label_font = ("TkDefaultFont", max(11, int(s * 0.115)), "bold")
        label_y = cy + r_outer * 0.82
        lbl = self.canvas.create_text(cx, label_y, text=self.label, font=label_font, fill="black")
        self._text_items.append(lbl)

        # Border: match Master buttons (1px on half-pixel coords), outline-only
        self._border_id = self.canvas.create_rectangle(
            0.5,
            0.5,
            s - 0.5,
            s - 0.5,
            outline="black",
            width=1,
        )
        self._stroke_items.append(self._border_id)

        self._apply_theme()

    # ----------------------------
    # Dynamic needle
    # ----------------------------
    def set_value(self, value_0_100: int) -> None:
        self.value = int(max(0, min(100, value_0_100)))

        s = self.size
        cx, cy = s / 2, s * 0.50
        r_needle = s * 0.29
        hub_r = max(5, int(s * 0.04))

        ang = math.radians(self._map_value_to_deg(self.value))
        x = cx + r_needle * math.cos(ang)
        y = cy - r_needle * math.sin(ang)

        if self._needle_id is not None:
            try:
                self.canvas.delete(self._needle_id)
            except tk.TclError:
                pass
        if self._hub_id is not None:
            try:
                self.canvas.delete(self._hub_id)
            except tk.TclError:
                pass

        fg = "white" if self._inverted else "black"

        self._needle_id = self.canvas.create_line(cx, cy, x, y, width=5, fill=fg)
        self._line_items.append(self._needle_id)

        self._hub_id = self.canvas.create_oval(cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r, fill=fg, outline=fg)

    # ----------------------------
    # Press / release
    # ----------------------------
    def _on_press(self, _event) -> None:
        self._inverted = True
        self._apply_theme()
        # send command if specified
        if callable(self._command):
            print(self._command)
            if self._args is not None:
                print(self._args)
                self._command(*self._args)
            else:
                self._command(self.value)

    def _on_release(self, _event) -> None:
        self._inverted = False
        self._apply_theme()
