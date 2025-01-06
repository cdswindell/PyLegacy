from threading import Lock

from gpiozero import Device, GPIODeviceClosed, SourceMixin

from src.gpio.mcp23017 import Mcp23017Factory, OUTPUT


class I2CLED(Device, SourceMixin):
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
        # self._stop_blink()
        self.value = 1

    def off(self):
        # self._stop_blink()
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
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C LED is closed or uninitialized")
        return self._dio_pin

    @property
    def closed(self) -> bool:
        return self._mcp_23017 is None


I2CLED.is_lit = I2CLED.is_active
