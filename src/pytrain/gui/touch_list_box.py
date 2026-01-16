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
from __future__ import annotations

import time
from tkinter import TclError
from typing import Any, Callable, Optional

from guizero import ListBox


class TouchListBox(ListBox):
    """
    GuiZero ListBox with touch-friendly behavior:
      - Drag scrolls the list
      - Long-press selects/activates (hold-to-select)
      - Optional tap-to-highlight
    """

    def __init__(
        self,
        master,
        items=None,
        selected=None,
        *,
        hold_ms: int = 500,
        move_px: int = 35,
        tap_highlight: bool = True,
        on_hold_select: Optional[Callable[[int, str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, items=items, selected=selected, **kwargs)

        self.hold_ms = int(hold_ms)
        self.move_px = int(move_px)
        self.tap_highlight = bool(tap_highlight)
        self.on_hold_select = on_hold_select or (lambda idx, text: None)

        self._press_y: int = 0
        self._press_time: float = 0.0
        self._moved: bool = False
        self._after_id: Optional[str] = None
        self._candidate_index: Optional[int] = None
        self._start_yview: float = 0.0
        self._hold_fired: bool = False

        # Keep selection when focus changes (touch-friendly)
        try:
            self.tk.config(exportselection=False)
        except TclError:
            # Tk can throw during teardown / if widget not fully realized yet
            pass

        self._bind_touch_handlers()

    # ---------- Public API ----------

    def set_on_hold_select(self, callback: Callable[[int, str], None]) -> None:
        self.on_hold_select = callback

    def set_hold_threshold(self, hold_ms: int) -> None:
        self.hold_ms = int(hold_ms)

    def set_move_threshold(self, move_px: int) -> None:
        self.move_px = int(move_px)

    # ---------- Internal helpers ----------

    def _bind_touch_handlers(self) -> None:
        self.tk.bind("<ButtonPress-1>", self._on_press, add="+")
        self.tk.bind("<B1-Motion>", self._on_motion, add="+")
        self.tk.bind("<ButtonRelease-1>", self._on_release, add="+")

    def _cancel_hold_timer(self) -> None:
        if self._after_id is None:
            return
        try:
            self.tk.after_cancel(self._after_id)
        except TclError:
            # after id may be invalid, or widget may be destroying
            pass
        finally:
            self._after_id = None

    def _schedule_hold_timer(self) -> None:
        self._cancel_hold_timer()
        try:
            self._after_id = self.tk.after(self.hold_ms, self._fire_hold_select)
        except TclError:
            # Can fail if widget is being destroyed
            self._after_id = None

    def _tk_size(self) -> int:
        try:
            return int(self.tk.size())
        except (TclError, TypeError, ValueError):
            return 0

    def _fire_hold_select(self) -> None:
        # Timer callback: only fire if user hasn't scrolled
        self._after_id = None
        if self._moved:
            return

        idx = self._candidate_index
        if idx is None:
            return

        size = self._tk_size()
        if not (0 <= idx < size):
            return

        try:
            self.tk.selection_clear(0, "end")
            self.tk.selection_set(idx)
            self.tk.activate(idx)
            text = self.tk.get(idx)
        except TclError:
            # Widget might be gone or not in a good state
            return

        self._hold_fired = True
        self.on_hold_select(idx, text)

    # ---------- Tk event handlers ----------

    def _on_press(self, event: Any) -> None:
        self._press_y = int(event.y)
        self._press_time = time.monotonic()
        self._moved = False
        self._hold_fired = False

        try:
            self._start_yview = float(self.tk.yview()[0])
        except (TclError, TypeError, ValueError, IndexError):
            self._start_yview = 0.0

        size = self._tk_size()
        if size <= 0:
            self._candidate_index = None
            self._cancel_hold_timer()
            return

        try:
            idx = int(self.tk.nearest(event.y))
        except (TclError, TypeError, ValueError):
            self._candidate_index = None
            self._cancel_hold_timer()
            return

        if not (0 <= idx < size):
            self._candidate_index = None
            self._cancel_hold_timer()
            return

        self._candidate_index = idx
        self._schedule_hold_timer()

    def _on_motion(self, event: Any) -> None:
        dy = int(event.y) - self._press_y

        if abs(dy) >= self.move_px:
            self._moved = True
            self._cancel_hold_timer()

        if not self._moved:
            return

        total = max(1, self._tk_size())

        try:
            visible_rows = int(self.tk.cget("height"))
            visible_rows = max(1, visible_rows)
        except (TclError, TypeError, ValueError):
            visible_rows = 10

        try:
            widget_px_h = max(1, int(self.tk.winfo_height()))
        except (TclError, TypeError, ValueError):
            widget_px_h = 1

        frac_per_row = 1.0 / total
        frac_per_px = (frac_per_row * visible_rows) / widget_px_h

        new_yview = self._start_yview - (dy * frac_per_px)
        new_yview = max(0.0, min(1.0, new_yview))

        try:
            self.tk.yview_moveto(new_yview)
        except TclError:
            pass

    def _on_release(self, _event: Any) -> None:
        self._cancel_hold_timer()

        if not self.tap_highlight:
            return
        if self._moved or self._hold_fired:
            return

        idx = self._candidate_index
        if idx is None:
            return

        size = self._tk_size()
        if not (0 <= idx < size):
            return

        try:
            self.tk.selection_clear(0, "end")
            self.tk.selection_set(idx)
            self.tk.activate(idx)
        except TclError:
            pass
