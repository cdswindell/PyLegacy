from .command_base import TMCC1Command
from .constants import SwitchState, DEFAULT_BAUDRATE, DEFAULT_PORT
from .constants import TMCC1_COMMAND_PREFIX
from .constants import TMCC1_SWITCH_THROUGH_COMMAND
from .constants import TMCC1_SWITCH_OUT_COMMAND


class SwitchCmd(TMCC1Command):
    def __init__(self, switch: int,
                 state: SwitchState = SwitchState.THROUGH,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if switch < 1 or switch > 99:
            raise ValueError("Switch must be between 1 and 99")
        TMCC1Command.__init__(self, baudrate, port)
        self._switch = switch
        self._state = state
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        if self._state == SwitchState.OUT:
            return TMCC1_COMMAND_PREFIX + self._encode_address(self._switch, TMCC1_SWITCH_OUT_COMMAND)
        else:
            return TMCC1_COMMAND_PREFIX + self._encode_address(self._switch, TMCC1_SWITCH_THROUGH_COMMAND)
