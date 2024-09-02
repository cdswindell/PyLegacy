#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBaseTMCC, cli_parser
from src.cli.cli_base import tmcc1_cli_parser
from src.protocol.tmcc1.route_cmd import RouteCmd as RouteCmdTMCC1
from src.protocol.tmcc2.route_cmd import RouteCmd as RouteCmdTMCC2


class RouteCli(CliBaseTMCC):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        self.route = self._args.route
        try:
            if self.use_tmcc1_format:
                RouteCmdTMCC1(self.route, baudrate=self._args.baudrate, port=self._args.port).fire()
            else:
                RouteCmdTMCC2(self.route, baudrate=self._args.baudrate, port=self._args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Fire specified route (1 - 99)", parents=[cli_parser(), tmcc1_cli_parser()])
    parser.add_argument("route", metavar='Route Number', type=int, help="route to fire")
    RouteCli(parser)
