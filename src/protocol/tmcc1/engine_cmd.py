from ..constants import TMCC1EngineOption, DEFAULT_BAUDRATE, DEFAULT_PORT
from .tmcc1_command import TMCC1Command


class EngineCmd(TMCC1Command):
    def __init__(self,
                 engine: int,
                 option: TMCC1EngineOption,
                 option_data: int = 0,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if engine < 1 or engine > 99:
            raise ValueError("Engine must be between 1 and 99")
        super().__init__(baudrate, port)
        self._engine = engine
        self._option = option
        self._option_data = option_data
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        command_op = self._option.value.apply_data(self._option_data)
        return self.command_prefix + self._encode_address(self._engine, command_op)
