#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

from tkinter import TclError
from tkinter import font as tkfont

from guizero import Text


class ScrollingText(Text):
    """
    Drop-in replacement for guizero.Text with truncation-aware marquee scrolling.

    Additions vs. previous version:
      - start_delay_ms: wait this long BEFORE starting scrolling
      - press-to-pause: mouse/touch press stops scrolling and resets to start;
                        release resumes (after start_delay_ms)

    Notes:
      - Intended for single-line ticker use.
      - Uses Tk font measurement for accurate truncation detection.
    """

    def __init__(
        self,
        *args,
        text: str = "",
        auto_scroll: bool = True,
        gap: str = "  ",
        speed_ms: int = 500,
        pause_ms: int = 0,
        start_delay_ms: int = 10_000,  # 10 seconds default
        **kwargs,
    ):
        super().__init__(*args, text=text, **kwargs)

        self._base_text = text
        self._gap = gap
        self._speed_ms = max(10, int(speed_ms))
        self._pause_ms = max(0, int(pause_ms))
        self._start_delay_ms = max(0, int(start_delay_ms))
        self._auto_scroll = bool(auto_scroll)

        self._running = False
        self._pressed = False

        self._tick_after_id: str | None = None
        self._start_after_id: str | None = None

        self._scroll_buf = ""

        # Enforce single-line behavior
        try:
            self.tk.config(wraplength=0)
        except TclError:
            pass

        # Press/release bindings for mouse + touch-like behavior
        self._bind_press_release()

        # Kick off auto-management after geometry settles
        self._schedule_start_check(delay_ms=0)

    # -------------------------
    # Public API
    # -------------------------

    @property
    def value(self) -> str:
        return super().value

    @value.setter
    def value(self, new_text: str) -> None:
        self.set_text(new_text)

    def set_text(self, text: str) -> None:
        self.stop_scroll()  # <-- force stop on every value change
        """Set base text and re-evaluate scrolling (with start delay)."""
        self._base_text = "" if text is None else str(text)

        # You said you already added the "stop on assign" behavior—so keep it:
        self.stop_scroll(reset_to_start=True, cancel_start=True)
        self._set_label_text(self._base_text)

        self._schedule_start_check(delay_ms=0)

    def needs_scroll(self) -> bool:
        """True if base text width exceeds widget width."""
        label = self.tk

        try:
            label.update_idletasks()
        except TclError:
            return False

        widget_width = label.winfo_width()
        if widget_width <= 1:
            return False

        tk_font = tkfont.Font(font=label.cget("font"))
        text_px = tk_font.measure(self._base_text)
        return text_px > widget_width

    def start_scroll(self, delay_ms: int | None = None) -> None:
        """
        Begin scrolling. If delay_ms is provided (or start_delay_ms is set),
        scrolling begins after that delay.
        """
        if self._pressed:
            return

        self._cancel_start()
        self._cancel_tick()

        if delay_ms is None:
            delay_ms = self._start_delay_ms
        delay_ms = max(0, int(delay_ms))

        # If already running, just keep ticking
        if self._running and delay_ms == 0:
            self._tick()
            return

        # Not running yet; schedule actual start
        self._running = False
        self._start_after_id = self._after(delay_ms, self._start_now)

    def stop_scroll(self, *, reset_to_start: bool = False, cancel_start: bool = True) -> None:
        """Stop scrolling. Optionally reset to base text start, and cancel pending start."""
        self._running = False
        self._cancel_tick()
        if cancel_start:
            self._cancel_start()
        if reset_to_start:
            self._scroll_buf = ""
            self._set_label_text(self._base_text)

    def set_speed(self, speed_ms: int) -> None:
        self._speed_ms = max(10, int(speed_ms))

    def set_gap(self, gap: str) -> None:
        self._gap = "" if gap is None else str(gap)
        if self._running:
            self._scroll_buf = self._base_text + self._gap

    def set_start_delay(self, start_delay_ms: int) -> None:
        self._start_delay_ms = max(0, int(start_delay_ms))

    def set_auto_scroll(self, enabled: bool) -> None:
        self._auto_scroll = bool(enabled)
        self._schedule_start_check(delay_ms=0)

    # -------------------------
    # Internals: scrolling
    # -------------------------

    def _schedule_start_check(self, delay_ms: int) -> None:
        """Re-evaluate whether we should scroll (auto_scroll), respecting press state and delay."""
        self._after(max(0, int(delay_ms)), self._auto_manage_scroll)

    def _auto_manage_scroll(self) -> None:
        if not self._auto_scroll or self._pressed:
            return

        if self.needs_scroll():
            # start after delay
            self.start_scroll()
        else:
            # stop immediately
            self.stop_scroll(reset_to_start=True, cancel_start=True)

    def _start_now(self) -> None:
        """Actual start (after delay)."""
        self._start_after_id = None

        if self._pressed:
            return
        if self._auto_scroll and not self.needs_scroll():
            return

        self._running = True
        self._scroll_buf = self._base_text + self._gap
        self._set_label_text(self._scroll_buf)
        self._tick()

    def _tick(self) -> None:
        if not self._running or self._pressed:
            return

        if not self._scroll_buf:
            self._scroll_buf = self._base_text + self._gap

        # Rotate left by one character
        self._scroll_buf = self._scroll_buf[1:] + self._scroll_buf[0]
        self._set_label_text(self._scroll_buf)

        delay = self._speed_ms
        if self._pause_ms > 0 and self._scroll_buf == (self._base_text + self._gap):
            delay = self._pause_ms

        self._cancel_tick()
        self._tick_after_id = self._after(delay, self._tick)

    # -------------------------
    # Internals: press/release
    # -------------------------

    def _bind_press_release(self) -> None:
        # Mouse press/release
        try:
            self.tk.bind("<ButtonPress-1>", self._on_press, add="+")
            self.tk.bind("<ButtonRelease-1>", self._on_release, add="+")
            # A little extra robustness if pointer leaves widget while pressed:
            self.tk.bind("<Leave>", self._on_leave, add="+")
        except TclError:
            pass

    def _on_press(self, _event=None) -> None:
        # Stop + reset immediately, cancel any pending start
        self._pressed = True
        self.stop_scroll(reset_to_start=True, cancel_start=True)

    def _on_release(self, _event=None) -> None:
        self._pressed = False
        # Resume (after start delay) if it needs scrolling / auto_scroll enabled
        self._schedule_start_check(delay_ms=0)

    def _on_leave(self, _event=None) -> None:
        # If user drags off while pressed, we keep paused until release
        pass

    # -------------------------
    # Internals: Tk helpers
    # -------------------------

    def _set_label_text(self, s: str) -> None:
        # Avoid recursion through our overridden .value setter
        super(ScrollingText, self.__class__).value.fset(self, s)  # type: ignore

    def _after(self, delay_ms: int, fn) -> str | None:
        try:
            return self.tk.after(int(delay_ms), fn)
        except TclError:
            return None

    def _cancel_tick(self) -> None:
        if self._tick_after_id is None:
            return
        try:
            self.tk.after_cancel(self._tick_after_id)
        except TclError:
            pass
        finally:
            self._tick_after_id = None

    def _cancel_start(self) -> None:
        if self._start_after_id is None:
            return
        try:
            self.tk.after_cancel(self._start_after_id)
        except TclError:
            pass
        finally:
            self._start_after_id = None
