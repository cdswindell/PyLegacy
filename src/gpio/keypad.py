#!/usr/bin/env python3
from typing import List

from gpiozero import Button, CompositeDevice, EventsMixin, GPIOPinMissing, PinInvalidPin, DigitalOutputDevice
import time

KEYS = ["1", "2", "3", "A", "4", "5", "6", "B", "7", "8", "9", "C", "*", "0", "#", "D"]


class Keypad(EventsMixin, CompositeDevice):
    def __init__(
        self,
        row_pins: List[int | str],
        column_pins: List[int | str],
        bounce_time: float = None,
        pin_factory=None,
    ):
        if len(row_pins) < 4:
            raise GPIOPinMissing("Need exactly 4 Row pins")
        if len(row_pins) > 4:
            raise PinInvalidPin("Need exactly 4 Row pins")
        if len(column_pins) < 4:
            raise GPIOPinMissing("Need exactly 4 Column pins")
        if len(column_pins) > 4:
            raise PinInvalidPin("Need exactly 4 Column pins")
        devices = []
        self._rows = []
        for pin in row_pins:
            dev = DigitalOutputDevice(pin, pin_factory=pin_factory)
            self._rows.append(dev)
            devices.append(dev)
        self._cols = []
        for pin in column_pins:
            dev = Button(pin, pull_up=False, bounce_time=bounce_time, hold_repeat=False, pin_factory=pin_factory)
            self._cols.append(dev)
            devices.append(dev)
        super().__init__(*devices, pin_factory=pin_factory)
        if len(self) == 0:
            raise GPIOPinMissing("No pins given")
        self._last_keypress = None

    @property
    def key(self) -> str:
        return self._scan_keys()

    def _scan_keys(self) -> str | None:
        for r, row in enumerate(self._rows):
            row.on()
            try:
                for c, col in enumerate(self._cols):
                    if col.is_active:
                        self._last_keypress = KEYS[(r * 4) + c]
                        while col.is_active:
                            time.sleep(0.05)
                        return self._last_keypress
            finally:
                row.off()
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
