from typing import Tuple, Callable

from gpiozero import Button, LED, GPIODevice

from src.protocol.command_req import CommandReq
from src.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from src.protocol.command_def import CommandDefEnum
from src.protocol.constants import CommandScope

DEFAULT_BOUNCE_TIME: float = 0.05


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
                            port: str = DEFAULT_PORT | int,
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
                         port: str = DEFAULT_PORT,
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
                           port: str = DEFAULT_PORT,
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
    def reset_all(cls) -> None:
        for device in cls.GPIO_DEVICE_CACHE:
            device.close()
        cls.GPIO_DEVICE_CACHE = set()

    @classmethod
    def release_device(cls, device: GPIODevice) -> None:
        cls._release_device(device)

    @classmethod
    def _cache_device(cls, device: GPIODevice) -> None:
        """
            Keep devices around after creation so they remain in scope
        """
        cls.GPIO_DEVICE_CACHE.add(device)

    @classmethod
    def _release_device(cls, device: GPIODevice) -> None:
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
