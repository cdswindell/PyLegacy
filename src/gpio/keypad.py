#!/usr/bin/env python3
from typing import List

from gpiozero import Button, LED, CompositeDevice
import time

KEYS = ["1", "2", "3", "A", "4", "5", "6", "B", "7", "8", "9", "C", "*", "0", "#", "D"]


class Keypad(CompositeDevice):
    def __init__(
        self,
        row_pins: List[int | str],
        column_pins: List[int | str],
        bounce_time: float = None,
        pin_factory=None,
    ):
        devices = []
        self._rows = []
        for pin in row_pins:
            dev = LED(pin, pin_factory=pin_factory)
            self._rows.append(dev)
            devices.append(dev)
        self._cols = []
        for pin in column_pins:
            dev = Button(pin, pull_up=False, bounce_time=bounce_time, pin_factory=pin_factory)
            self._cols.append(dev)
            devices.append(dev)
        super().__init__(*devices, pin_factory=pin_factory)

    @property
    def key(self) -> str:
        return self._scan_keys()

    def _scan_keys(self) -> str | None:
        r = 0
        for row in self._rows:
            row.on()
            c = 0
            try:
                for col in self._cols:
                    if col.is_active:
                        while col.is_active:
                            time.sleep(0.05)
                        return KEYS[(r * 4) + c]
                    else:
                        c += 1
            finally:
                row.off()
            r += 1
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
