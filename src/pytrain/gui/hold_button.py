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


class HoldButton(PushButton):
    """
    A PushButton subclass that adds:
      - on_press  → single short tap, or fired when held if no hold/repeat defined
      - on_hold   → single fire after hold_threshold seconds
      - on_repeat → continuous fire while held
    Each callback can be:
        func
        or (func, args)
        or (func, args, kwargs)
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
        text_size: int = None,
        text_bold: bool = None,
        flash: bool = True,
        **kwargs,
    ):
        super().__init__(master, text=text, **kwargs)

        # base properties, new to HoldButton
        self._normal_bg = None
        self._normal_fg = None

        # basic button properties
        if bg:
            self.bg = bg
        if text_color:
            self.text_color = text_color
        if text_size is not None:
            self.text_size = text_size
        if text_bold is not None:
            self.text_bold = text_bold

        # callback configuration
        self._on_press = on_press
        self._on_hold = on_hold
        self._on_repeat = on_repeat

        # timing and state tracking
        self.hold_threshold = hold_threshold
        self.repeat_interval = repeat_interval
        self.debounce_ms = debounce_ms
        self._press_time = None
        self._held = False
        self._repeating = False
        self._after_id = None
        self._handled_hold = False
        self._handled_flash = False

        # bind events (mouse and touchscreen compatible)
        self.when_left_button_pressed = self._on_press_event
        self.when_left_button_released = self._on_release_event

        # flash button on press, if requested
        self._flash_requested = flash
        if flash and text:
            self.do_flash()

    # ───────────────────────────────
    # Parent setter overrides
    # ───────────────────────────────
    @PushButton.text.setter
    def text(self, value):
        PushButton.text.fset(self, value)
        if self._flash_requested and value:
            self.do_flash()

    # ───────────────────────────────
    # Properties for dynamic callbacks
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
    # Internal event handlers
    # ───────────────────────────────
    # noinspection PyUnusedLocal
    def _on_press_event(self, event=None):
        self._press_time = time.time()
        self._held = False
        self._repeating = False
        self._handled_hold = False

        # schedule hold trigger
        self._after_id = self.tk.after(int(self.hold_threshold * 1000), self._trigger_hold_or_repeat)

    # noinspection PyUnusedLocal
    def _on_release_event(self, event=None):
        if self._after_id:
            self.tk.after_cancel(self._after_id)
            self._after_id = None

        elapsed = (time.time() - self._press_time) if self._press_time else 0
        if elapsed < self.debounce_ms / 1000:
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

    def _trigger_hold_or_repeat(self):
        self._held = True
        handled = False

        if self._on_repeat:
            self._repeating = True
            self._repeat_fire()
            handled = True
        elif self._on_hold:
            self._invoke_callback(self._on_hold)
            handled = True
        elif self._on_press and not self._on_hold and not self._on_repeat:
            # fire on_press here if no dedicated hold/repeat
            self._invoke_callback(self._on_press)
            handled = True

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

        # noinspection PyUnusedLocal
        def on_press(event):
            self._normal_bg = self.bg
            self._normal_fg = self.text_color
            self.bg = pressed_bg
            self.text_color = pressed_fg

        # noinspection PyUnusedLocal
        def on_release(event):
            self.bg = self._normal_bg
            self.text_color = self._normal_fg

        # bind both events
        self.tk.bind("<ButtonPress-1>", on_press, add="+")
        self.tk.bind("<ButtonRelease-1>", on_release, add="+")

    def restore_color_state(self):
        if self._normal_bg and self.bg != self._normal_bg:
            self.bg = self._normal_bg
        if self._normal_fg and self.text_color != self._normal_fg:
            self.text_color = self._normal_fg
