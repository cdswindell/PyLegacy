from .tmcc1_command import TMCC1Command
from ..constants import SwitchState, DEFAULT_BAUDRATE, DEFAULT_PORT, TMCC1_SWITCH_SET_ADDRESS_COMMAND
from ..constants import TMCC1_SWITCH_THROUGH_COMMAND, TMCC1_SWITCH_OUT_COMMAND


class SwitchCmd(TMCC1Command):
    def __init__(self, switch: int,
                 state: SwitchState = SwitchState.THROUGH,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if switch < 1 or switch > 99:
            raise ValueError("Switch must be between 1 and 99")
        super().__init__(baudrate, port)
        self._switch = switch
        self._state = state
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        if self._state == SwitchState.OUT:
            cmd = TMCC1_SWITCH_OUT_COMMAND
        elif self._state == SwitchState.SET_ADDRESS:
            cmd = TMCC1_SWITCH_SET_ADDRESS_COMMAND
        else:
            cmd = TMCC1_SWITCH_THROUGH_COMMAND
        return self.command_prefix + self._encode_address(self._switch, cmd)
