from .tmcc2_command import TMCC2Command
from ..constants import TMCC2CommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT
from ..constants import LEGACY_HALT_COMMAND


class HaltCmd(TMCC2Command):
    """
        Issue TMCC2 Halt command; stops all engines in motion
    """
    def __init__(self, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT) -> None:
        super().__init__(TMCC2CommandScope.ENGINE, baudrate, port)
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        return self.command_prefix + self._encode_address(0, LEGACY_HALT_COMMAND)
