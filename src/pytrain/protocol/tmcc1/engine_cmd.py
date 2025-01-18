from .tmcc1_command import TMCC1Command
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandEnum


class EngineCmd(TMCC1Command):
    def __init__(
        self,
        engine: int,
        command: TMCC1EngineCommandEnum,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        if scope == CommandScope.ENGINE:
            if engine < 1 or engine > 99:
                raise ValueError("Engine must be between 1 and 99")
        elif scope == CommandScope.TRAIN:
            if engine < 1 or engine > 10:
                raise ValueError("Train must be between 1 and 10")
        req = CommandReq(command, engine, data=data, scope=scope)
        super().__init__(command, req, engine, data, scope, baudrate, port, server)
        self._command = self._build_command()
