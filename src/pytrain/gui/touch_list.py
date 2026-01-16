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

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = tk.Frame(self.canvas)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        # Keep scroll region updated
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Touch/mouse drag scrolling (no scrollbar widget)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)

        # Optional mouse wheel for desktop testing
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows/macOS
        self.canvas.bind_all("<Button-4>", lambda e: self._wheel_linux(-1))  # Linux up
        self.canvas.bind_all("<Button-5>", lambda e: self._wheel_linux(1))  # Linux down

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
        # event.delta: Windows=120 increments; macOS often smaller
        self.canvas.yview_scroll(int(-event.delta / 60), "units")

    def _wheel_linux(self, direction):
        self.canvas.yview_scroll(direction, "units")


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
