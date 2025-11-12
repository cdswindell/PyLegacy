#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import time

from guizero import PushButton


class HoldButton:
    """
    A guizero PushButton with enhanced touch/mouse behavior:
      - on_press: single short press
      - on_hold: fires once after holding for hold_threshold seconds
      - on_repeat: continuously fires while held down

    Each callback may be:
        func
        or (func, args, kwargs)
    """

    def __init__(
        self,
        parent,
        text,
        on_press=None,
        on_hold=None,
        on_repeat=None,
        hold_threshold=0.5,
        repeat_interval=0.2,
        debounce_ms=80,
        **kwargs,
    ):
        # store callbacks (can be changed later)
        self._on_press = on_press
        self._on_hold = on_hold
        self._on_repeat = on_repeat

        self.hold_threshold = hold_threshold
        self.repeat_interval = repeat_interval
        self.debounce_ms = debounce_ms

        self._press_time = None
        self._held = False
        self._repeating = False
        self._after_id = None

        # create the base guizero PushButton (no default command)
        self.button = PushButton(parent, text=text, **kwargs)

        # handle both mouse and touchscreen
        self.button.tk.bind("<ButtonPress-1>", self._on_press_event, add="+")
        self.button.tk.bind("<ButtonRelease-1>", self._on_release_event, add="+")

    # ───────────────────────────────
    # Properties for dynamic assignment
    # ───────────────────────────────
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
    # Event handlers
    # ───────────────────────────────
    # noinspection PyUnusedLocal
    def _on_press_event(self, event=None):
        self._press_time = time.time()
        self._held = False
        self._repeating = False

        # schedule hold trigger
        self._after_id = self.button.tk.after(int(self.hold_threshold * 1000), self._trigger_hold_or_repeat)

    # noinspection PyUnusedLocal
    def _on_release_event(self, event=None):
        # cancel any pending after() callback
        if self._after_id:
            self.button.tk.after_cancel(self._after_id)
            self._after_id = None

        elapsed = (time.time() - self._press_time) if self._press_time else 0
        if elapsed < self.debounce_ms / 1000:
            return

        if self._repeating:
            self._repeating = False
        elif not self._held:
            self._invoke_callback(self._on_press)

    def _trigger_hold_or_repeat(self):
        self._held = True
        if self._on_repeat:
            self._repeating = True
            self._repeat_fire()
        elif self._on_hold:
            self._invoke_callback(self._on_hold)

    def _repeat_fire(self):
        if not self._repeating:
            return
        self._invoke_callback(self._on_repeat)
        self._after_id = self.button.tk.after(int(self.repeat_interval * 1000), self._repeat_fire)

    # ───────────────────────────────
    # Helper: safe callback invocation
    # ───────────────────────────────
    @staticmethod
    def _invoke_callback(cb):
        """
        Invoke callback allowing:
            func
            (func, args)
            (func, args, kwargs)
        """
        if not cb:
            return
        if callable(cb):
            cb()
        elif isinstance(cb, (tuple, list)) and len(cb) > 0:
            func = cb[0]
            args = cb[1] if len(cb) > 1 else []
            kwargs = cb[2] if len(cb) > 2 else {}
            func(*args, **kwargs)
