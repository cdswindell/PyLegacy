from __future__ import annotations

import time
from collections import deque
from threading import Condition, Event
from typing import List, Callable

from gpiozero import Button, CompositeDevice, GPIOPinMissing, DigitalOutputDevice, event, EventsMixin
from gpiozero.threads import GPIOThread

DEFAULT_4X4_KEYS = (
    ("1", "2", "3", "A"),
    ("4", "5", "6", "B"),
    ("7", "8", "9", "C"),
    ("*", "0", "#", "D"),
)

TELEPHONE_4X3_KEYS = (
    ("1", "2", "3"),
    ("4", "5", "6"),
    ("7", "8", "9"),
    ("*", "0", "#"),
)


class Keypad(EventsMixin, CompositeDevice):
    def __init__(
        self,
        row_pins: List[int | str],
        column_pins: List[int | str],
        bounce_time: float = None,
        keys: List[List[str]] = DEFAULT_4X4_KEYS,
        pin_factory=None,
        key_queue: KeyQueue = None,
    ):
        if keys is None or len(keys) == 0:
            raise ValueError("Must specify at least one row of keys")
        if len(row_pins) != len(keys):
            raise GPIOPinMissing(f"Number of row pins must match the number of rows ({len(row_pins)} != {len(keys)})")
        num_cols = len(keys[0])
        if len(column_pins) != num_cols:
            raise ValueError(
                f"Number of column pins must match the number of keys ({len(column_pins)} != {len(keys[0])})"
            )

        devices = []
        self._rows = []
        for pin in row_pins:
            dev = DigitalOutputDevice(pin, pin_factory=pin_factory)
            self._rows.append(dev)
            devices.append(dev)

        self._cols = []
        for pin in column_pins:
            dev = Button(
                pin,
                pull_up=False,
                bounce_time=bounce_time,
                hold_repeat=False,
                active_state=None,
                pin_factory=pin_factory,
            )
            self._cols.append(dev)
            devices.append(dev)
        super().__init__(*devices, pin_factory=pin_factory)

        if len(self) == 0:
            raise GPIOPinMissing("No pins given")

        # _handlers only exists to ensure that we keep a reference to the
        # generated fire_both_events handler for each Button (remember that
        # pin.when_changed only keeps a weak reference to handlers)
        def get_new_handler(device):
            def fire_both_events(ticks, state):
                # noinspection PyProtectedMember
                device._fire_events(ticks, device._state_to_value(state))
                self._fire_events(ticks, self.is_active)

            return fire_both_events

        self._handlers = tuple(get_new_handler(device) for device in self._cols)
        for button, handler in zip(self._cols, self._handlers):
            button.pin.when_changed = handler

        self._when_changed = None
        self._last_value = None
        self._keypress = self._last_keypress = None
        self._keys = keys
        if key_queue is None:
            self._key_queue = KeyQueue()
        elif isinstance(key_queue, KeyQueue):
            self._key_queue = key_queue
        else:
            raise ValueError(f"{key_queue} is not a KeyQueue")
        self.when_pressed = self._key_queue.keypress_handler()

        # Call _fire_events once to set initial state of events
        self._fire_events(self.pin_factory.ticks(), self.is_active)

        # create the background thread to continually scan the matrix
        self._scan_thread = GPIOThread(self._scan_keyboard)
        self._is_running = True
        self._scan_thread.start()

    def close(self) -> None:
        self._is_running = False
        self._reset_pin_states()
        super().close()

    @property
    def keypress(self) -> str | None:
        return self._keypress

    @property
    def last_keypress(self) -> str | None:
        return self._last_keypress

    @property
    def key_queue(self) -> KeyQueue:
        return self._key_queue

    """
    The following methods expose behavior of KeyQueue and are
    repeated here for convenience
    """

    def reset_keypresses(self) -> None:
        self._key_queue.reset()
        self._keypress = self._last_keypress = None

    def wait_for_eol(self, timeout: float = 10) -> str | None:
        return self._key_queue.wait_for_eol(timeout)

    @property
    def keypresses(self) -> str:
        return self._key_queue.keypresses

    @property
    def is_eol(self) -> bool:
        return self._key_queue.is_eol

    when_changed = event()

    def _fire_changed(self):
        if self.when_changed:
            self.when_changed()

    def _fire_events(self, ticks, new_value):
        super()._fire_events(ticks, new_value)
        old_value, self._last_value = self._last_value, new_value
        if old_value is None:
            # Initial "indeterminate" value; don't do anything
            pass
        elif old_value != new_value:
            self._fire_changed()

    def _reset_pin_states(self) -> None:
        """
        Resets the states of all pins associated with the rows.

        Sets the state of each row pin to 'off' if it is not already closed.
        """
        for r in self._rows:
            if r.closed is False:
                r.off()

    def _scan_keyboard(self) -> None:
        """
        Scan the keys and handle keypress events in a loop that runs in a
        background thread.

        This method continuously scans the keys of a matrix keypad until
        the _is_running flag is set to False. For each row, it checks each
        column to detect if a key is pressed and handles keypress events
        accordingly.

        The method ensures a rest period to avoid excessive CPU usage
        when no key is pressed.
        """
        while self._is_running:
            self._reset_pin_states()
            self._keypress = None
            for r, row in enumerate(self._rows):
                row.on()
                try:
                    for c, col in enumerate(self._cols):
                        if col.is_active:
                            self._keypress = self._last_keypress = self._keys[r][c]
                            self._fire_events(self.pin_factory.ticks(), True)
                            while col.is_active:
                                time.sleep(0.05)
                            self._fire_events(self.pin_factory.ticks(), False)
                            break
                finally:
                    if self._keypress:
                        break
                    row.off()
            if self._keypress is None:
                time.sleep(0.05)  # give CPU a break


