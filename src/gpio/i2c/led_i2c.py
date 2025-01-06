from threading import Lock
from itertools import repeat

from gpiozero import Device, GPIODeviceClosed, SourceMixin
from gpiozero.threads import GPIOThread

from .mcp23017 import Mcp23017Factory, OUTPUT


class LEDI2C(Device, SourceMixin):
    def __init__(
        self,
        pin,
        i2c_address: int = 0x23,
        initial_value: bool = False,
        pin_factory=None,
    ):
        # i2c buttons use the MCP 23017 i2c dio board, which supports 16 pins and interrupts
        self._dio_pin = pin
        self._mcp_23017 = Mcp23017Factory.build(
            address=i2c_address,
            pin=pin,
            client=self,
        )
        # initialize the gpiozero device
        super().__init__(pin_factory=pin_factory)
        self._controller = None
        self._blink_thread = None
        self._lock = Lock()

        # configure the Mcp23017 pin to the appropriate mode
        self._mcp_23017.set_pin_mode(pin, OUTPUT)
        if initial_value is not None:
            self.value = 1 if initial_value else 0

    def __repr__(self):
        # noinspection PyBroadException
        try:
            return f"<{self.__class__.__name__} object on pin " f"is_active={self.is_active}>"
        except Exception:
            return super().__repr__()

    def close(self) -> None:
        try:
            # in edge cases where constructor fails, _mcp_23017 property may not exist
            if hasattr(self, "_mcp_23017") and self._mcp_23017 is not None:
                self._mcp_23017.disable_interrupt(self._dio_pin)
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
        return self._mcp_23017.value(self._dio_pin)

    @value.setter
    def value(self, value: int) -> None:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
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

    @property
    def pin(self) -> int:
        return self._dio_pin

    # noinspection PyMethodOverriding
    def source(self, value):
        self._stop_blink()
        super().source(value)

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
