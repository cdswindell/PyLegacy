from gpiozero import Button

from src.protocol.constants import OptionEnum, DEFAULT_BAUDRATE, DEFAULT_PORT
from src.protocol.constants import CommandScope, TMCC1Enum, TMCC2Enum, TMCC2CommandPrefix
from src.protocol.tmcc2.tmcc2_command import TMCC2Command


class GpioHandler:
    @classmethod
    def when_button_pressed(cls,
                            pin: int | str,
                            address: int,
                            command: OptionEnum,
                            data: int = 0,
                            scope: CommandScope = CommandScope.ENGINE,
                            baudrate: int = DEFAULT_BAUDRATE,
                            port: str = DEFAULT_PORT
                            ) -> Button:
        # create the button object we will associate an action with
        button = Button(pin)

        # create a command function to fire when button pressed
        # this queues the tmcc/tmcc2 command to the buffer
        if isinstance(command, TMCC2Enum):
            tmcc_scope = TMCC2CommandPrefix(scope.name)
            func = TMCC2Command.send_func(address,
                                          command,
                                          data,
                                          scope=tmcc_scope,
                                          baudrate=baudrate,
                                          port=port)
        button.when_pressed = func
        return button
