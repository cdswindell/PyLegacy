from gpiozero import Device, GPIODeviceClosed, HoldMixin

from src.gpio.mcp23017 import INPUT, HIGH, Mcp23017Factory


class I2CButton(Device, HoldMixin):
    def __init__(
        self,
        pin,
        i2c_address: int = 0x23,
        pull_up: bool = True,
        pin_factory=None,
    ):
        self._dio_pin = pin
        # i2c buttons use the MCP 23017 i2c dio board, which supports 16 pins and interrupts
        self._mcp_23017 = Mcp23017Factory.build(address=i2c_address, pin=pin)
        self._mcp_23017.set_pin_mode(pin, INPUT)
        self._mcp_23017.set_pull_up(pin, pull_up)
        super().__init__(pin_factory=pin_factory)

        # _handlers only exists to ensure that we keep a reference to the
        # generated fire_both_events handler for each Button (remember that
        # pin.when_changed only keeps a weak reference to handlers)
        def get_new_handler(device):
            def fire_both_events(ticks, state):
                # noinspection PyProtectedMember
                device._fire_events(ticks, device._state_to_value(state))
                self._fire_events(ticks, self.is_active)

            return fire_both_events

        self._handlers = (get_new_handler(self), self)
        self.when_changed = self._handlers[0]

    def close(self) -> None:
        super().close()
        self._mcp_23017 = None

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
    def closed(self) -> bool:
        return self._mcp_23017 is None
