from command_base import CommandBase


class RouteCmd(CommandBase):
    def __init__(self, route: int, baudrate: int=9600, port:str = "/dev/ttyUSB0") -> None:
        CommandBase.__init__(self, baudrate, port)
