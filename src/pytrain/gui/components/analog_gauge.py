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


class AnalogGauge:
    """
    Black-on-white analog gauge (150x150-friendly) with clickable face.

    - set_value(0..100) updates the needle
    - clicking calls on_click(current_value)
    """

    def __init__(
        self,
        parent_tk,  # e.g. guizero_box.tk
        label: str,  # "Fuel" / "Water"
        size: int = 150,
        on_click=None,  # callable(int)->None
        start_deg: float = 210.0,  # needle left limit
        end_deg: float = -30.0,  # needle right limit
    ):
        self.size = size
        self.label = label
        self.on_click = on_click
        self.start_deg = start_deg
        self.end_deg = end_deg
        self.value = 0

        self.canvas = tk.Canvas(
            parent_tk,
            width=size,
            height=size,
            bg="white",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        self._needle_id = None
        self._hub_id = None

        self._draw_static()
        self.set_value(0)

        # Whole gauge is clickable
        self.canvas.bind("<Button-1>", self._handle_click)

    def _handle_click(self, _event):
        if callable(self.on_click):
            self.on_click(self.value)

    def _map_value_to_deg(self, value_0_100: float) -> float:
        v = max(0.0, min(100.0, float(value_0_100)))
        t = v / 100.0
        return self.start_deg + t * (self.end_deg - self.start_deg)

    def _draw_static(self):
        s = self.size

        # Place center slightly low so the arc “fills” the square icon nicely
        cx, cy = s / 2, s * 0.64

        # Geometry
        r_outer = s * 0.46  # USED: rim radius
        r_inner = s * 0.40  # inner rim (gives a thicker, icon-like ring)
        r_tick = s * 0.38  # tick end radius

        # Rim thickness
        rim_w = max(3, int(s * 0.035))

        # Arc bbox derived from r_outer (this is the "use it as above" part)
        x0, y0 = cx - r_outer, cy - r_outer
        x1, y1 = cx + r_outer, cy + r_outer

        # Use the same angles you’re mapping the needle through (clean + consistent)
        arc_start = self.start_deg
        arc_extent = self.end_deg - self.start_deg  # likely negative; Tk needs positive extent
        # Tk’s arc uses "extent" direction; normalize to a positive sweep
        if arc_extent < 0:
            arc_start = self.end_deg
            arc_extent = -arc_extent

        # Outer rim arc
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

        # Inner rim arc (slightly thinner) to “tighten” the face
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
            width=max(2, rim_w - 2),
            outline="black",
        )

        # Ticks: fewer + bolder majors, light minors (keeps it clean at 150x150)
        majors = {0, 5, 10}
        for i in range(0, 11):
            v = i / 10.0
            ang = math.radians(self._map_value_to_deg(v * 100))
            is_major = i in majors

            tick_len = s * (0.075 if is_major else 0.04)
            tick_w = 3 if is_major else 2

            x1t = cx + (r_tick - tick_len) * math.cos(ang)
            y1t = cy - (r_tick - tick_len) * math.sin(ang)
            x2t = cx + r_tick * math.cos(ang)
            y2t = cy - r_tick * math.sin(ang)
            self.canvas.create_line(x1t, y1t, x2t, y2t, width=tick_w, fill="black")

        # E / F closer to ends, slightly lower
        ef_font = ("TkDefaultFont", max(10, int(s * 0.10)), "bold")
        self.canvas.create_text(s * 0.18, s * 0.68, text="E", font=ef_font, fill="black")
        self.canvas.create_text(s * 0.82, s * 0.68, text="F", font=ef_font, fill="black")

        # Label (mixed case) — bolder and tucked in like your icon
        label_font = ("TkDefaultFont", max(12, int(s * 0.12)), "bold")
        self.canvas.create_text(cx, s * 0.91, text=self.label, font=label_font, fill="black")

    def set_value(self, value_0_100: int):
        self.value = int(max(0, min(100, value_0_100)))

        s = self.size
        cx, cy = s / 2, s * 0.64

        # Needle length + hub size tuned for 150x150 icon look
        r_needle = s * 0.33
        hub_r = max(5, int(s * 0.04))

        ang = math.radians(self._map_value_to_deg(self.value))
        x = cx + r_needle * math.cos(ang)
        y = cy - r_needle * math.sin(ang)

        # Remove previous needle + hub
        if self._needle_id is not None:
            self.canvas.delete(self._needle_id)
        if self._hub_id is not None:
            self.canvas.delete(self._hub_id)

        # Draw needle
        self._needle_id = self.canvas.create_line(cx, cy, x, y, width=5, fill="black")

        # Draw hub
        self._hub_id = self.canvas.create_oval(
            cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r, fill="black", outline="black"
        )
