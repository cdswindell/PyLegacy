#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBase
from src.cli.cli_base import cli_parser_factory
from src.protocol.tmcc1.route_cmd import RouteCmd


class RouteCli(CliBase):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        self.route = self.args.route
        try:
            RouteCmd(self.route, baudrate=self.args.baudrate, port=self.args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Fire specified base_sh (1 - 99)",
                                     parents=[cli_parser_factory()])
    parser.add_argument("route", metavar='Route Number', type=int, help="route to fire")

    args = parser.parse_args()
    RouteCli(parser)
