from .tmcc1_command import TMCC1Command
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, TMCC1AuxCommandDef


class AccCmd(TMCC1Command):
    def __init__(self, acc: int,
                 option: TMCC1AuxCommandDef,
                 option_data: int = None,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if acc < 1 or acc > 99:
            raise ValueError("Accessory must be between 1 and 99")
        super().__init__(acc, baudrate, port)
        self._option = option
        self._option_data = option_data
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        command_op = self._option.value.apply_data(self._option_data)
        return self.command_prefix + self._encode_address(command_op)
