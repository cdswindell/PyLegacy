import math
from threading import Thread
from typing import Tuple, Callable

from gpiozero import Button, LED, MCP3008, Device

from src.comm.comm_buffer import CommBuffer
from src.protocol.command_req import CommandReq
from src.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from src.protocol.command_def import CommandDefEnum
from src.protocol.constants import CommandScope

DEFAULT_BOUNCE_TIME: float = 0.05  # button debounce threshold
DEFAULT_VARIANCE: float = 0.001  # pot difference variance


class PotHandler(Thread):
    def __init__(self,
                 command: CommandReq,
                 buffer: CommBuffer,
                 channel: int = 0) -> None:
        super().__init__(daemon=True)
        self._pot = MCP3008(channel=channel)
        self._command = command
        self._buffer = buffer
        self._last_value = 0.0
        self._action = command.as_action()
        if command.is_tmcc1:
            self._interp = self.make_interpolator(31)
        else:
            self._interp = self.make_interpolator(199)
        self.start()

    @property
    def pot(self) -> MCP3008:
        return self._pot

    def run(self) -> None:
        while True:
            value = self._pot.value
            if math.fabs(self._last_value - value) < DEFAULT_VARIANCE:
                continue
            self._last_value = value
            value = self._interp(value)
            print(f"New Speed: {value}")
            self._action(new_data=value)

    @staticmethod
    def make_interpolator(to_max: int,
                          to_min: int = 0,
                          from_min: float = 0.0,
                          from_max: float = 1.0) -> Callable:
        # Figure out how 'wide' each range is
        from_span = from_max - from_min
        to_span = to_max - to_min

        # Compute the scale factor between left and right values
        scale_factor = float(to_span) / float(from_span)

        # create interpolation function using pre-calculated scaleFactor
        def interp_fn(value) -> int:
            return int(round(to_min + (value - from_min) * scale_factor))

        return interp_fn


