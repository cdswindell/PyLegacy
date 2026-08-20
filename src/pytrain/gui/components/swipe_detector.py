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


def event_screen_y(event) -> int | None:
    """Screen-relative y of an event, for either event shape a handler may receive.

    guizero delivers its own ``EventData`` (screen coords via ``display_y``) when a
    callback is attached through a ``when_*`` hook, while a callback bound straight
    onto a Tk widget receives the raw Tk event (``y_root``). Returns None if neither
    is present.
    """
    for attribute in ("display_y", "y_root"):
        value = getattr(event, attribute, None)
        if value is not None:
            return int(value)
    return None


def event_targets(event) -> tuple:
    """Widgets an event may be attributed to: guizero widget and/or Tk widget.

    ``EventData.widget`` is the *guizero* widget; a raw Tk event's ``widget`` is the
    Tk one. Callers comparing against a known widget need to accept either.
    """
    target = getattr(event, "widget", None)
    if target is None:
        return ()
    return (target, getattr(target, "tk", None))


class SwipeDetector:
    def __init__(
        self,
        widget: Widget,
        min_distance=50,
        max_time=0.5,
        long_press_time=0.6,
        max_move_for_long_press=10,
        should_start=None,
        bind_directly=False,
    ):
        """
        min_distance: minimum swipe distance in pixels
        max_time: max duration of swipe gesture
        long_press_time: seconds finger must remain down to count as long press
        max_move_for_long_press: if movement exceeds this, long press is canceled
        should_start: optional predicate taking the press event; when it returns
            False the whole gesture is ignored. Needed when the detector is attached
            to a large container that covers more than the region of interest -- the
            predicate restricts the gesture to that region.
        bind_directly: bind the Tk widget instead of using guizero's ``when_*`` hooks.
            Required when the widget already has raw Tk bindings that must survive:
            guizero binds without ``add="+"``, so attaching a hook *replaces* any
            existing binding for that event (and ``<Button-1>`` and ``<ButtonPress-1>``
            are the same Tk sequence). Handlers then receive raw Tk events rather than
            guizero ``EventData`` -- use the module helpers above to read either.
        """
        self.widget = widget
        self.min_distance = min_distance
        self.max_time = max_time
        self.long_press_time = long_press_time
        self.max_move_for_long_press = max_move_for_long_press
        self.should_start = should_start

        self.start_x = None
        self.start_y = None
        self.start_time = None
        self.long_press_timer = None
        self.long_press_fired = False

        # Every guizero widget (containers included -- EventsMixin comes in via
        # Component) exposes ``when_*`` hooks, so prefer them unless the caller asks
        # for direct binding, or the object has no hooks at all. Direct binding uses
        # ``add="+"`` so existing bindings on the widget survive, which guizero's own
        # hooks would silently discard.
        if not bind_directly and hasattr(type(widget), "when_left_button_pressed"):
            widget.when_left_button_pressed = self._on_press
            widget.when_mouse_moved = self._on_move
            widget.when_left_button_released = self._on_release
        else:
            widget.tk.bind("<ButtonPress-1>", self._on_press, add="+")
            widget.tk.bind("<Motion>", self._on_move, add="+")
            widget.tk.bind("<ButtonRelease-1>", self._on_release, add="+")

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
        if self.should_start is not None and not self.should_start(e):
            # Outside this detector's region of interest: drop the whole gesture, so
            # the matching release cannot be mistaken for a swipe.
            self.start_x = self.start_y = self.start_time = None
            self._cancel_long_press_timer()
            return

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
        # cancel long-press if moved too far. Deliberately does no logging: this fires
        # continuously during a drag, on the same thread that services the touch
        # screen, so even a debug call here is a real cost.
        if self.start_x is not None:
            if (
                abs(e.x - self.start_x) > self.max_move_for_long_press
                or abs(e.y - self.start_y) > self.max_move_for_long_press
            ):
                self._cancel_long_press_timer()

    # ------------------------------

    def _on_release(self, e):
        # Read the long-press flag *before* cancelling the timer: cancelling resets
        # it, which would let an already-fired long press be taken for a swipe.
        long_press_had_fired = self.long_press_fired
        self._cancel_long_press_timer()

        # if long press fired, stop — it's not a swipe
        if long_press_had_fired:
            self.start_x = self.start_y = self.start_time = None
            return

        # -- swipe detection --
        if self.start_x is None:
            # No matching press: either should_start rejected it, or the press went to
            # a different widget.
            return

        end_x = e.x
        end_y = e.y
        dt = time.monotonic() - self.start_time

        dx = end_x - self.start_x
        dy = end_y - self.start_y

        self.start_x = self.start_y = self.start_time = None

        rejected = None
        if dt > self.max_time:
            rejected = "too slow"
        elif abs(dx) < self.min_distance:
            rejected = "too short"
        elif abs(dx) <= abs(dy):
            rejected = "not primarily horizontal"
        if rejected is not None:
            # One line per gesture, at debug: which threshold dropped a swipe is
            # otherwise invisible, and "nothing happened" is the hardest symptom to
            # chase on a touch screen.
            log.debug(
                "swipe rejected (%s): dt=%.3fs dx=%s dy=%s (max_time=%s min_distance=%s)",
                rejected,
                dt,
                dx,
                dy,
                self.max_time,
                self.min_distance,
            )
            return

        # direction
        try:
            if dx > 0:
                log.debug("swipe right: dt=%.3fs dx=%s dy=%s", dt, dx, dy)
                if self.on_swipe_right:
                    self.widget.tk.after(0, self.on_swipe_right)
            else:
                log.debug("swipe left: dt=%.3fs dx=%s dy=%s", dt, dx, dy)
                if self.on_swipe_left:
                    self.widget.tk.after(0, self.on_swipe_left)
        except TclError:
            pass
