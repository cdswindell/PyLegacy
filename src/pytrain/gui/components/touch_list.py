#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
#
#
import tkinter as tk
from tkinter import ttk

from pytrain.gui.components.scroll_input import precise_scroll_deltas, wheel_scroll_pixels


class TouchList(tk.Frame):
    """
    Touch-friendly scrollable list:
      - scroll by finger drag (no visible scrollbar)
      - big row buttons with optional subtitle
      - calls on_select(item) when tapped
    """

    def __init__(self, parent, *, row_height=56, padding=8, on_select=None):
        super().__init__(parent)
        self.row_height = row_height
        self.padding = padding
        self.on_select = on_select or (lambda item: None)

        self.canvas = tk.Canvas(self, highlightthickness=0, yscrollincrement=1)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        # Keep scroll region updated
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Touch/mouse drag scrolling (no scrollbar widget)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)

        # Bind locally, including row surfaces: scrolling one list must not move another.
        for widget in (self, self.canvas, self.inner):
            self._bind_scrolling(widget)

        self._drag_start_y = 0
        self._scroll_start = 0
        self._items = []

    def set_items(self, items):
        """items: list of dicts or strings. dict can include: title, subtitle, payload"""
        for child in self.inner.winfo_children():
            child.destroy()

        self._items = items
        for idx, item in enumerate(items):
            if isinstance(item, str):
                title, subtitle, payload = item, "", item
            else:
                title = item.get("title", "")
                subtitle = item.get("subtitle", "")
                payload = item.get("payload", item)

            row = tk.Frame(self.inner, height=self.row_height)
            row.pack(fill="x", padx=self.padding, pady=(0, self.padding))
            row.pack_propagate(False)

            # Big button-like surface
            btn = tk.Label(
                row,
                text=title,
                anchor="w",
                justify="left",
                padx=14,
                pady=10,
                font=("Helvetica", 16),
                relief="raised",
                bd=1,
            )
            btn.pack(fill="both", expand=True)

            if subtitle:
                # Put subtitle in same label via newline (keeps the whole row tappable)
                btn.config(text=f"{title}\n{subtitle}", font=("Helvetica", 14))

            btn.bind("<Button-1>", lambda e, p=payload: self.on_select(p))

            # Optional separator line after each row (subtle, touch-friendly)
            sep = ttk.Separator(self.inner, orient="horizontal")
            sep.pack(fill="x", padx=self.padding, pady=(0, self.padding))
            for widget in (row, btn, sep):
                self._bind_scrolling(widget)

    def _bind_scrolling(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", lambda e: self._wheel_linux(-1), add="+")
        widget.bind("<Button-5>", lambda e: self._wheel_linux(1), add="+")
        try:
            widget.bind("<TouchpadScroll>", self._on_touchpad_scroll, add="+")
        except tk.TclError:
            # Tk 8.6 uses MouseWheel for touch-surface input instead.
            pass

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # Make inner frame width track canvas width
        self.canvas.itemconfigure(self.inner_id, width=event.width)

    def _on_press(self, event):
        self._drag_start_y = event.y
        self._scroll_start = self.canvas.canvasy(0)

    def _on_drag(self, event):
        dy = event.y - self._drag_start_y
        target = self._scroll_start - dy
        self._scroll_to_pixel(target)

    def _scroll_to_pixel(self, y):
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        _, top, _, bottom = bbox
        total = bottom - top
        if total <= 0:
            return

        # Clamp y
        view_h = self.canvas.winfo_height()
        y = max(0, min(y, max(0, total - view_h)))

        self.canvas.yview_moveto(y / total)

    def _on_mousewheel(self, event):
        self._scroll_to_pixel(self.canvas.canvasy(0) + wheel_scroll_pixels(event))
        return "break"

    def _on_touchpad_scroll(self, event):
        _, dy = precise_scroll_deltas(event)
        if dy:
            self._scroll_to_pixel(self.canvas.canvasy(0) - dy)
        return "break"

    def _wheel_linux(self, direction):
        self._scroll_to_pixel(self.canvas.canvasy(0) + direction * 48)
        return "break"


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("420x600")
    root.title("TouchList demo (no arrows)")

    def picked(item):
        print("Selected:", item)

    lst = TouchList(root, on_select=picked)
    lst.pack(fill="both", expand=True)

    demo = []
    for i in range(1, 51):
        demo.append(
            {
                "title": f"Engine {i:03d}",
                "subtitle": "Tap to open / press to select",
                "payload": {"type": "engine", "id": i},
            }
        )

    lst.set_items(demo)
    root.mainloop()
