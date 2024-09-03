from src.protocol.tmcc1.tmcc1_command import TMCC1Command
from src.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from src.protocol.constants import TMCC1_HALT_COMMAND


class HaltCmd(TMCC1Command):
    """
        Issue TMCC1 Halt command; stops all engines in motion
    """
    def __init__(self, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT) -> None:
        super().__init__(DEFAULT_ADDRESS, baudrate, port)
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        return self.command_prefix + self._encode_command(TMCC1_HALT_COMMAND)
