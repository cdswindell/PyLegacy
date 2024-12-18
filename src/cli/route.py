#!/usr/bin/env python3
import logging
from typing import List

from src.cli.cli_base import CliBaseTMCC
from src.protocol.tmcc1.route_cmd import RouteCmd as RouteCmdTMCC1
from src.protocol.tmcc2.route_cmd import RouteCmd as RouteCmdTMCC2
from src.utils.argument_parser import ArgumentParser

log = logging.getLogger(__name__)


class RouteCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        route_parser = ArgumentParser(add_help=False)
        route_parser.add_argument("route", metavar="Route", type=int, help="route to fire")
        return ArgumentParser(
            "Fire specified route (1 - 99)", parents=[route_parser, cls.command_format_parser(), cls.cli_parser()]
        )

    def __init__(self, arg_parser: ArgumentParser, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self.route = self._args.route
        try:
            if self.is_tmcc1:
                cmd = RouteCmdTMCC1(self.route, baudrate=self._baudrate, port=self._port, server=self._server)
            else:
                cmd = RouteCmdTMCC2(self.route, baudrate=self._baudrate, port=self._port, server=self._server)
            if self.do_fire:
                cmd.fire()
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)


if __name__ == "__main__":
    RouteCli(RouteCli.command_parser())
