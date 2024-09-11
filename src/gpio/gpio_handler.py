from gpiozero import Button

from src.protocol.command_req import CommandReq
from src.protocol.constants import CommandDefEnum, DEFAULT_BAUDRATE, DEFAULT_PORT
from src.protocol.constants import CommandScope


class GpioHandler:
    @classmethod
    def when_button_pressed(cls,
                            pin: int | str,
                            command: CommandReq | CommandDefEnum,
                            address: int | None = None,
                            data: int = 0,
                            scope: CommandScope = None,
                            baudrate: int = DEFAULT_BAUDRATE,
                            port: str = DEFAULT_PORT
                            ) -> Button:
        # create the button object we will associate an action with
        button = Button(pin)

        # if command is actually a CommandDefEnum, build a CommandReq
        if isinstance(command, CommandDefEnum):
            command = CommandReq(command, address=address, data=data, scope=scope)

        # create a command function to fire when button pressed
        button.when_pressed = command.as_action(baudrate=baudrate, port=port)
        return button

    @classmethod
    def when_button_held(cls,
                         pin: int | str,
                         command: CommandReq | CommandDefEnum,
                         address: int = None,
                         data: int = 0,
                         scope: CommandScope = None,
                         frequency: float = 1,
                         baudrate: int = DEFAULT_BAUDRATE,
                         port: str = DEFAULT_PORT
                         ) -> Button:
        # create the button object we will associate an action with
        button = Button(pin)

        # if command is actually a CommandDefEnum, build a CommandReq
        if isinstance(command, CommandDefEnum):
            command = CommandReq(command, address=address, data=data, scope=scope)

        # create a command function to fire when button held
        button.when_held = command.as_action(baudrate=baudrate, port=port)
        button.hold_repeat = True
        button.hold_time = frequency
        return button
