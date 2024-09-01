from .command_base import TMCC1Command
from .constants import TMCC1_COMMAND_PREFIX, DEFAULT_BAUDRATE, DEFAULT_PORT
from .constants import TMCC1_HALT_COMMAND


class HaltCmd(TMCC1Command):
    """
        Issue TMCC1 Halt command; stops all engines in motion
    """
    def __init__(self, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT) -> None:
        TMCC1Command.__init__(self, baudrate, port)
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        return TMCC1_COMMAND_PREFIX + self._encode_command(TMCC1_HALT_COMMAND)
