from .tmcc1_command import TMCC1Command
from .tmcc1_constants import TMCC1HaltCommandEnum

from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS


class HaltCmd(TMCC1Command):
    """
    Issue TMCC1 Halt command; stops all engines in motion
    """

    def __init__(self, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT, server: str = None) -> None:
        req = CommandReq(TMCC1HaltCommandEnum.HALT)
        super().__init__(TMCC1HaltCommandEnum.HALT, req, DEFAULT_ADDRESS, 0, None, baudrate, port, server)
        self._command = self._build_command()
