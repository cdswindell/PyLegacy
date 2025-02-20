from .tmcc1_command import TMCC1Command
from .tmcc1_constants import TMCC1AuxCommandEnum
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT


class AccCmd(TMCC1Command):
    def __init__(
        self,
        acc: int,
        command: TMCC1AuxCommandEnum,  # enum
        data: int = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        if acc < 1 or acc > 99:
            raise ValueError("Accessory must be between 1 and 99")
        req = CommandReq(command, acc, data=data)
        super().__init__(command, req, acc, data, None, baudrate, port, server=server)
        self._command = self._build_command()
