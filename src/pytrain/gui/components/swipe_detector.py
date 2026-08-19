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
import logging
import threading
import time
from tkinter import TclError

from guizero.base import Widget

log = logging.getLogger(__name__)


class SwipeDetector:
    def __init__(self, widget: Widget, min_distance=50, max_time=0.5, long_press_time=0.6, max_move_for_long_press=10):
        """
        min_distance: minimum swipe distance in pixels
        max_time: max duration of swipe gesture
        long_press_time: seconds finger must remain down to count as long press
        max_move_for_long_press: if movement exceeds this, long press is canceled
        """
        self.widget = widget
        self.min_distance = min_distance
        self.max_time = max_time
        self.long_press_time = long_press_time
        self.max_move_for_long_press = max_move_for_long_press

        self.start_x = None
        self.start_y = None
        self.start_time = None
        self.long_press_timer = None
        self.long_press_fired = False

        widget.when_left_button_pressed = self._on_press
        widget.when_mouse_moved = self._on_move
        widget.when_left_button_released = self._on_release

        # user callback hooks:
        self.on_swipe_left = None
        self.on_swipe_right = None
        self.on_long_press = None

    # ------------------------------

    def _cancel_long_press_timer(self):
        if self.long_press_timer:
            self.long_press_timer.cancel()
            self.long_press_timer = None
            self.long_press_fired = False

    # ------------------------------
    #
    # def _trigger_long_press(self):
    #     self.long_press_fired = True
    #     if self.on_long_press:
    #         self.on_long_press()

    def _trigger_long_press(self) -> None:
        if self.long_press_fired:
            return

        self.long_press_fired = True
        if self.on_long_press:
            try:
                self.widget.tk.after(0, self.on_long_press)
            except TclError:
                pass

    # ------------------------------

    def _on_press(self, e):
        # TEMPORARY SWIPE DIAGNOSTIC (remove with the rest): where the press landed
        # inside the widget, and where the widget sits on screen. A gesture that logs
        # no press at all never reached this widget.
        try:
            tk = self.widget.tk
            log.info(
                "SWIPE-DIAG press: at (%s,%s) in widget %sx%s whose left edge is screen x=%s (so screen x=%s)",
                e.x,
                e.y,
                tk.winfo_width(),
                tk.winfo_height(),
                tk.winfo_rootx(),
                tk.winfo_rootx() + e.x,
            )
        except (AttributeError, TclError):
            pass
        self._first_move_logged = False

        self.start_x = e.x
        self.start_y = e.y
        self.start_time = time.monotonic()
        self.long_press_fired = False

        # start long-press timer
        self._cancel_long_press_timer()
        self.long_press_timer = threading.Timer(self.long_press_time, self._trigger_long_press)
        self.long_press_timer.daemon = True
        self.long_press_timer.start()

    # ------------------------------

    def _on_move(self, e):
        # cancel long-press if moved too far
        if self.start_x is not None:
            # TEMPORARY SWIPE DIAGNOSTIC: log only the FIRST move of each gesture.
            # _on_move fires continuously, and logging every one would stall the Tk
            # loop (it is the same thread that services the touch screen).
            if not getattr(self, "_first_move_logged", True):
                self._first_move_logged = True
                log.info("SWIPE-DIAG first move: to (%s,%s) from (%s,%s)", e.x, e.y, self.start_x, self.start_y)
            if (
                abs(e.x - self.start_x) > self.max_move_for_long_press
                or abs(e.y - self.start_y) > self.max_move_for_long_press
            ):
                self._cancel_long_press_timer()

    # ------------------------------

    def _on_release(self, e):
        # TEMPORARY SWIPE DIAGNOSTIC (remove once the left-swipe bug is fixed):
        # one log line per gesture -- never log from _on_move, which fires
        # continuously and would stall the Tk loop.
        long_press_had_fired = self.long_press_fired
        self._cancel_long_press_timer()

        # if long press fired, stop — it's not a swipe
        if long_press_had_fired:
            log.info("SWIPE-DIAG release: rejected, long press had fired")
            self.start_x = self.start_y = self.start_time = None
            return

        # -- swipe detection --
        if self.start_x is None:
            log.info("SWIPE-DIAG release: rejected, no press recorded (start_x is None)")
            return

        end_x = e.x
        end_y = e.y
        dt = time.monotonic() - self.start_time

        dx = end_x - self.start_x
        dy = end_y - self.start_y

        self.start_x = self.start_y = self.start_time = None

        measurements = f"dt={dt:.3f}s dx={dx} dy={dy} (max_time={self.max_time} min_distance={self.min_distance})"

        # swipe must be fast
        if dt > self.max_time:
            log.info("SWIPE-DIAG release: rejected, too slow -- %s", measurements)
            return

        # swipe must be wide enough
        if abs(dx) < self.min_distance:
            log.info("SWIPE-DIAG release: rejected, too short -- %s", measurements)
            return

        # primarily horizontal
        if abs(dx) <= abs(dy):
            log.info("SWIPE-DIAG release: rejected, not primarily horizontal -- %s", measurements)
            return

        # direction
        try:
            if dx > 0:
                log.info(
                    "SWIPE-DIAG release: accepted RIGHT (dx>0, on_swipe_right=%s) -- %s",
                    "set" if self.on_swipe_right else "None",
                    measurements,
                )
                if self.on_swipe_right:
                    self.widget.tk.after(0, self.on_swipe_right)
            else:
                log.info(
                    "SWIPE-DIAG release: accepted LEFT (dx<0, on_swipe_left=%s) -- %s",
                    "set" if self.on_swipe_left else "None",
                    measurements,
                )
                if self.on_swipe_left:
                    self.widget.tk.after(0, self.on_swipe_left)
        except TclError:
            pass
