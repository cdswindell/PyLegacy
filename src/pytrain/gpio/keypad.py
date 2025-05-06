from __future__ import annotations

import time
from collections import deque
from threading import Condition, Event
from typing import List, Callable

from gpiozero import Button, CompositeDevice, GPIOPinMissing, DigitalOutputDevice, event, EventsMixin
from gpiozero.threads import GPIOThread
from smbus2 import SMBus

from .gpio_handler import GpioHandler

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
        clear_key: str = "C",
        digit_key: str = "D",
        eol_key: str = "#",
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

        # _handlers only exist to ensure that we keep a reference to the
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
            self._key_queue = KeyQueue(clear_key=clear_key, digit_key=digit_key, eol_key=eol_key)
        elif isinstance(key_queue, KeyQueue):
            self._key_queue = key_queue
        else:
            raise ValueError(f"{key_queue} is not a KeyQueue")
        self.when_pressed = self._key_queue.keypress_handler()

        # Call _fire_events once to set initial state of events
        self._fire_events(self.pin_factory.ticks(), self.is_active)

        # create the background thread to continually scan the matrix
        self._scan_thread = GPIOThread(self._scan_keyboard)
        self._scan_thread.daemon = True
        self._is_running = True
        self._scan_thread.start()
        GpioHandler.cache_handler(self._scan_thread)

    def reset(self) -> None:
        self.close()

    def close(self) -> None:
        self._is_running = False
        self._reset_pin_states()
        super().close()
        if self._key_queue:
            self._key_queue.reset()
        if self._scan_thread:
            self._scan_thread.stop()

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

    def reset_key_presses(self) -> None:
        self._key_queue.reset()
        self._keypress = self._last_keypress = None

    def wait_for_eol(self, timeout: float = 10) -> str | None:
        return self._key_queue.wait_for_eol(timeout)

    @property
    def key_presses(self) -> str:
        return self._key_queue.key_presses

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


# PCF8574T address
KEYPAD_PCF8574_ADDRESS = 0x20

# Row pins on the PCF8574T
ROW_PINS = (0, 1, 2, 3)

# Column pins on the PCF8574T
COL_PINS = (4, 5, 6, 7)


class KeyPadI2C:
    def __init__(
        self,
        i2c_address: int = KEYPAD_PCF8574_ADDRESS,
        row_pins: List[int] = ROW_PINS,
        col_pins: List[int] = COL_PINS,
        keys: List[List[str]] = DEFAULT_4X4_KEYS,
        clear_key: str = "C",
        digit_key: str = "D",
        eol_key: str = "#",
        swap_key: str = "*",
        key_queue: KeyQueue = None,
    ):
        self._i2c_address = i2c_address
        self._row_pins = row_pins
        self._col_pins = col_pins
        self._is_running = True
        self._last_value = None
        self._keypress = self._last_keypress = None
        self._keys = keys
        if key_queue is None:
            self._key_queue = KeyQueue(
                clear_key=clear_key,
                digit_key=digit_key,
                eol_key=eol_key,
                swap_key=swap_key,
            )
        elif isinstance(key_queue, KeyQueue):
            self._key_queue = key_queue
        else:
            raise ValueError(f"{key_queue} is not a KeyQueue")
        self._keypress_handler = self._key_queue.keypress_handler()

        # create the background thread to continually scan the matrix
        self._scan_thread = GPIOThread(self._scan_keyboard)
        self._scan_thread.daemon = True
        self._is_running = True
        self._scan_thread.start()
        GpioHandler.cache_handler(self._scan_thread)

    def reset(self) -> None:
        self.close()

    def close(self) -> None:
        self._is_running = False
        if self._key_queue:
            self._key_queue.reset()
        if self._scan_thread:
            self._scan_thread.stop()

    @property
    def keypress(self) -> str | None:
        return self._keypress

    @property
    def last_keypress(self) -> str | None:
        return self._last_keypress

    @property
    def key_queue(self) -> KeyQueue:
        return self._key_queue

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
        with SMBus(1) as bus:  # Use the appropriate I2C bus number
            while self._is_running is True and self._scan_thread.stopping.is_set() is False:
                key = self.read_keypad(bus)
                if key is not None:
                    self._last_keypress = self._keypress
                    self._keypress = key
                    self._keypress_handler(self)

    def read_keypad(self, bus: SMBus = None):
        if bus is None:
            bus = SMBus(1)
        """
        Reads the state of the matrix keypad. If a key is being pressed, return it
        once released. If no key is being pressed, return None.
        """
        for r, row_pin in enumerate(self._row_pins):
            bus.write_byte(self._i2c_address, 0xFF & ~(1 << row_pin))
            time.sleep(0.001)
            for c, col_pin in enumerate(self._col_pins):
                if bus.read_byte(self._i2c_address) & (1 << col_pin) == 0:
                    while bus.read_byte(self._i2c_address) & (1 << col_pin) == 0:
                        time.sleep(0.05)
                    return self._keys[r][c]
        time.sleep(0.05)
        return None


