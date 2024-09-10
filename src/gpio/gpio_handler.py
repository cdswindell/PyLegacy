from gpiozero import Button

from src.protocol.command_base import CommandBase
from src.protocol.constants import OptionEnum, DEFAULT_BAUDRATE, DEFAULT_PORT
from src.protocol.constants import CommandScope


class GpioHandler:
    @classmethod
    def when_button_pressed(cls,
                            pin: int | str,
                            address: int,
                            command: OptionEnum,
                            data: int = 0,
                            scope: CommandScope = None,
                            baudrate: int = DEFAULT_BAUDRATE,
                            port: str = DEFAULT_PORT
                            ) -> Button:
        # create the button object we will associate an action with
        button = Button(pin)

        # create a command function to fire when button pressed
        # this queues the tmcc/tmcc2 command to the buffer
        func = CommandBase.send_func(address,
                                     command,
                                     data,
                                     scope,
                                     baudrate=baudrate,
                                     port=port)

        button.when_pressed = func
        return button
