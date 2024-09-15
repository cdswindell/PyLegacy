from .tmcc1_command import TMCC1Command
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from ..tmcc1_constants import TMCC1RouteCommandDef


class RouteCmd(TMCC1Command):
    def __init__(self, route: int, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT) -> None:
        if route < 1 or route > 31:
            raise ValueError("TMCC1 Route must be between 1 and 31")
        req = CommandReq(TMCC1RouteCommandDef.ROUTE, route)
        super().__init__(TMCC1RouteCommandDef.ROUTE, req, route, 0, None, baudrate, port)
        self._command = self._build_command()
