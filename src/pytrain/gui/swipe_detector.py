#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
import time
import threading

from guizero.base import Widget


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

    # ------------------------------

    def _trigger_long_press(self):
        self.long_press_fired = True
        if self.on_long_press:
            self.on_long_press()

    # ------------------------------

    def _on_press(self, e):
        self.start_x = e.x
        self.start_y = e.y
        self.start_time = time.time()
        self.long_press_fired = False

        # start long-press timer
        self._cancel_long_press_timer()
        self.long_press_timer = threading.Timer(self.long_press_time, self._trigger_long_press)
        self.long_press_timer.start()

    # ------------------------------

    def _on_move(self, e):
        # cancel long-press if moved too far
        if self.start_x is not None:
            if (
                abs(e.x - self.start_x) > self.max_move_for_long_press
                or abs(e.y - self.start_y) > self.max_move_for_long_press
            ):
                self._cancel_long_press_timer()

    # ------------------------------

    def _on_release(self, e):
        self._cancel_long_press_timer()

        # if long press fired, stop — it's not a swipe
        if self.long_press_fired:
            self.start_x = self.start_y = self.start_time = None
            return

        # -- swipe detection --
        if self.start_x is None:
            return

        end_x = e.x
        end_y = e.y
        dt = time.time() - self.start_time

        dx = end_x - self.start_x
        dy = end_y - self.start_y

        self.start_x = self.start_y = self.start_time = None

        # swipe must be fast
        if dt > self.max_time:
            return

        # swipe must be wide enough
        if abs(dx) < self.min_distance:
            return

        # primarily horizontal
        if abs(dx) <= abs(dy):
            return

        # direction
        if dx > 0:
            if self.on_swipe_right:
                self.on_swipe_right()
        else:
            if self.on_swipe_left:
                self.on_swipe_left()
