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
        super().__init__(engine, baudrate, port)
        self._option = option
        self._option_data = option_data
        self._command = self._build_command()

    def __repr__(self):
        data = f" [{self._option_data}] " if self._option.value.num_data_bits else ''
        return f"<Engine {self.address} {self._option.name}{data}: 0x{self.command_bytes.hex()}>"

    def _build_command(self) -> bytes:
        command_op = self._option.value.apply_data(self._option_data)
        return self.command_prefix + self._encode_address(command_op)
