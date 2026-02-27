#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import math
import tkinter as tk
from typing import Callable

from guizero import Box


class AnalogGaugeWidget(Box):
    """
    A guizero widget (Box) containing a Tk Canvas analog gauge.

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

        self.size = size
        self.label = label
        self._command = command
        self.start_deg = start_deg
        self.end_deg = end_deg
        self.value = 0

        # Create and pack a Tk Canvas inside this guizero Box
        self.canvas = tk.Canvas(
            self.tk,
            width=size,
            height=size,
            bg="white",
            highlightthickness=0,
            bd=0,
            relief="flat",  # avoid any non-uniform Tk border
        )
        self.tk.pack_propagate(False)  # keep Box square
        self.canvas.pack(expand=True)  # center it

        self._needle_id = None
        self._hub_id = None

        self._draw_static()
        self.set_value(0)

        # Click-to-speak
        self.canvas.bind("<Button-1>", self._handle_click)

    @property
    def command(self) -> Callable | None:
        return self._command

    @command.setter
    def command(self, callback):
        self._command = callback

    def _handle_click(self, _event):
        if callable(self._command):
            self._command(self.value)

    def _map_value_to_deg(self, value_0_100: float) -> float:
        v = max(0.0, min(100.0, float(value_0_100)))
        t = v / 100.0
        return self.start_deg + t * (self.end_deg - self.start_deg)

    def _draw_static(self):
        s = self.size

        # Gauge center: slightly above mid to leave room for label
        cx, cy = s / 2, s * 0.50

        # Radii tuned for 120x120 button cell (breathing room for E/F + label)
        r_outer = s * 0.38
        r_inner = s * 0.33
        r_tick = s * 0.30

        rim_w = max(2, int(s * 0.025))  # thinner rim for small sizes

        # Arc bbox derived from r_outer
        x0, y0 = cx - r_outer, cy - r_outer
        x1, y1 = cx + r_outer, cy + r_outer

        # Normalize arc sweep for Tk
        arc_start = self.start_deg
        arc_extent = self.end_deg - self.start_deg
        if arc_extent < 0:
            arc_start = self.end_deg
            arc_extent = -arc_extent

        # Outer + inner rim arcs
        self.canvas.create_arc(
            x0,
            y0,
            x1,
            y1,
            start=arc_start,
            extent=arc_extent,
            style="arc",
            width=rim_w,
            outline="black",
        )

        xi0, yi0 = cx - r_inner, cy - r_inner
        xi1, yi1 = cx + r_inner, cy + r_inner
        self.canvas.create_arc(
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

        # Ticks
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
            self.canvas.create_line(x1t, y1t, x2t, y2t, width=tick_w, fill="black")

        # --- E / F: make them easier to read (bigger + more inward + bigger knockout) ---
        ef_font = ("TkDefaultFont", max(10, int(s * 0.095)), "bold")

        # Pull letters farther inside the face and away from arc endpoints
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

        # Knockout padding (bigger than before to keep ticks/rim from visually merging)
        pad = 3
        for tid in (e_id, f_id):
            xk0, yk0, xk1, yk1 = self.canvas.bbox(tid)
            self.canvas.create_rectangle(
                xk0 - pad,
                yk0 - pad,
                xk1 + pad,
                yk1 + pad,
                fill="white",
                outline="",
            )
            self.canvas.lift(tid)  # keep letter on top

        # Label: slightly larger and a touch lower (but still close to the gauge)
        label_font = ("TkDefaultFont", max(11, int(s * 0.115)), "bold")
        label_y = cy + r_outer * 0.78
        self.canvas.create_text(cx, label_y, text=self.label, font=label_font, fill="black")

        # ---- Button-style outer border (match Master buttons) ----
        # Use a 1px stroke on half-pixel coordinates for a crisp, uniform border.
        border_w = 1
        self.canvas.create_rectangle(
            0.5,
            0.5,
            s - 0.5,
            s - 0.5,
            outline="black",
            width=border_w,
        )

    def set_value(self, value_0_100: int):
        self.value = int(max(0, min(100, value_0_100)))

        s = self.size
        cx, cy = s / 2, s * 0.50
        r_needle = s * 0.29
        hub_r = max(5, int(s * 0.04))

        ang = math.radians(self._map_value_to_deg(self.value))
        x = cx + r_needle * math.cos(ang)
        y = cy - r_needle * math.sin(ang)

        if self._needle_id is not None:
            self.canvas.delete(self._needle_id)
        if self._hub_id is not None:
            self.canvas.delete(self._hub_id)

        self._needle_id = self.canvas.create_line(cx, cy, x, y, width=5, fill="black")
        self._hub_id = self.canvas.create_oval(
            cx - hub_r,
            cy - hub_r,
            cx + hub_r,
            cy + hub_r,
            fill="black",
            outline="black",
        )
