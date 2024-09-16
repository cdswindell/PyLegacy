#!/usr/bin/env python3
from typing import List

from src.cli.cli_base import CliBaseTMCC, cli_parser
from src.cli.cli_base import command_format_parser
from src.protocol.tmcc1.route_cmd import RouteCmd as RouteCmdTMCC1
from src.protocol.tmcc2.route_cmd import RouteCmd as RouteCmdTMCC2
from src.utils.argument_parser import ArgumentParser


class RouteCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        route_parser = ArgumentParser(add_help=False)
        route_parser.add_argument("route", metavar='Route', type=int, help="route to fire")
        return ArgumentParser("Fire specified route (1 - 99)",
                              parents=[route_parser, command_format_parser(), cli_parser()])

    def __init__(self,
                 arg_parser: ArgumentParser,
                 cmd_line: List[str] = None,
                 do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self.route = self._args.route
        try:
            if self.is_tmcc1:
                cmd = RouteCmdTMCC1(self.route,
                                    baudrate=self._args.baudrate,
                                    port=self._args.port,
                                    server=self._args.server)
            else:
                cmd = RouteCmdTMCC2(self.route,
                                    baudrate=self._args.baudrate,
                                    port=self._args.port,
                                    server=self._args.server)
            if self.do_fire:
                cmd.fire()
            self._command = cmd
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    RouteCli(RouteCli.command_parser())
