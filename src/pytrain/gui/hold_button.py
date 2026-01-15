from __future__ import annotations

import time
import tkinter as tk
from threading import Condition, RLock
from typing import Any, Callable

from guizero import PushButton


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
      - Works best for text buttons.
      - If you set images=(normal,inverted), this class will *not* attempt to composite progress with your image.
        (It will simply skip the full-height progress image so your normal images remain intact.)
    """

    def __init__(
        self,
        master,
        text="",
        on_press=None,
        on_hold=None,
        on_repeat=None,
        hold_threshold=1.0,
        repeat_interval=0.2,
        debounce_ms=80,
        bg: str = "white",
        text_color: str = "black",
        text_size: int | None = None,
        text_bold: bool | None = None,
        flash: bool = True,
        command: Callable | None = None,
        args: list[Any] | None = None,
        # ── Progress fill options ──
        show_hold_progress: bool = False,
        progress_update_ms: int = 40,
        progress_fill_color: str = "darkgrey",
        progress_empty_color: str | None = None,  # None => uses current bg
        progress_keep_full_until_release: bool = True,
        cancel_on_leave: bool = False,
        **kwargs,
    ):
        # semaphore to protect critical code
        self._cv = Condition(RLock())

        # base properties, new to HoldButton
        self._normal_bg: str | None = None
        self._normal_fg: str | None = None
        self._normal_img = None
        self._inverted_img = None

        # now initialize the parent class
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
            if args:
                on_press = (command, args)
            else:
                on_press = command

        # callback configuration
        self._on_press = on_press
        self._on_hold = on_hold
        self._on_repeat = on_repeat

        # timing and state tracking
        self.hold_threshold = float(hold_threshold)
        self.repeat_interval = float(repeat_interval)
        self.debounce_ms = int(debounce_ms)

        self._press_time: float | None = None
        self._pressed = False
        self._held = False
        self._repeating = False
        self._after_id: str | None = None
        self._handled_hold = False
        self._handled_flash = False

        # bind events (mouse and touchscreen compatible)
        self.when_left_button_pressed = self._on_press_event
        self.when_left_button_released = self._on_release_event

        if cancel_on_leave:
            self.tk.bind("<Leave>", self._on_leave_event, add="+")

        # flash button on press, if requested
        self._flash_requested = flash
        if flash and text:
            self.do_flash()

        # ── Progress state ──
        self._show_hold_progress = bool(show_hold_progress)
        self._progress_update_ms = int(progress_update_ms)
        self._progress_fill_color = str(progress_fill_color)
        self._progress_empty_color = progress_empty_color
        self._progress_keep_full_until_release = bool(progress_keep_full_until_release)

        self._progress_start: float | None = None
        self._progress_after_id: str | None = None
        self._progress_img: tk.PhotoImage | None = None
        self._progress_using_image = False

        # keep progress image sized correctly while pressed
        self.tk.bind("<Configure>", self._on_configure_event, add="+")

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
        # Restore normal image as the canonical image state
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
    # noinspection PyUnusedLocal
    def _on_press_event(self, event=None):
        self._pressed = True
        self._press_time = time.monotonic()
        self._held = False
        self._repeating = False
        self._handled_hold = False

        # start full-height progress fill
        self._start_progress()

        # schedule hold trigger
        self._cancel_after()
        self._after_id = self.tk.after(int(self.hold_threshold * 1000), self._trigger_hold_or_repeat)

    # noinspection PyUnusedLocal
    def _on_release_event(self, event=None):
        self._pressed = False

        # cancel progress and timers
        self._stop_progress()
        self._cancel_after()

        elapsed = (time.monotonic() - self._press_time) if self._press_time else 0.0
        if elapsed < (self.debounce_ms / 1000.0):
            return

        # stop repeating
        if self._repeating:
            self._repeating = False
            return

        # Case 1: standard short press
        if not self._held:
            self._invoke_callback(self._on_press)
            return

        # Case 2: held long enough, but no hold/repeat defined
        # (we already fired on_press during hold trigger)
        if self._held and not self._handled_hold:
            self._invoke_callback(self._on_press)

    # noinspection PyUnusedLocal
    def _on_leave_event(self, event=None):
        # Treat leaving the button as a cancel (common on touch drags)
        self._pressed = False
        self._repeating = False
        self._stop_progress()
        self._cancel_after()

    # noinspection PyUnusedLocal
    def _on_configure_event(self, event=None):
        # If the widget is resizing while we're drawing progress, rebuild at the new size
        if self._pressed and self._progress_using_image:
            self._ensure_progress_image()
            self._update_progress_image(self._progress_fraction())

    def _trigger_hold_or_repeat(self):
        self._held = True
        handled = False

        if self._on_repeat:
            self._repeating = True
            # For repeat mode, leaving the bar full until release is usually nice feedback.
            if not self._progress_keep_full_until_release:
                self._stop_progress()
            else:
                self._set_progress_full()
            self._repeat_fire()
            handled = True

        elif self._on_hold:
            # Single hold fire
            if self._progress_keep_full_until_release:
                self._set_progress_full()
            else:
                self._stop_progress()

            self._invoke_callback(self._on_hold)
            handled = True
            self.restore_color_state()

        elif self._on_press and not self._on_hold and not self._on_repeat:
            # fire on_press here if no dedicated hold/repeat
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
        """Invoke callback allowing func, (func,args), or (func,args,kwargs)."""
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
    # Helper: Flash button when pressed
    # ───────────────────────────────
    def do_flash(self) -> None:
        if self._handled_flash:
            return
        self._handled_flash = True

        # pressed colors
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

        # bind both events
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
    # Progress fill (full height, left→right, behind text)
    # ───────────────────────────────
    def _progress_fraction(self) -> float:
        if not self._progress_start or self.hold_threshold <= 0:
            return 0.0
        elapsed = time.monotonic() - self._progress_start
        return max(0.0, min(1.0, elapsed / self.hold_threshold))

    def _ensure_progress_image(self) -> None:
        """
        Create a full-size PhotoImage and install it as the button image.
        We only do this if you are NOT using custom images=(normal,inverted).
        """
        if self._normal_img or self._inverted_img:
            self._progress_using_image = False
            return

        w = max(1, int(self.tk.winfo_width()))
        h = max(1, int(self.tk.winfo_height()))

        # Recreate at current size. Keep a reference on self to prevent GC.
        self._progress_img = tk.PhotoImage(width=w, height=h)

        # Install image so text is drawn on top
        self.tk.config(image=self._progress_img, compound="center")
        self._progress_using_image = True

    def _update_progress_image(self, frac: float) -> None:
        """
        Type-checker-friendly progress rendering.

        Draws a full-height background, then a left→right fill behind the text.
        Uses only PhotoImage.put(color, to=(x, y)) which matches conservative stubs.
        """
        if not self._progress_using_image or not self._progress_img:
            return

        w = int(self._progress_img.width())
        h = int(self._progress_img.height())

        empty = self._progress_empty_color or self._normal_bg or self.bg
        fill = self._progress_fill_color

        fill_w = int(w * max(0.0, min(1.0, frac)))
        if fill_w <= 0:
            # All empty
            for y in range(h):
                for x in range(w):
                    self._progress_img.put(empty, to=(x, y))
            return

        if fill_w >= w:
            # All filled
            for y in range(h):
                for x in range(w):
                    self._progress_img.put(fill, to=(x, y))
            return

        # Mixed: fill left part, empty right part
        for y in range(h):
            # Filled region (0 .. fill_w-1)
            for x in range(fill_w):
                self._progress_img.put(fill, to=(x, y))
            # Empty region (fill_w .. w-1)
            for x in range(fill_w, w):
                self._progress_img.put(empty, to=(x, y))

    def _set_progress_full(self) -> None:
        if not self._show_hold_progress:
            return
        self._ensure_progress_image()
        if self._progress_using_image:
            self._update_progress_image(1.0)

    def _schedule_progress_tick(self) -> None:
        self._progress_after_id = self.tk.after(self._progress_update_ms, self._progress_tick)

    def _progress_tick(self) -> None:
        if not self._pressed or not self._progress_start:
            return

        frac = self._progress_fraction()
        self._update_progress_image(frac)

        if frac < 1.0:
            self._schedule_progress_tick()

    def _start_progress(self) -> None:
        if not self._show_hold_progress or self.hold_threshold <= 0:
            return

        self._progress_start = time.monotonic()
        self._cancel_progress_after()

        self._ensure_progress_image()
        if self._progress_using_image:
            self._update_progress_image(0.0)
            self._schedule_progress_tick()

    def _stop_progress(self) -> None:
        self._cancel_progress_after()
        self._progress_start = None

        if self._progress_using_image:
            self._progress_using_image = False
            self._progress_img = None

            # Restore canonical image state
            if self._normal_img:
                self.tk.config(image=self._normal_img, compound="center")
            else:
                # Remove the image so this returns to a normal text button
                self.tk.config(image="", compound="center")

    # ───────────────────────────────
    # Timer cancellation helpers
    # ───────────────────────────────
    def _cancel_after(self) -> None:
        after_id = self._after_id
        if not after_id:
            return
        self._after_id = None
        try:
            self.tk.after_cancel(after_id)
        except tk.TclError:
            # Usually: "can't delete Tcl command" / invalid or already-fired after id
            pass
        except RuntimeError:
            # Rare: during interpreter shutdown / widget teardown
            pass

    def _cancel_progress_after(self) -> None:
        after_id = self._progress_after_id
        if not after_id:
            return
        self._progress_after_id = None
        try:
            self.tk.after_cancel(after_id)
        except tk.TclError:
            pass
        except RuntimeError:
            pass
