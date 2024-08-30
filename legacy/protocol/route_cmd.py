from . import CommandBase


class RouteCmd(CommandBase):
    def __init__(self, route: int, baudrate: int = 9600, port: str = "/dev/ttyUSB0") -> None:
        CommandBase.__init__(self, baudrate, port)
        if route < 1 or route > 99:
            raise ValueError("Route must be between 1 and 99")
        self._route = route

    def fire(self) -> None:
        if self._route < 10:
            pass
        else:
            pass
        print(f"Fire Route {self._route}")
