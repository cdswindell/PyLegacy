from .tmcc2_command import TMCC2FixedParameterCommand
from .tmcc2_param_constants import TMCC2LightingControl
from ..constants import CommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT


class LightingCmd(TMCC2FixedParameterCommand):
    def __init__(self,
                 engine: int,
                 command: TMCC2LightingControl,
                 data: int = 0,
                 scope: CommandScope = CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        super().__init__(command, engine, data, scope, baudrate, port)