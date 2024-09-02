from .tmcc1_command import TMCC1Command
from ..constants import AuxChoice, AuxOption, DEFAULT_BAUDRATE, DEFAULT_PORT, TMCC1_ACC_CHOICE_MAP


class AccCmd(TMCC1Command):
    def __init__(self, acc: int,
                 choice: AuxChoice,
                 option: AuxOption,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if acc < 1 or acc > 99:
            raise ValueError("Accessory must be between 1 and 99")
        super().__init__(baudrate, port)
        self._acc = acc
        self._choice = choice
        self._option = option
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        choices = TMCC1_ACC_CHOICE_MAP[self._choice]
        if isinstance(choices, int):
            choice = int(choices)
        else:
            choice = choices[self._option]
        return self.command_prefix + self._encode_address(self._acc, choice)
