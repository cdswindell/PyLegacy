from gpiozero import Device, GPIODeviceClosed, HoldMixin

from src.gpio.mcp23017 import INPUT, HIGH, Mcp23017Factory


class I2CButton(Device, HoldMixin):
    def __init__(
        self,
        pin,
        i2c_address: int = 0x23,
        pull_up: bool = True,
        interrupt_pin: int | str = None,
        pin_factory=None,
    ):
        self._dio_pin = pin
        # i2c buttons use the MCP 23017 i2c dio board, which supports 16 pins and interrupts
        self._mcp_23017 = Mcp23017Factory.build(
            address=i2c_address,
            pin=pin,
            interrupt_pin=interrupt_pin,
            client=self,
        )
        self._mcp_23017.set_pin_mode(pin, INPUT)
        self._mcp_23017.set_pull_up(pin, pull_up)
        if interrupt_pin is not None:
            self._mcp_23017.set_interrupt(pin, True)
        self._interrupt_pin = interrupt_pin
        super().__init__(pin_factory=pin_factory)

    def __repr__(self):
        # noinspection PyBroadException
        try:
            return (
                f"<{self.__class__.__name__} object on pin "
                f"{self.pin!r}, pull_up={self.pull_up}, "
                f"is_active={self.is_active}>"
            )
        except Exception:
            return super().__repr__()

    def close(self) -> None:
        if self._mcp_23017 is not None:
            self._mcp_23017.set_interrupt(self._dio_pin, False)
            self._mcp_23017.deregister_client(self)
            Mcp23017Factory.close(self._mcp_23017, self._dio_pin)
        self._mcp_23017 = None
        super().close()

    @property
    def i2c_address(self) -> int:
        return self._mcp_23017.address

    @property
    def value(self) -> int:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C Button is closed or uninitialized")
        return 0 if self._mcp_23017.digital_read(self._dio_pin) == HIGH else 1

    @property
    def is_active(self) -> bool:
        return self.value == 1

    @property
    def pin(self) -> int:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C Button is closed or uninitialized")
        return self._dio_pin

    @property
    def pull_up(self) -> bool:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C Button is closed or uninitialized")
        return self._mcp_23017.get_pull_up(self._dio_pin)

    @property
    def closed(self) -> bool:
        return self._mcp_23017 is None
