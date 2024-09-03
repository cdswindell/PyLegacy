from ..constants import TMCC2CommandScope, LEGACY_ROUTE_COMMAND
from .tmcc2_command import TMCC2Command


class RouteCmd(TMCC2Command):
    def __init__(self, route: int, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        if route < 1 or route > 99:
            raise ValueError("Route must be between 1 and 99")
        super().__init__(TMCC2CommandScope.EXTENDED, route, baudrate, port)
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        return self.command_prefix + self._encode_address(LEGACY_ROUTE_COMMAND)
