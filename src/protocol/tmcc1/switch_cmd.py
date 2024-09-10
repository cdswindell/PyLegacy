from .tmcc1_command import TMCC1Command
from ..constants import TMCC1SwitchState, DEFAULT_BAUDRATE, DEFAULT_PORT


class SwitchCmd(TMCC1Command):
    def __init__(self, switch: int,
                 state: TMCC1SwitchState = TMCC1SwitchState.THROUGH,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if switch < 1 or switch > 99:
            raise ValueError("Switch must be between 1 and 99")
        super().__init__(switch, baudrate, port)
        self._state = state
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        return self.command_prefix + self._encode_address(self._state.value.command)
