#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#
#
"""Offline macOS Tk 9 touch-surface checks; never connects to layout hardware."""

import sys
import tkinter as tk
from pathlib import Path

from guizero import App, Box, Text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pytrain.gui.components.scroll_box import ScrollBox
from pytrain.gui.components.swipe_detector import SwipeDetector
from pytrain.gui.components.touch_list import TouchList
from pytrain.gui.components.touch_list_box import TouchListBox


def gesture(app, widget, dx=0, dy=0):
    widget.event_generate("<TouchpadScroll>", delta=(dx << 16) | (dy & 0xFFFF))
    app.tk.update()


def main():
    app = App(title="Offline scroll checks", width=800, height=800)
    try:
        assert app.tk.tk.call("tk", "windowingsystem") == "aqua", "Requires macOS Aqua Tk"
        assert tk.TkVersion >= 9, "Requires Tk 9 for generated TouchpadScroll events"
        calls = []
        lists = Box(app, width="fill", height=260)
        lists.tk.pack_propagate(False)
        touch = TouchList(lists.tk, on_select=lambda item: calls.append(item))
        touch.pack(side="left", fill="both", expand=True)
        touch.set_items([f"Item {i}" for i in range(50)])
        other = TouchList(lists.tk)
        other.pack(side="left", fill="both", expand=True)
        other.set_items([f"Other {i}" for i in range(50)])
        lb = TouchListBox(app, items=[f"Entry {i}" for i in range(50)], width=40, height=5)
        window = ScrollBox(app, width=700)
        rows = [Text(window.content, text=f"Page row {i}") for i in range(30)]
        image = Text(app, text="Swipe navigation")
        swipe = SwipeDetector(image)
        swipe.on_swipe_left = lambda: calls.append("LEFT")
        swipe.on_swipe_right = lambda: calls.append("RIGHT")
        swipe.on_long_press = lambda: calls.append("HOLD")
        app.tk.update()
        window.fit(180)
        window.bind_scrolling()
        app.tk.update()

        label = touch.inner.winfo_children()[0].winfo_children()[0]
        gesture(app, label, dy=-1)
        assert round(touch.canvas.canvasy(0)) == 1
        gesture(app, label, dy=-7)
        assert round(touch.canvas.canvasy(0)) == 8
        gesture(app, label, dx=-100)
        assert round(touch.canvas.canvasy(0)) == 8
        assert round(other.canvas.canvasy(0)) == 0
        assert calls == []

        lb._lb.selection_set(2)
        before = lb._lb.curselection()
        row_px = lb._lb.bbox(0)[3]
        for _ in range(row_px - 1):
            gesture(app, lb._lb, dy=-1)
        assert lb._lb.yview()[0] == 0
        gesture(app, lb._lb, dy=-1)
        assert round(lb._lb.yview()[0] * 50) == 1
        assert lb._lb.curselection() == before
        assert calls == []

        gesture(app, rows[0].tk, dy=-7)
        assert window.offset == 7
        gesture(app, rows[0].tk, dy=2)
        assert window.offset == 5
        gesture(app, image.tk, dx=-50)
        gesture(app, image.tk, dx=-100)
        assert calls == ["LEFT"]
        gesture(app, image.tk, dx=50)
        assert calls == ["LEFT", "RIGHT"]

        # Destroying a list must not leave global wheel handlers behind.
        touch.destroy()
        gesture(app, other.canvas, dy=-1)
        assert round(other.canvas.canvasy(0)) == 1
        print("Real macOS touch-surface events passed: TouchList, TouchListBox, ScrollBox, SwipeDetector")
    finally:
        app.destroy()


if __name__ == "__main__":
    main()
