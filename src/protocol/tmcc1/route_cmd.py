from .tmcc1_command import TMCC1Command
from ..constants import TMCC1_ROUTE_COMMAND


class RouteCmd(TMCC1Command):
    def __init__(self, route: int, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        super().__init__(baudrate, port)
        if route < 1 or route > 99:
            raise ValueError("Route must be between 1 and 99")
        self._route = route
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        if self._route < 32:
            return self.command_prefix + self._encode_address(self._route, TMCC1_ROUTE_COMMAND)
        else:
            raise ValueError("TMCC1 Route must be between 1 and 31")
