#!/usr/bin/env python3
#
import argparse
from typing import List

from src.cli.cli_base import CliBaseTMCC, cli_parser
from src.cli.cli_base import command_format_parser
from src.protocol.tmcc1.route_cmd import RouteCmd as RouteCmdTMCC1
from src.protocol.tmcc2.route_cmd import RouteCmd as RouteCmdTMCC2


class RouteCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        route_parser = argparse.ArgumentParser(add_help=False)
        route_parser.add_argument("route", metavar='Route', type=int, help="route to fire")
        return argparse.ArgumentParser("Fire specified route (1 - 99)",
                                       parents=[route_parser, command_format_parser(), cli_parser()])

    def __init__(self,
                 arg_parser: argparse.ArgumentParser,
                 cmd_line: List[str] = None,
                 do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line)
        self.route = self._args.route
        try:
            if self.is_tmcc1:
                cmd = RouteCmdTMCC1(self.route, baudrate=self._args.baudrate, port=self._args.port)
            else:
                cmd = RouteCmdTMCC2(self.route, baudrate=self._args.baudrate, port=self._args.port)
            if do_fire:
                cmd.fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    RouteCli(RouteCli.command_parser())
