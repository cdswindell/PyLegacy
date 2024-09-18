from .tmcc2_command import TMCC2Command
from .tmcc2_param_constants import TMCC2ParameterEnum
from ..command_req import CommandReq
from ..constants import CommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT
from src.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef


class EngineCmd(TMCC2Command):
    def __init__(self,
                 engine: int,
                 command: TMCC2EngineCommandDef | TMCC2ParameterEnum,
                 data: int = 0,
                 scope: CommandScope = CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT,
                 server: str = None) -> None:
        if scope is None or scope not in [CommandScope.ENGINE, CommandScope.TRAIN]:
            raise ValueError(f"Scope must be ENGINE or TRAIN ({scope})")
        if engine < 1 or engine > 99:
            raise ValueError(f"{scope.name.capitalize()} must be between 1 and 99")
        req = CommandReq.build_request(command, engine, data, scope)
        super().__init__(command, req, engine, data, scope, baudrate, port, server)