Keypad.is_pressed = Keypad.is_active
Keypad.pressed_time = Keypad.active_time
Keypad.when_pressed = Keypad.when_activated
Keypad.when_released = Keypad.when_deactivated
Keypad.wait_for_press = Keypad.wait_for_active
Keypad.wait_for_release = Keypad.wait_for_inactive


class KeyQueue:
    def __init__(
        self,
        clear_key: str = "C",
        eol_key: str = "#",
        max_length: int = 256,
    ) -> None:
        self._deque: deque[str] = deque(maxlen=max_length)
        self._clear_key = clear_key
        self._eol_key = eol_key
        self._cv = Condition()
        self._keypress_ev = Event()
        self._eol_ev = Event() if eol_key else None
        self._clear_ev = Event() if clear_key else None

    def keypress_handler(self) -> Callable:
        def fn(keypad: Keypad) -> None:
            keypress = keypad.keypress
            if keypress:
                with self._cv:
                    self._keypress_ev.clear()
                    if self._eol_ev:
                        self._eol_ev.clear()
                    if self._clear_ev:
                        self._clear_ev.clear()
                    if keypress == self._clear_key:
                        self._deque.clear()
                        if self._clear_ev:
                            self._clear_ev.set()
                    elif keypress == self._eol_key:
                        if self._eol_ev:
                            self._eol_ev.set()
                    else:
                        print(f"Extending {keypress}")
                        self._deque.extend(keypress)
                    self._keypress_ev.set()
                    self._cv.notify()

        return fn

    __call__ = keypress_handler

    @property
    def keypresses(self) -> str:
        with self._cv:
            return "".join(self._deque)

    def reset(self) -> None:
        with self._cv:
            self._deque.clear()
            self._eol_ev.clear()
            self._clear_ev.clear()
            self._keypress_ev.clear()
            self._cv.notify()

    @property
    def is_eol(self) -> bool:
        return self._eol_ev.is_set() if self._eol_ev else False

    @property
    def is_clear(self) -> bool:
        return self._clear_ev.is_set() if self._eol_ev else False

    def wait_for_keypress(self, timeout: float = 10) -> str | None:
        try:
            self._keypress_ev.wait(timeout)
            if self._keypress_ev.is_set() is False or self._keypress_ev.is_set() or self._clear_ev.is_set():
                return None
            else:
                return self._deque[-1] if len(self._deque) > 0 else None
        finally:
            self._keypress_ev.clear()

    def wait_for_eol(self, timeout: float = 10) -> str | None:
        if self._eol_ev:
            self._eol_ev.wait(timeout)
            if self._eol_ev.is_set():
                self._eol_ev.clear()
                return self.keypresses
        return None


# Initialize the columns
# col1 = Button(12, pull_up=False)
# col2 = Button(16, pull_up=False)
# col3 = Button(20, pull_up=False)
# col4 = Button(21, pull_up=False)
# columns = [col1, col2, col3, col4]
#
# row1 = LED(18)
# row2 = LED(23)
# row3 = LED(24)
# row4 = LED(25)
# rows = [row1, row2, row3, row4]
