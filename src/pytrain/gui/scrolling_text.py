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
    Drop-in replacement for guizero.Text with automatic marquee scrolling.

    - Detects truncation via Tk font measurement
    - Scrolls right-to-left only when needed (or always, if forced)
    - Uses Tk's after(), no threads
    """

    def __init__(
        self,
        *args,
        text: str = "",
        auto_scroll: bool = True,
        gap: str = "  ",
        speed_ms: int = 1000,
        pause_ms: int = 0,
        **kwargs,
    ):
        super().__init__(*args, text=text, **kwargs)

        self._base_text = text
        self._gap = gap
        self._speed_ms = int(speed_ms)
        self._pause_ms = int(pause_ms)
        self._auto_scroll = bool(auto_scroll)

        self._running = False
        self._after_id: str | None = None
        self._scroll_buf = ""

        # Enforce single-line behavior
        try:
            self.tk.config(wraplength=0)
        except TclError:
            pass

        self._schedule(self._auto_manage_scroll, delay_ms=0)

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
        self._base_text = "" if text is None else str(text)

        if not self._running:
            super(ScrollingText, self.__class__).value.fset(self, self._base_text)  # type: ignore

        self._schedule(self._auto_manage_scroll, delay_ms=0)

    def needs_scroll(self) -> bool:
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

    def start_scroll(self) -> None:
        if self._running:
            return

        self._running = True
        self._scroll_buf = self._base_text + self._gap

        super(ScrollingText, self.__class__).value.fset(self, self._scroll_buf)  # type: ignore
        self._tick()

    def stop_scroll(self) -> None:
        self._running = False
        self._cancel_scheduled_tick()
        super(ScrollingText, self.__class__).value.fset(self, self._base_text)  # type: ignore

    def set_speed(self, speed_ms: int) -> None:
        self._speed_ms = max(10, int(speed_ms))

    def set_gap(self, gap: str) -> None:
        self._gap = "" if gap is None else str(gap)
        if self._running:
            self._scroll_buf = self._base_text + self._gap

    def set_auto_scroll(self, enabled: bool) -> None:
        self._auto_scroll = bool(enabled)
        self._schedule(self._auto_manage_scroll, delay_ms=0)

    # -------------------------
    # Internals
    # -------------------------

    def _auto_manage_scroll(self) -> None:
        if not self._auto_scroll:
            return

        if self.needs_scroll():
            if not self._running:
                self.start_scroll()
        else:
            if self._running:
                self.stop_scroll()

    def _tick(self) -> None:
        if not self._running:
            return

        if not self._scroll_buf:
            self._scroll_buf = self._base_text + self._gap

        self._scroll_buf = self._scroll_buf[1:] + self._scroll_buf[0]
        super(ScrollingText, self.__class__).value.fset(self, self._scroll_buf)  # type: ignore

        delay = self._speed_ms
        if self._pause_ms > 0 and self._scroll_buf == (self._base_text + self._gap):
            delay = self._pause_ms

        self._schedule(self._tick, delay_ms=delay)

    def _schedule(self, fn, delay_ms: int) -> None:
        try:
            self._after_id = self.tk.after(int(delay_ms), fn)
        except TclError:
            self._after_id = None

    def _cancel_scheduled_tick(self) -> None:
        if self._after_id is None:
            return
        try:
            self.tk.after_cancel(self._after_id)
        except TclError:
            pass
        finally:
            self._after_id = None
