from .tmcc1_command import TMCC1Command
from .tmcc1_constants import TMCC1RouteCommandEnum

from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT


class RouteCmd(TMCC1Command):
    def __init__(
        self, route: int, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT, server: str = None
    ) -> None:
        if route < 1 or route > 31:
            raise ValueError("TMCC1 Route must be between 1 and 31")
        req = CommandReq(TMCC1RouteCommandEnum.FIRE, route)
        super().__init__(TMCC1RouteCommandEnum.FIRE, req, route, 0, None, baudrate, port, server)
        self._command = self._build_command()
