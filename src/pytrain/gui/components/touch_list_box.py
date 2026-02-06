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
from __future__ import annotations

import time
from tkinter import TclError
from typing import Any, Callable, Optional

from guizero import ListBox


class TouchListBox(ListBox):
    """
    GuiZero ListBox with touch-friendly behavior:
      - Drag (finger move) scrolls the list (no arrows required)
      - Long-press selects/activates (hold-to-select)
      - Optional tap-to-highlight (no activation)

    IMPORTANT (GuiZero implementation detail):
      GuiZero's ListBox is a composite widget. `self.tk` is typically a Tk Frame wrapper,
      and the actual Tk Listbox is usually `self.children[0].tk`.
      We MUST bind and call yview/nearest/size/etc. on the real Tk Listbox.
    """

    def __init__(
        self,
        master,
        items=None,
        selected=None,
        *,
        hold_ms: int = 500,
        move_px: int = 35,
        tap_highlight: bool = False,
        on_hold_select: Optional[Callable[[int, str], None]] = None,
        debug: bool = False,
        **kwargs,
    ):
        super().__init__(master, items=items, selected=selected, **kwargs)

        self.hold_ms = int(hold_ms)
        self.move_px = int(move_px)
        self.tap_highlight = bool(tap_highlight)
        self.on_hold_select = on_hold_select or (lambda idx, text: None)
        self.debug = bool(debug)

        # Internal gesture state
        self._press_y: int = 0
        self._press_time: float = 0.0
        self._moved: bool = False
        self._after_id: Optional[str] = None
        self._candidate_index: Optional[int] = None
        self._start_yview: float = 0.0
        self._hold_fired: bool = False

        # Resolve the inner Tk Listbox (the widget that actually receives events)
        self._lb = self._resolve_inner_listbox()
        if self._lb is None:
            # Fail loudly: if GuiZero changes internals, we want to know immediately.
            raise RuntimeError(
                "TouchListBox: could not resolve inner Tk Listbox. "
                "GuiZero ListBox appears not to have a children[0].tk listbox."
            )

        # Keep selection when focus changes (touch-friendly)
        try:
            self._lb.config(exportselection=False)
        except TclError:
            # Can happen during teardown or if not fully realized.
            pass

        self._dbg(
            f"init: hold_ms={self.hold_ms} move_px={self.move_px} tap_highlight={self.tap_highlight} lb={self._lb}"
        )

        self._bind_touch_handlers()

    # ---------- Public API ----------

    def set_on_hold_select(self, callback: Callable[[int, str], None]) -> None:
        self.on_hold_select = callback

    def set_hold_threshold(self, hold_ms: int) -> None:
        self.hold_ms = int(hold_ms)

    def set_move_threshold(self, move_px: int) -> None:
        self.move_px = int(move_px)

    # ---------- Internal helpers ----------

    def _dbg(self, msg: str) -> None:
        if self.debug:
            print(f"[TouchListBox] {msg}", flush=True)

    def _resolve_inner_listbox(self):
        """
        Return the Tk listbox widget inside the GuiZero ListBox composite.
        Narrow exceptions only; no blanket Exception.
        """
        try:
            child0 = self.children[0]
        except (AttributeError, IndexError, KeyError, TypeError):
            return None

        try:
            tk_widget = child0.tk
        except AttributeError:
            return None

        # We could optionally verify class == "Listbox", but don't hard-require it.
        # This keeps us tolerant of Tk variants.
        return tk_widget

    def _bind_touch_handlers(self) -> None:
        """
        Bind to the inner Tk listbox widget (not the wrapper frame).
        Use add="+" so we don't clobber existing bindings.
        """
        try:
            self._lb.bind("<ButtonPress-1>", self._on_press, add="+")
            self._lb.bind("<B1-Motion>", self._on_motion, add="+")
            self._lb.bind("<ButtonRelease-1>", self._on_release, add="+")
        except TclError:
            # Widget may be destroying
            pass

    def _cancel_hold_timer(self) -> None:
        if self._after_id is None:
            return
        try:
            self._lb.after_cancel(self._after_id)
        except TclError:
            # after id may be invalid, or widget may be destroying
            pass
        finally:
            self._after_id = None

    def _schedule_hold_timer(self) -> None:
        self._cancel_hold_timer()
        try:
            self._after_id = self._lb.after(self.hold_ms, self._fire_hold_select)
        except TclError:
            self._after_id = None
            return
        self._dbg(f"schedule: hold_ms={self.hold_ms} idx={self._candidate_index}")

    def _tk_size(self) -> int:
        try:
            return int(self._lb.size())
        except (TclError, TypeError, ValueError):
            return 0

    # ---------- Gesture actions ----------

    def _fire_hold_select(self) -> None:
        """
        Timer callback for long-press selection.
        """
        self._after_id = None
        self._dbg(f"hold_fire: moved={self._moved} idx={self._candidate_index} size={self._tk_size()}")

        # Only fire if user hasn't scrolled
        if self._moved:
            return

        idx = self._candidate_index
        if idx is None:
            return

        size = self._tk_size()
        if not (0 <= idx < size):
            return

        try:
            self._lb.selection_clear(0, "end")
            self._lb.selection_set(idx)
            self._lb.activate(idx)
            text = self._lb.get(idx)
        except TclError:
            return

        self._hold_fired = True
        self._dbg(f"on_hold_select: idx={idx} text={text!r}")
        self.on_hold_select(idx, text)

    # ---------- Tk event handlers ----------

    def _on_press(self, event: Any) -> None:
        self._press_y = int(event.y)
        self._press_time = time.monotonic()
        self._moved = False
        self._hold_fired = False

        size = self._tk_size()
        self._dbg(f"press: y={event.y} size={size}")

        try:
            self._start_yview = float(self._lb.yview()[0])
        except (TclError, TypeError, ValueError, IndexError):
            self._start_yview = 0.0

        if size <= 0:
            self._candidate_index = None
            self._cancel_hold_timer()
            return

        try:
            idx = int(self._lb.nearest(event.y))
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

        # Touch jitter is common; only treat as scroll once threshold exceeded.
        if abs(dy) >= self.move_px and not self._moved:
            self._dbg(f"motion: cancel_hold dy={dy} move_px={self.move_px}")

        if abs(dy) >= self.move_px:
            self._moved = True
            self._cancel_hold_timer()

        if not self._moved:
            return

        total = max(1, self._tk_size())

        # Tk Listbox 'height' is rows, not pixels; we just need an estimate.
        try:
            visible_rows = int(self._lb.cget("height"))
            visible_rows = max(1, visible_rows)
        except (TclError, TypeError, ValueError):
            visible_rows = 10

        try:
            widget_px_h = max(1, int(self._lb.winfo_height()))
        except (TclError, TypeError, ValueError):
            widget_px_h = 1

        # Convert pixel drag into yview fraction movement
        frac_per_row = 1.0 / total
        frac_per_px = (frac_per_row * visible_rows) / widget_px_h

        new_yview = self._start_yview - (dy * frac_per_px)
        new_yview = max(0.0, min(1.0, new_yview))

        try:
            self._lb.yview_moveto(new_yview)
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
            self._lb.selection_clear(0, "end")
            self._lb.selection_set(idx)
            self._lb.activate(idx)
        except TclError:
            pass
