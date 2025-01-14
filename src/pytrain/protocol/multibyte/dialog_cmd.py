from .multibyte_constants import TMCC2RailSoundsDialogControl
from ..tmcc2.tmcc2_command import TMCC2FixedParameterCommand
from ..constants import CommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT


class DialogCmd(TMCC2FixedParameterCommand):
    def __init__(
        self,
        engine: int,
        command: TMCC2RailSoundsDialogControl,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        super().__init__(command, engine, data, scope, baudrate, port, server)
