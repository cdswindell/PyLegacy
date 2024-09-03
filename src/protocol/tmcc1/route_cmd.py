from .tmcc1_command import TMCC1Command
from ..constants import TMCC1_ROUTE_COMMAND, DEFAULT_BAUDRATE, DEFAULT_PORT


class RouteCmd(TMCC1Command):
    def __init__(self, route: int, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT) -> None:
        if route < 1 or route > 99:
            raise ValueError("Route must be between 1 and 99")
        super().__init__(route, baudrate, port)
        self._command = self._build_command()

    def _build_command(self) -> bytes:
        if self.address < 32:
            return self.command_prefix + self._encode_address(TMCC1_ROUTE_COMMAND)
        else:
            raise ValueError("TMCC1 Route must be between 1 and 31")
