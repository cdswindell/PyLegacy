from .tmcc1_command import TMCC1Command
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, TMCC1AuxCommandDef


class AccCmd(TMCC1Command):
    def __init__(self, acc: int,
                 command: TMCC1AuxCommandDef,  # enum
                 data: int = None,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if acc < 1 or acc > 99:
            raise ValueError("Accessory must be between 1 and 99")
        super().__init__(acc, baudrate, port)
        self._command_req = CommandReq(command, acc, data=data)
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        return self._command_req.as_bytes
