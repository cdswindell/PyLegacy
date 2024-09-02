from ..constants import TMCC2CommandScope, EngineOption, DEFAULT_BAUDRATE, DEFAULT_PORT
from .tmcc2_command import TMCC2Command


class EngineCmd(TMCC2Command):
    def __init__(self,
                 engine: int,
                 option: EngineOption,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if engine < 1 or engine > 99:
            raise ValueError("Engine must be between 1 and 99")
        super().__init__(TMCC2CommandScope.EXTENDED, baudrate, port)
        self._engine = engine
        self._option = option
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        return self.command_prefix + self._encode_address(self._engine, self._option)
