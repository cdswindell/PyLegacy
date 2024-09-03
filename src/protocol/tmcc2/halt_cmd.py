from .tmcc2_command import TMCC2Command
from ..constants import TMCC2CommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from ..constants import TMCC2_HALT_COMMAND


class HaltCmd(TMCC2Command):
    """
        Issue TMCC2 Halt command; stops all engines in motion
    """
    def __init__(self,
                 scope: TMCC2CommandScope = TMCC2CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        super().__init__(scope, DEFAULT_ADDRESS, baudrate, port)
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        return self.command_prefix + self._encode_address(TMCC2_HALT_COMMAND)
