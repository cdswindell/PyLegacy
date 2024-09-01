from .command_base import CommandBase
from .constants import TMCC1_COMMAND_PREFIX
from .constants import TMCC1_HALT_COMMAND


class HaltCmd(CommandBase):
    """
        Issue TMCC1 Halt command; stops all engines in motion
    """
    def __init__(self, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        CommandBase.__init__(self, baudrate, port)
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        cmd = (TMCC1_COMMAND_PREFIX.to_bytes(1, 'big') +
               TMCC1_HALT_COMMAND.to_bytes(2, 'big'))
        self._is_legacy_cmd = False

        return cmd