class KeyQueue:
    def __init__(
        self,
        clear_key: str = "C",
        digit_key: str = "D",
        eol_key: str = "#",
        swap_key: str = "*",
        max_length: int = 256,
    ) -> None:
        self._deque: deque[str] = deque(maxlen=max_length)
        self._clear_key = clear_key
        self._digit_key = digit_key
        self._eol_key = eol_key
        self._cv = Condition()
        self._excluded_keys = {k for k in [clear_key, digit_key, eol_key, swap_key] if k is not None}
        self._keypress_ev = Event()
        self._eol_ev = Event() if eol_key else None
        self._clear_ev = Event() if clear_key else None
        self._digit_ev = Event() if digit_key else None

    def __len__(self) -> int:
        return len(self.key_presses)

    def keypress_handler(self) -> Callable:
        def fn(keypad: Keypad) -> None:
            keypress = keypad.keypress
            if keypress:
                with self._cv:
                    # don't clear digit_ev, we need it for context
                    for ev in [self._keypress_ev, self._eol_ev, self._clear_ev]:
                        if ev:
                            ev.clear()
                    if keypress == self._clear_key:
                        self._deque.clear()
                        self._clear_ev.set()
                    elif keypress == self._digit_key:
                        self._deque.clear()
                        self._digit_ev.set()
                    elif keypress == self._eol_key:
                        self._eol_ev.set()
                    else:
                        self._deque.extend(keypress)
                    self._keypress_ev.set()
                    self._cv.notify_all()

        return fn

    __call__ = keypress_handler

    @property
    def key_presses(self) -> str:
        with self._cv:
            return "".join([c for c in self._deque if c not in self._excluded_keys])

    def processed_digit(self) -> None:
        with self._cv:
            if self._digit_ev and self._digit_ev.is_set():
                self._digit_ev.clear()
                self._deque.clear()

    def reset(self) -> None:
        with self._cv:
            self._keypress_ev.set()  # force controllers to wake up
            for ev in [self._eol_ev, self._clear_ev, self._digit_ev, self._keypress_ev]:
                if ev:
                    ev.clear()
            self._deque.clear()
            self._cv.notify_all()

    @property
    def is_eol(self) -> bool:
        return self._eol_ev.is_set() if self._eol_ev else False

    @property
    def is_clear(self) -> bool:
        return self._clear_ev.is_set() if self._clear_ev else False

    @property
    def is_digit(self) -> bool:
        return self._digit_ev.is_set() if self._digit_ev else False

    def wait_for_keypress(self, timeout: float = 10) -> str | None:
        try:
            self._keypress_ev.wait(timeout)
            if (
                self._keypress_ev.is_set() is False
                or (self._eol_ev and self._eol_ev.is_set())
                or (self._clear_ev and self._clear_ev.is_set())
                or (self._digit_ev and self._digit_ev.is_set() and len(self._deque) == 0)
            ):
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
                return self.key_presses
        return None
