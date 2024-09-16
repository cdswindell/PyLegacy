from .tmcc1_command import TMCC1Command
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from src.protocol.tmcc1.tmcc1_constants import TMCC1SwitchState


class SwitchCmd(TMCC1Command):
    def __init__(self, switch: int,
                 state: TMCC1SwitchState = TMCC1SwitchState.THROUGH,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT,
                 server: str = None) -> None:
        if switch < 1 or switch > 99:
            raise ValueError("Switch must be between 1 and 99")
        req = CommandReq(state, switch)
        super().__init__(state, req, switch, 0, None, baudrate, port, server)
        self._command = self._build_command()
