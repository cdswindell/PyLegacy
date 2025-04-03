from itertools import repeat
from threading import RLock
from typing import Tuple

from gpiozero import GPIODeviceClosed, SourceMixin
from gpiozero.threads import GPIOThread

from .i2c_device import I2CDevice
from .mcp23017 import OUTPUT, Mcp23017Factory


class LEDI2C(I2CDevice, SourceMixin):
    def __init__(
        self,
        pin: int | Tuple[int, int],
        i2c_address: int = 0x23,
        cathode: bool = True,
        initial_value: bool = False,
        pin_factory=None,
    ):
        # i2c buttons use the MCP 23017 i2c dio board, which supports 16 pins and interrupts
        if isinstance(pin, tuple):
            if len(pin) > 1 and pin[1]:
                i2c_address = pin[1]
            if len(pin) > 2 and pin[2] in {True, False}:
                cathode = pin[2]
            if len(pin) > 3 and pin[3] in {True, False}:
                initial_value = pin[3]
            if len(pin) > 0 and pin[0] in range(16):
                pin = pin[0]
            else:
                raise ValueError(f"Invalid pin specifier: {pin}")
        self._dio_pin = pin
        self._cathode = cathode
        self._mcp_23017 = Mcp23017Factory.build(
            address=i2c_address,
            pin=pin,
            client=self,
        )
        # initialize the gpiozero device
        super().__init__(pin_factory=pin_factory)
        self.source_delay = 0.2
        self._controller = None
        self._blink_thread = None
        self._lock = RLock()

        # configure the Mcp23017 pin to the appropriate mode
        self._mcp_23017.set_pin_mode(pin, OUTPUT)

        # If cathode is connected to GPIO,
        if cathode is False:
            self._mcp_23017.set_value(pin, 1)  #  turns the pin off
        if initial_value is not None:
            self.value = 1 if initial_value is True else 0

    def __repr__(self):
        # noinspection PyBroadException
        try:
            return f"<{self.__class__.__name__} object on pin {self.pin} is_active={self.is_active}>"
        except Exception:
            return super().__repr__()

    def _signal_event(self, active: bool) -> None:
        # Noop for LEDs
        pass

    @property
    def bounce_time(self) -> float | None:
        return None

    @property
    def pin(self) -> int:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
        return self._dio_pin

    def close(self) -> None:
        with self._lock:
            try:
                self._stop_blink()
                # in edge cases where constructor fails, _mcp_23017 property may not exist
                if hasattr(self, "_mcp_23017") and self._mcp_23017 is not None:
                    self.value = 0
                    self.source = None
                    self._mcp_23017.deregister_client(self)
                    Mcp23017Factory.close(self._mcp_23017, self._dio_pin)
                self._mcp_23017 = None
            finally:
                super().close()

    @property
    def closed(self) -> bool:
        return self._mcp_23017 is None

    @property
    def i2c_address(self) -> int:
        return self._mcp_23017.address

    @property
    def value(self) -> int:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
        value = self._mcp_23017.value(self._dio_pin)
        if self._cathode is False:
            value = 1 if value == 0 else 0
        return value

    @value.setter
    def value(self, value: int) -> None:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
        if self._cathode is False:
            value = 1 if value == 0 else 0
        self._mcp_23017.set_value(self._dio_pin, value)

    def on(self):
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
        self._stop_blink()
        self.value = 1

    def off(self):
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
        self._stop_blink()
        self.value = 0

    def toggle(self):
        """
        Reverse the state of the device. If it's on, turn it off; if it's off,
        turn it on.
        """
        with self._lock:
            if self.is_active:
                self.off()
            else:
                self.on()

    @property
    def is_active(self) -> bool:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
        return self.value == 1

    @SourceMixin.source.setter  # override setter
    def source(self, value) -> None:
        with self._lock:
            if self._mcp_23017 is None:
                raise GPIODeviceClosed("I2C LED is closed or uninitialized")
            self._stop_blink()
            SourceMixin.source.fset(self, value)

    def blink(self, on_time=1, off_time=1, n=None, background=True):
        """
        Make the device turn on and off repeatedly.

        :param float on_time:
            Number of seconds on. Defaults to 1 second.

        :param float off_time:
            Number of seconds off. Defaults to 1 second.

        :type n: int or None
        :param n:
            Number of times to blink; :data:`None` (the default) means forever.

        :param bool background:
            If :data:`True` (the default), start a background thread to
            continue blinking and return immediately. If :data:`False`, only
            return when the blink is finished (warning: the default value of
            *n* will result in this method never returning).
        """
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
        self.source = None
        self._stop_blink()
        self._blink_thread = GPIOThread(self._blink_device, (on_time, off_time, n))
        self._blink_thread.start()
        if not background:
            self._blink_thread.join()
            self._blink_thread = None

    # noinspection PyProtectedMember
    def _stop_blink(self):
        if getattr(self, "_controller", None):
            self._controller._stop_blink(self)
        self._controller = None
        if getattr(self, "_blink_thread", None):
            self._blink_thread.stop()
        self._blink_thread = None

    def _blink_device(self, on_time, off_time, n):
        iterable = repeat(0) if n is None else repeat(0, n)
        for _ in iterable:
            self.value = 1
            if self._blink_thread.stopping.wait(on_time):
                break
            self.value = 0
            if self._blink_thread.stopping.wait(off_time):
                break


LEDI2C.is_lit = LEDI2C.is_active
