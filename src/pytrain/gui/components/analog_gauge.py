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

from guizero import Box


class AnalogGaugeWidget(Box):
    """
    A guizero widget (Box) containing a Tk Canvas analog gauge.

    Usage:
        g = AnalogGaugeWidget(parent, label="Fuel", size=150, on_click=...)
        g.set_value(73)
    """

    def __init__(
        self,
        master,
        label: str,
        size: int = 150,
        on_click=None,  # callable(int)->None
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
        self._on_click = on_click
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
        )
        self.canvas.pack(fill="both", expand=True)

        self._needle_id = None
        self._hub_id = None

        self._draw_static()
        self.set_value(0)

        # Click-to-speak
        self.canvas.bind("<Button-1>", self._handle_click)

    def set_on_click(self, callback):
        self._on_click = callback

    def _handle_click(self, _event):
        if callable(self._on_click):
            self._on_click(self.value)

    def _map_value_to_deg(self, value_0_100: float) -> float:
        v = max(0.0, min(100.0, float(value_0_100)))
        t = v / 100.0
        return self.start_deg + t * (self.end_deg - self.start_deg)

    def _draw_static(self):
        s = self.size
        cx, cy = s / 2, s * 0.64

        r_outer = s * 0.46  # USED
        r_inner = s * 0.40
        r_tick = s * 0.38

        rim_w = max(3, int(s * 0.035))

        # Arc bbox derived from r_outer
        x0, y0 = cx - r_outer, cy - r_outer
        x1, y1 = cx + r_outer, cy + r_outer

        # Normalize arc sweep for Tk
        arc_start = self.start_deg
        arc_extent = self.end_deg - self.start_deg
        if arc_extent < 0:
            arc_start = self.end_deg
            arc_extent = -arc_extent

        # Outer + inner rim arcs (tight icon look)
        self.canvas.create_arc(
            x0, y0, x1, y1, start=arc_start, extent=arc_extent, style="arc", width=rim_w, outline="black"
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
            width=max(2, rim_w - 2),
            outline="black",
        )

        # Ticks (clean at 150x150)
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

        # E/F + label (mixed case)
        ef_font = ("TkDefaultFont", max(10, int(s * 0.10)), "bold")
        self.canvas.create_text(s * 0.18, s * 0.68, text="E", font=ef_font, fill="black")
        self.canvas.create_text(s * 0.82, s * 0.68, text="F", font=ef_font, fill="black")

        label_font = ("TkDefaultFont", max(12, int(s * 0.12)), "bold")
        self.canvas.create_text(cx, s * 0.91, text=self.label, font=label_font, fill="black")

    def set_value(self, value_0_100: int):
        self.value = int(max(0, min(100, value_0_100)))

        s = self.size
        cx, cy = s / 2, s * 0.64

        r_needle = s * 0.33
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
            cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r, fill="black", outline="black"
        )
