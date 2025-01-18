from .tmcc2_command import TMCC2Command
from ..multibyte.multibyte_constants import TMCC2MultiByteEnum
from ..command_req import CommandReq
from ..constants import CommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT
from .tmcc2_constants import TMCC2EngineCommandEnum


class EngineCmd(TMCC2Command):
    def __init__(
        self,
        engine: int,
        command: TMCC2EngineCommandEnum | TMCC2MultiByteEnum,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        if scope is None or scope not in [CommandScope.ENGINE, CommandScope.TRAIN]:
            raise ValueError(f"Scope must be ENGINE or TRAIN ({scope})")
        if engine < 1 or engine > 99:
            raise ValueError(f"{scope.name.title()} must be between 1 and 99")
        req = CommandReq.build(command, engine, data, scope)
        super().__init__(command, req, engine, data, scope, baudrate, port, server)
