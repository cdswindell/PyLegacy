from threading import RLock
from typing import Tuple

from gpiozero import GPIODeviceClosed, HoldMixin

from .i2c_device import I2CDevice
from .mcp23017 import INPUT, HIGH, Mcp23017Factory


class ButtonI2C(I2CDevice, HoldMixin):
    def __init__(
        self,
        pin: int | Tuple[int, int] | Tuple[int, int, int],
        i2c_address: int = 0x23,
        pull_up: bool = True,
        bounce_time: float = None,
        hold_time: float = 1,
        hold_repeat: bool = False,
        interrupt_pin: int | str = None,
        pin_factory=None,
    ):
        self._lock = RLock()
        # i2c buttons use the MCP 23017 i2c dio board, which supports 16 pins and interrupts
        if isinstance(pin, tuple):
            if len(pin) > 1 and pin[1]:
                interrupt_pin = pin[1]
            if len(pin) > 2 and pin[2]:
                i2c_address = pin[2]
            if len(pin) > 3 and pin[3] in {True, False}:
                pull_up = pin[3]
            pin = pin[0]
        self._dio_pin = pin
        self._mcp_23017 = Mcp23017Factory.build(
            address=i2c_address,
            pin=pin,
            interrupt_pin=interrupt_pin,
            client=self,
        )
        # initialize the gpiozero device
        super().__init__(pin_factory=pin_factory)

        # configure the Mcp23017 pin to the appropriate mode
        self._mcp_23017.set_pin_mode(pin, INPUT)
        self._mcp_23017.set_pull_up(pin, pull_up)
        if interrupt_pin is not None:
            self._mcp_23017.enable_interrupt(pin)
        self._interrupt_pin = interrupt_pin
        self._bounce_time = bounce_time
        self.hold_time = hold_time if hold_time is not None and hold_time >= 0 else 1
        self.hold_repeat = hold_repeat

        # Call _fire_events once to set initial state of events
        self._fire_events(self.pin_factory.ticks(), self.is_active)

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

    @property
    def pin(self) -> int:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C Button is closed or uninitialized")
        return self._dio_pin

    def close(self) -> None:
        with self._lock:
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
    def bounce_time(self) -> float:
        return self._bounce_time

    @bounce_time.setter
    def bounce_time(self, value: float) -> None:
        if value is not None and value < 0:
            raise ValueError("bounce_time must be None or >= 0")
        self._bounce_time = value

    def _signal_event(self, active: bool) -> None:
        self._fire_events(self.pin_factory.ticks(), active)

    @property
    def i2c_address(self) -> int:
        return self._mcp_23017.address

    @property
    def value(self) -> int:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C Button is closed or uninitialized")
        if self.pull_up:
            return 0 if self._mcp_23017.digital_read(self._dio_pin) == HIGH else 1
        else:
            return 1 if self._mcp_23017.digital_read(self._dio_pin) == HIGH else 0

    @property
    def is_active(self) -> bool:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C Button is closed or uninitialized")
        return self.value == 1

    @property
    def pull_up(self) -> bool:
        if self._mcp_23017 is None:
            raise GPIODeviceClosed("I2C Button is closed or uninitialized")
        return self._mcp_23017.get_pull_up(self._dio_pin)


ButtonI2C.is_pressed = ButtonI2C.is_active
ButtonI2C.pressed_time = ButtonI2C.active_time
ButtonI2C.when_pressed = ButtonI2C.when_activated
ButtonI2C.when_released = ButtonI2C.when_deactivated
ButtonI2C.wait_for_press = ButtonI2C.wait_for_active
ButtonI2C.wait_for_release = ButtonI2C.wait_for_inactive
