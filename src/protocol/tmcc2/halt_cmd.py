from .tmcc2_command import TMCC2Command
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from ..tmcc2_constants import TMCC2HaltCommandDef


class HaltCmd(TMCC2Command):
    """
        Issue TMCC2 Halt command; stops all engines in motion
    """
    def __init__(self,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        req = CommandReq(TMCC2HaltCommandDef.HALT, DEFAULT_ADDRESS)
        super().__init__(TMCC2HaltCommandDef.HALT, req, DEFAULT_ADDRESS, 0, None, baudrate, port)
        self._command = self._build_command()
