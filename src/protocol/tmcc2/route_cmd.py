from .tmcc2_command import TMCC2Command
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from ..constants import LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX, TMCC2RouteCommandDef


class RouteCmd(TMCC2Command):
    def __init__(self, route: int, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT) -> None:
        if route < 1 or route > 99:
            raise ValueError("Route must be between 1 and 99")
        req = CommandReq(TMCC2RouteCommandDef.ROUTE, route)
        super().__init__(TMCC2RouteCommandDef.ROUTE, req, route, 0, None, baudrate, port)
        self._command = self._build_command()

    def _command_prefix(self) -> bytes:
        return LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX.to_bytes(1, byteorder='big')
