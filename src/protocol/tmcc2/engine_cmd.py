from ..constants import TMCC2CommandScope, TMCC2EngineOption, DEFAULT_BAUDRATE, DEFAULT_PORT
from .tmcc2_command import TMCC2Command


class EngineCmd(TMCC2Command):
    def __init__(self,
                 engine: int,
                 option: TMCC2EngineOption,
                 option_data: int = 0,
                 scope: TMCC2CommandScope = TMCC2CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if engine < 1 or engine > 99:
            raise ValueError(f"{scope.name.capitalize()} must be between 1 and 99")
        super().__init__(scope, baudrate, port)
        self._engine = engine
        self._option = option
        self._option_data = option_data
        self._command = self._build_command()

    def __repr__(self):
        data = f" [{self._option_data}] " if self._option.value.num_data_bits else ''
        return f"<{self.scope.name} {self._engine} {self._option.name}{data}: 0x{self.command_bytes.hex()}>"

    def _build_command(self) -> bytes:
        command_op = self._option.value.apply_data(self._option_data)
        return self.command_prefix + self._encode_address(self._engine, command_op)
