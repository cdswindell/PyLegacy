from .tmcc2_command import TMCC2Command
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from .tmcc2_constants import LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX, TMCC2RouteCommandEnum


class RouteCmd(TMCC2Command):
    def __init__(
        self, route: int, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT, server: str = None
    ) -> None:
        if route < 1 or route > 99:
            raise ValueError("Route must be between 1 and 99")
        req = CommandReq(TMCC2RouteCommandEnum.FIRE, route)
        super().__init__(TMCC2RouteCommandEnum.FIRE, req, route, 0, None, baudrate, port, server)
        self._command = self._build_command()

    def _command_prefix(self) -> bytes:
        return LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX.to_bytes(1, byteorder="big")
