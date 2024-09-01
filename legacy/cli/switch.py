#!/usr/bin/env python
#
import argparse

from legacy.cli.cli_base import CliBase
from legacy.cli.cli_base import cli_parser_factory
from legacy.protocol import SwitchState
from legacy.protocol.switch_cmd import SwitchCmd


class SwitchCli(CliBase):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        self._switch = self.args.switch
        self._switch_state = SwitchState.OUT if self.args.out else SwitchState.THROUGH
        try:
            SwitchCmd(self._switch, self._switch_state, baudrate=self.args.baudrate, port=self.args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Fire specified switch (1 - 99)",
                                     parents=[cli_parser_factory()])
    parser.add_argument("switch", metavar='Switch Number', type=int, help="switch to fire")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-t", "--through", action="store_const", const=True,
                       help="Throw Through")
    group.add_argument("-o", "--out", action="store_const", const=True,
                       help="Throw Out")

    args = parser.parse_args()
    SwitchCli(parser)
