#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

from tkinter import TclError, font as tkfont

from guizero import Text


class ScrollingText(Text):
    """
    Drop-in replacement for guizero.Text with truncation-aware marquee scrolling.

    Features:
      - Detects truncation via Tk font measurement
      - Optional auto-scroll with configurable start delay
      - Touch interaction modes:
          * "hold": press pauses and resets, release resumes
          * "toggle": tap toggles scrolling on/off
    """

    def __init__(
        self,
        *args,
        text: str = "",
        auto_scroll: bool = True,
        gap: str = "  ",
        speed_ms: int = 500,
        pause_ms: int = 0,
        start_delay_ms: int = 10_000,
        touch_mode: str = "toggle",  # "hold" or "toggle"
        **kwargs,
    ):
        super().__init__(*args, text=text, **kwargs)

        self._base_text = text
        self._gap = gap
        self._speed_ms = max(10, int(speed_ms))
        self._pause_ms = max(0, int(pause_ms))
        self._start_delay_ms = max(0, int(start_delay_ms))
        self._auto_scroll = bool(auto_scroll)
        self._touch_mode = touch_mode

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

        self._bind_press_release()
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
        """Set base text and re-evaluate scrolling."""
        self._base_text = "" if text is None else str(text)

        self.stop_scroll(reset_to_start=True, cancel_start=True)
        self._set_label_text(self._base_text)

        self._schedule_start_check(delay_ms=0)

    def set_touch_mode(self, mode: str) -> None:
        """
        Change touch interaction mode at runtime.
        Valid values: "hold", "toggle"
        """
        if mode not in ("hold", "toggle"):
            raise ValueError("touch_mode must be 'hold' or 'toggle'")

        self._touch_mode = mode
        self._unbind_touch_events()
        self._bind_press_release()

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
        return tk_font.measure(self._base_text) > widget_width

    def start_scroll(self, delay_ms: int | None = None) -> None:
        if self._pressed:
            return

        self._cancel_start()
        self._cancel_tick()

        if delay_ms is None:
            delay_ms = self._start_delay_ms
        delay_ms = max(0, int(delay_ms))

        self._running = False
        self._start_after_id = self._after(delay_ms, self._start_now)

    def stop_scroll(self, *, reset_to_start: bool = False, cancel_start: bool = True) -> None:
        self._running = False
        self._cancel_tick()
        if cancel_start:
            self._cancel_start()
        if reset_to_start:
            self._scroll_buf = ""
            self._set_label_text(self._base_text)

    # -------------------------
    # Internals: scrolling
    # -------------------------

    def _schedule_start_check(self, delay_ms: int) -> None:
        self._after(max(0, int(delay_ms)), self._auto_manage_scroll)

    def _auto_manage_scroll(self) -> None:
        if not self._auto_scroll or self._pressed:
            return

        if self.needs_scroll():
            self.start_scroll()
        else:
            self.stop_scroll(reset_to_start=True, cancel_start=True)

    def _start_now(self) -> None:
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

        self._scroll_buf = self._scroll_buf[1:] + self._scroll_buf[0]
        self._set_label_text(self._scroll_buf)

        delay = self._speed_ms
        if self._pause_ms > 0 and self._scroll_buf == (self._base_text + self._gap):
            delay = self._pause_ms

        self._cancel_tick()
        self._tick_after_id = self._after(delay, self._tick)

    # -------------------------
    # Internals: touch handling
    # -------------------------

    def _bind_press_release(self) -> None:
        try:
            self.tk.bind("<ButtonPress-1>", self._on_press, add="+")
            if self._touch_mode == "hold":
                self.tk.bind("<ButtonRelease-1>", self._on_release, add="+")
                self.tk.bind("<Leave>", self._on_leave, add="+")
        except TclError:
            pass

    def _unbind_touch_events(self) -> None:
        try:
            self.tk.unbind("<ButtonPress-1>")
            self.tk.unbind("<ButtonRelease-1>")
            self.tk.unbind("<Leave>")
        except TclError:
            pass

    def _on_press(self, _event=None) -> None:
        if not self.needs_scroll():
            return

        if self._touch_mode == "toggle":
            if self._running or self._start_after_id is not None:
                self.stop_scroll(reset_to_start=True, cancel_start=True)
            else:
                self.start_scroll(delay_ms=0)
            return

        self._pressed = True
        self.stop_scroll(reset_to_start=True, cancel_start=True)

    def _on_release(self, _event=None) -> None:
        self._pressed = False

        if self._auto_scroll and self.needs_scroll():
            self.start_scroll(delay_ms=0)

    def _on_leave(self, _event=None) -> None:
        pass

    # -------------------------
    # Internals: Tk helpers
    # -------------------------

    def _set_label_text(self, s: str) -> None:
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
