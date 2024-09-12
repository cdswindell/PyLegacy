from .tmcc1_command import TMCC1Command
from ..command_req import CommandReq
from ..constants import TMCC1SwitchState, DEFAULT_BAUDRATE, DEFAULT_PORT


class SwitchCmd(TMCC1Command):
    def __init__(self, switch: int,
                 state: TMCC1SwitchState = TMCC1SwitchState.THROUGH,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if switch < 1 or switch > 99:
            raise ValueError("Switch must be between 1 and 99")
        req = CommandReq(state, switch)
        super().__init__(state, req, switch, 0, None, baudrate, port)
        self._command = self._build_command()