class GpioHandler:
    GPIO_DEVICE_CACHE = set()

    @classmethod
    def when_button_pressed(cls,
                            pin: int | str,
                            command: CommandReq | CommandDefEnum,
                            address: int = DEFAULT_ADDRESS,
                            data: int = 0,
                            scope: CommandScope = None,
                            led_pin: int | str = None,
                            baudrate: int = DEFAULT_BAUDRATE,
                            port: str | int = DEFAULT_PORT,
                            server: str = None
                            ) -> Button:

        # Use helper method to construct objects
        command, button, led = cls._make_button(pin, command, address, data, scope, led_pin)

        # create a command function to fire when button pressed
        button.when_pressed = command.as_action(baudrate=baudrate, port=port, server=server)
        return button

    @classmethod
    def when_button_held(cls,
                         pin: int | str,
                         command: CommandReq | CommandDefEnum,
                         address: int = DEFAULT_ADDRESS,
                         data: int = 0,
                         scope: CommandScope = None,
                         frequency: float = 1,
                         led_pin: int | str = None,
                         baudrate: int = DEFAULT_BAUDRATE,
                         port: str | int = DEFAULT_PORT,
                         server: str = None
                         ) -> Button:

        # Use helper method to construct objects
        command, button, led = cls._make_button(pin, command, address, data, scope, led_pin)

        # create a command function to fire when button held
        button.when_held = command.as_action(baudrate=baudrate, port=port, server=server)
        button.hold_repeat = True
        button.hold_time = frequency
        return button

    @classmethod
    def when_toggle_switch(cls,
                           off_pin: int | str,
                           on_pin: int | str,
                           off_command: CommandReq,
                           on_command: CommandReq,
                           led_pin: int | str = None,
                           baudrate: int = DEFAULT_BAUDRATE,
                           port: str | int = DEFAULT_PORT,
                           server: str = None
                           ) -> Tuple[Button, Button, LED]:
        # create a LED, if requested. It is turned on by pressing the
        # ON button, and turned off by pressing the OFF button
        if led_pin is not None and led_pin != 0:
            led = LED(led_pin)
        else:
            led = None

        # create the off and on buttons
        off_button = Button(off_pin, bounce_time=DEFAULT_BOUNCE_TIME)
        on_button = Button(on_pin, bounce_time=DEFAULT_BOUNCE_TIME)

        # bind them to functions; we need to wrap the functions if we're using a LED
        off_action = off_command.as_action(baudrate=baudrate, port=port, server=server)
        on_action = on_command.as_action(baudrate=baudrate, port=port, server=server)
        if led is not None:
            off_button.when_pressed = cls._with_off_action(off_action, led)
            on_button.when_pressed = cls._with_on_action(on_action, led)
        else:
            off_button.when_pressed = off_action
            on_button.when_pressed = on_action

        cls._cache_device(off_button)
        cls._cache_device(on_button)
        if led is not None:
            cls._cache_device(led)
        return off_button, on_button, led

    @classmethod
    def when_toggle_button_pressed(cls,
                                   pin: int | str,
                                   command: CommandReq | CommandDefEnum,
                                   address: int = DEFAULT_ADDRESS,
                                   data: int = 0,
                                   scope: CommandScope = None,
                                   led_pin: int | str = None,
                                   initial_state: bool = False,  # off
                                   baudrate: int = DEFAULT_BAUDRATE,
                                   port: str | int = DEFAULT_PORT,
                                   server: str = None
                                   ) -> Button | tuple[Button, LED]:

        # Use helper method to construct objects
        command, button, led = cls._make_button(pin, command, address, data, scope, led_pin)

        # create a command function to fire when button pressed
        action = command.as_action(baudrate=baudrate, port=port, server=server)
        if led_pin is not None and led_pin != 0:
            button.when_pressed = cls._with_toggle_action(action, led)
            led.source = None  # want led to stay lit when button pressed
            if initial_state:
                led.on()
            else:
                led.off()
            return button, led
        else:
            button.when_pressed = action
            return button

    @classmethod
    def when_pot(cls,
                 command: CommandReq | CommandDefEnum,
                 address: int = DEFAULT_ADDRESS,
                 scope: CommandScope = None,
                 channel: int = 0,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str | int = DEFAULT_PORT,
                 server: str = None
                 ) -> PotHandler:
        if isinstance(command, CommandDefEnum):
            command = CommandReq.build_request(command, address, 0, scope)
        buffer = CommBuffer.build(baudrate, port, server)
        knob = PotHandler(command, buffer, channel)
        cls._cache_device(knob.pot)
        return knob

    @classmethod
    def reset_all(cls) -> None:
        for device in cls.GPIO_DEVICE_CACHE:
            device.close()
        cls.GPIO_DEVICE_CACHE = set()

    @classmethod
    def release_device(cls, device: Device) -> None:
        cls._release_device(device)

    @classmethod
    def _cache_device(cls, device: Device) -> None:
        """
            Keep devices around after creation so they remain in scope
        """
        cls.GPIO_DEVICE_CACHE.add(device)

    @classmethod
    def _release_device(cls, device: Device) -> None:
        device.close()
        cls.GPIO_DEVICE_CACHE.remove(device)

    @classmethod
    def _make_button(cls,
                     pin: int | str,
                     command: CommandReq | CommandDefEnum,
                     address: int,
                     data: int,
                     scope: CommandScope,
                     led_pin: int | str) -> Tuple[CommandReq, Button, LED]:
        # if command is actually a CommandDefEnum, build a CommandReq
        if isinstance(command, CommandDefEnum):
            command = CommandReq(command, address=address, data=data, scope=scope)

        # create the button object we will associate an action with
        button = Button(pin, bounce_time=DEFAULT_BOUNCE_TIME)
        cls._cache_device(button)

        # create a LED, if asked, and tie its source to the button
        if led_pin is not None and led_pin != 0:
            led = LED(led_pin)
            led.source = button
            cls._cache_device(led)
        else:
            led = None
        return command, button, led

    @classmethod
    def _with_toggle_action(cls, action: Callable, led: LED) -> Callable:
        def toggle_action() -> None:
            action()
            if led.value:
                led.off()
            else:
                led.on()

        return toggle_action

    @classmethod
    def _with_off_action(cls, action: Callable, led: LED) -> Callable:
        def off_action() -> None:
            action()
            led.off()

        return off_action

    @classmethod
    def _with_on_action(cls, action: Callable, led: LED) -> Callable:
        def on_action() -> None:
            action()
            led.on()

        return on_action
