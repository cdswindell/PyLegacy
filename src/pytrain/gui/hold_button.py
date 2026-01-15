#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

import time
import tkinter as tk
from threading import Condition, RLock
from tkinter import TclError
from typing import Any, Callable

from guizero import PushButton


# noinspection PyUnusedLocal
class HoldButton(PushButton):
    """
    A PushButton subclass that adds:
      - on_press → single short tap, or fired when held if no hold/repeat defined
      - on_hold → single fire after hold_threshold seconds
      - on_repeat → continuous fire while held

    Each callback can be:
        func
        or (func, args)
        or (func, args, kwargs)

    Optional: full-height left-to-right progress fill BEHIND TEXT while holding.
      - Implemented via a Canvas overlay (does NOT modify button image), so it does not affect geometry.
      - Works with text buttons and image buttons (your images= setter) without compositing.
    """

    def __init__(
        self,
        master,
        text: str = "",
        on_press=None,
        on_hold=None,
        on_repeat=None,
        hold_threshold: float = 1.0,
        repeat_interval: float = 0.2,
        debounce_ms: int = 80,
        bg: str = "white",
        text_color: str = "black",
        text_size: int | None = None,
        text_bold: bool | None = None,
        flash: bool = True,
        command: Callable | None = None,
        args: list[Any] | None = None,
        # ── Progress options ──
        show_hold_progress: bool = False,
        progress_update_ms: int = 40,
        progress_fill_color: str = "darkgrey",
        progress_empty_color: str | None = None,  # None => transparent/no background
        progress_keep_full_until_release: bool = True,
        cancel_on_leave: bool = False,
        **kwargs,
    ):
        self._cv = Condition(RLock())

        # base properties
        self._normal_bg: str | None = None
        self._normal_fg: str | None = None
        self._normal_img = None
        self._inverted_img = None

        super().__init__(master, text=text, **kwargs)

        # basic button properties
        if bg:
            self._normal_bg = self.bg = bg
        if text_color:
            self._normal_fg = self.text_color = text_color
        if text_size is not None:
            self.text_size = text_size
        if text_bold is not None:
            self.text_bold = text_bold

        if command and on_press:
            raise ValueError("Cannot specify both command and on_press")
        elif command:
            on_press = (command, args) if args else command

        # callback configuration
        self._on_press = on_press
        self._on_hold = on_hold
        self._on_repeat = on_repeat

        # timing and state tracking
        self.hold_threshold = float(hold_threshold)
        self.repeat_interval = float(repeat_interval)
        self.debounce_ms = int(debounce_ms)

        self._press_time: float | None = None
        self._pressed: bool = False
        self._held: bool = False
        self._repeating: bool = False
        self._after_id: str | None = None
        self._handled_hold: bool = False
        self._handled_flash: bool = False

        # progress config/state
        self._show_hold_progress = bool(show_hold_progress)
        self._progress_update_ms = int(progress_update_ms)
        self._progress_fill_color = str(progress_fill_color)
        self._progress_empty_color = progress_empty_color
        self._progress_keep_full_until_release = bool(progress_keep_full_until_release)

        self._progress_start: float | None = None
        self._progress_after_id: str | None = None

        # Canvas overlay used for progress (does not change button geometry)
        self._progress_canvas: tk.Canvas | None = None
        self._progress_rect = None
        self._progress_bg_rect = None
        self._overlay_visible = False

        # bind events
        self.when_left_button_pressed = self._on_press_event
        self.when_left_button_released = self._on_release_event
        if cancel_on_leave:
            self.tk.bind("<Leave>", self._on_leave_event, add="+")

        # keep overlay positioned when button moves/resizes
        self.tk.bind("<Configure>", self._on_configure_event, add="+")

        # flash button on press, if requested
        self._flash_requested = flash
        if flash and text:
            self.do_flash()

    # ───────────────────────────────
    # Parent setter overrides
    # ───────────────────────────────
    @PushButton.text.setter
    def text(self, value):
        with self._cv:
            PushButton.text.fset(self, value)
            if self._flash_requested and value:
                self.do_flash()

    @PushButton.text_color.setter
    def text_color(self, value):
        with self._cv:
            PushButton.text_color.fset(self, value)
            self._normal_fg = value

    @PushButton.bg.setter
    def bg(self, value):
        with self._cv:
            PushButton.bg.fset(self, value)
            self._normal_bg = value

    # ───────────────────────────────
    # Properties for dynamic callbacks
    # ───────────────────────────────
    @property
    def images(self) -> tuple:
        return self._normal_img, self._inverted_img

    @images.setter
    def images(self, value: tuple) -> None:
        self._normal_img, self._inverted_img = value
        self.tk.config(image=self._normal_img, compound="center")
        if self._flash_requested and self._normal_img and self._inverted_img:
            self.do_flash()

    @property
    def on_press(self):
        return self._on_press

    @on_press.setter
    def on_press(self, func):
        self._on_press = func

    @property
    def on_hold(self):
        return self._on_hold

    @on_hold.setter
    def on_hold(self, func):
        self._on_hold = func

    @property
    def on_repeat(self):
        return self._on_repeat

    @on_repeat.setter
    def on_repeat(self, func):
        self._on_repeat = func

    # ───────────────────────────────
    # Internal event handlers
    # ───────────────────────────────
    def _on_press_event(self, event=None):
        self._pressed = True
        self._press_time = time.monotonic()
        self._held = False
        self._repeating = False
        self._handled_hold = False

        self._start_progress()

        self._cancel_after()
        self._after_id = self.tk.after(int(self.hold_threshold * 1000), self._trigger_hold_or_repeat)

    def _on_release_event(self, event=None):
        self._pressed = False

        self._stop_progress()
        self._cancel_after()

        elapsed = (time.monotonic() - self._press_time) if self._press_time else 0.0
        if elapsed < (self.debounce_ms / 1000.0):
            return

        if self._repeating:
            self._repeating = False
            return

        if not self._held:
            self._invoke_callback(self._on_press)
            return

        if self._held and not self._handled_hold:
            self._invoke_callback(self._on_press)

    def _on_leave_event(self, event=None):
        self._pressed = False
        self._repeating = False
        self._stop_progress()
        self._cancel_after()

    def _on_configure_event(self, event=None):
        # keep overlay aligned to the button
        if self._overlay_visible:
            self._position_overlay()

    def _trigger_hold_or_repeat(self):
        self._held = True
        handled = False

        if self._on_repeat:
            self._repeating = True
            if self._progress_keep_full_until_release:
                self._set_progress_full()
            else:
                self._stop_progress()
            self._repeat_fire()
            handled = True

        elif self._on_hold:
            if self._progress_keep_full_until_release:
                self._set_progress_full()
            else:
                self._stop_progress()
            self._invoke_callback(self._on_hold)
            handled = True
            self.restore_color_state()

        elif self._on_press and not self._on_hold and not self._on_repeat:
            if self._progress_keep_full_until_release:
                self._set_progress_full()
            else:
                self._stop_progress()
            self._invoke_callback(self._on_press)
            handled = True
            self.restore_color_state()

        self._handled_hold = handled

    def _repeat_fire(self):
        if not self._repeating:
            return
        self._invoke_callback(self._on_repeat)
        self._after_id = self.tk.after(int(self.repeat_interval * 1000), self._repeat_fire)

    # ───────────────────────────────
    # Helper: invoke callback flexibly
    # ───────────────────────────────
    @staticmethod
    def _invoke_callback(cb):
        if not cb:
            return
        if callable(cb):
            cb()
        elif isinstance(cb, (tuple, list)) and len(cb) > 0:
            func = cb[0]
            args = cb[1] if len(cb) > 1 else []
            kwargs = cb[2] if len(cb) > 2 else {}
            func(*args, **kwargs)

    # ───────────────────────────────
    # Flash button on press
    # ───────────────────────────────
    def do_flash(self) -> None:
        if self._handled_flash:
            return
        self._handled_flash = True

        pressed_bg = "darkgrey"
        pressed_fg = "white"

        def on_press(_event):
            with self._cv:
                normal_bg = self.bg
                normal_fg = self.text_color
                if self.text:
                    self.bg = pressed_bg
                    self.text_color = pressed_fg
                    self._normal_bg = normal_bg
                    self._normal_fg = normal_fg
                if self._inverted_img:
                    self.tk.config(image=self._inverted_img, compound="center")

        def on_release(_event):
            self.restore_color_state()

        self.tk.bind("<ButtonPress-1>", on_press, add="+")
        self.tk.bind("<ButtonRelease-1>", on_release, add="+")

    def restore_color_state(self):
        with self._cv:
            if self.text:
                self.bg = self._normal_bg
                self.text_color = self._normal_fg
            if self._normal_img and self.tk.cget("image") != self._normal_img:
                self.tk.config(image=self._normal_img, compound="center")

    # ───────────────────────────────
    # Progress overlay (Canvas) — does not affect geometry
    # ───────────────────────────────
    def _progress_fraction(self) -> float:
        if not self._progress_start or self.hold_threshold <= 0:
            return 0.0
        return max(0.0, min(1.0, (time.monotonic() - self._progress_start) / self.hold_threshold))

    def _ensure_overlay(self) -> None:
        if self._progress_canvas is not None:
            return

        parent = self.tk.master  # same container as the button

        # Canvas requires a valid color string; empty "" breaks on some Tk builds.
        # Use the configured empty color, or fall back to the button's bg.
        canvas_bg = self._progress_empty_color or self._normal_bg or self.bg or "white"

        self._progress_canvas = tk.Canvas(
            parent,
            highlightthickness=0,
            bd=0,
            background=canvas_bg,
        )

        # Background rect (optional)
        self._progress_bg_rect = self._progress_canvas.create_rectangle(
            0,
            0,
            0,
            0,
            outline="",
            fill=canvas_bg,
        )

        # Fill rect
        self._progress_rect = self._progress_canvas.create_rectangle(
            0,
            0,
            0,
            0,
            outline="",
            fill=self._progress_fill_color,
        )

        self._progress_canvas.place_forget()

    def _position_overlay(self) -> None:
        if not self._progress_canvas:
            return

        # Canvas lives in THIS parent:
        canvas_parent = self._progress_canvas.master

        try:
            # Button position in screen/root coordinates
            bx = int(self.tk.winfo_rootx())
            by = int(self.tk.winfo_rooty())
            bw = max(1, int(self.tk.winfo_width()))
            bh = max(1, int(self.tk.winfo_height()))

            # Parent position in screen/root coordinates
            px = int(canvas_parent.winfo_rootx())
            py = int(canvas_parent.winfo_rooty())
        except TclError:
            return

        # Convert to canvas-parent coordinate system
        x = bx - px
        y = by - py

        self._progress_canvas.place(x=x, y=y, width=bw, height=bh)

        canvas_bg = self._progress_empty_color or self._normal_bg or self.bg or "white"
        self._progress_canvas.config(background=canvas_bg)
        self._progress_canvas.itemconfig(self._progress_bg_rect, fill=canvas_bg)
        self._progress_canvas.coords(self._progress_bg_rect, 0, 0, bw, bh)

        frac = self._progress_fraction() if self._pressed else 0.0
        fill_w = int(bw * frac)
        self._progress_canvas.coords(self._progress_rect, 0, 0, fill_w, bh)

        # Ensure the button stays above the overlay
        self.tk.tkraise()

    def _set_overlay_fraction(self, frac: float) -> None:
        if not self._progress_canvas:
            return
        w = max(1, int(self._progress_canvas.winfo_width()))
        h = max(1, int(self._progress_canvas.winfo_height()))
        fill_w = int(w * max(0.0, min(1.0, frac)))
        self._progress_canvas.coords(self._progress_rect, 0, 0, fill_w, h)

    def _schedule_progress_tick(self) -> None:
        self._progress_after_id = self.tk.after(self._progress_update_ms, self._progress_tick)

    def _progress_tick(self) -> None:
        if not self._pressed or not self._progress_start:
            return
        self._set_overlay_fraction(self._progress_fraction())
        if self._progress_fraction() < 1.0:
            self._schedule_progress_tick()

    def _start_progress(self) -> None:
        if not self._show_hold_progress or self.hold_threshold <= 0:
            return

        self._progress_start = time.monotonic()
        self._cancel_progress_after()

        self._ensure_overlay()
        self._overlay_visible = True
        self._position_overlay()
        self._set_overlay_fraction(0.0)
        self._schedule_progress_tick()

    def _set_progress_full(self) -> None:
        if not self._overlay_visible:
            return
        self._set_overlay_fraction(1.0)

    def _stop_progress(self) -> None:
        self._cancel_progress_after()
        self._progress_start = None

        if self._progress_canvas:
            self._progress_canvas.place_forget()
        self._overlay_visible = False

    # ───────────────────────────────
    # Timer cancellation helpers (narrow exceptions)
    # ───────────────────────────────
    def _cancel_after(self) -> None:
        after_id = self._after_id
        if not after_id:
            return
        self._after_id = None
        try:
            self.tk.after_cancel(after_id)
        except TclError:
            pass
        except RuntimeError:
            pass

    def _cancel_progress_after(self) -> None:
        after_id = self._progress_after_id
        if not after_id:
            return
        self._progress_after_id = None
        try:
            self.tk.after_cancel(after_id)
        except TclError:
            pass
        except RuntimeError:
            pass
