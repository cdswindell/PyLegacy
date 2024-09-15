from .tmcc1_command import TMCC1Command
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from src.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandDef


class HaltCmd(TMCC1Command):
    """
        Issue TMCC1 Halt command; stops all engines in motion
    """
    def __init__(self, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT) -> None:
        req = CommandReq(TMCC1HaltCommandDef.HALT)
        super().__init__(TMCC1HaltCommandDef.HALT, req, DEFAULT_ADDRESS, 0, None, baudrate, port)
        self._command = self._build_command()
