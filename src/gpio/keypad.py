#!/usr/bin/env python3
import time
from typing import List

from gpiozero import Button, CompositeDevice, EventsMixin, GPIOPinMissing, PinInvalidPin, DigitalOutputDevice, event
from gpiozero.threads import GPIOThread

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

        def get_new_handler(device):
            def fire_both_events(ticks, state):
                # noinspection PyProtectedMember
                device._fire_events(ticks, device._state_to_value(state))
                self._fire_events(ticks, self.is_active)

            return fire_both_events

        # _handlers only exists to ensure that we keep a reference to the
        # generated fire_both_events handler for each Button (remember that
        # pin.when_changed only keeps a weak reference to handlers)
        self._handlers = tuple(get_new_handler(device) for device in self._cols)
        for button, handler in zip(self._cols, self._handlers):
            button.pin.when_changed = handler
        self._when_changed = None
        self._last_value = None
        self._keypress = self._last_keypress = None
        # Call _fire_events once to set initial state of events
        self._fire_events(self.pin_factory.ticks(), self.is_active)
        self._scan_thread = GPIOThread(self._scan)
        self._scan_thread.start()

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

    # @property
    # def key(self) -> str:
    #     return self._scan()

    @property
    def last_key(self) -> str | None:
        return self._last_keypress

    def _scan(self) -> None:
        while True:
            self._reset_pin_states()
            for r, row in enumerate(self._rows):
                row.on()
                try:
                    for c, col in enumerate(self._cols):
                        if col.is_active:
                            self._keypress = self._last_keypress = KEYS[(r * 4) + c]
                            while col.is_active:
                                time.sleep(0.05)
                finally:
                    row.off()
            self._keypress = None

    def _reset_pin_states(self) -> None:
        for r in self._rows:
            r.off()


Keypad.is_pressed = Keypad.is_active
Keypad.pressed_time = Keypad.active_time
Keypad.when_pressed = Keypad.when_activated
Keypad.when_released = Keypad.when_deactivated
Keypad.wait_for_press = Keypad.wait_for_active
Keypad.wait_for_release = Keypad.wait_for_inactive


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
