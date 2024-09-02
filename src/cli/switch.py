#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBase, cli_parser_factory
from src.protocol.constants import SwitchState
from src.protocol.tmcc1.switch_cmd import SwitchCmd


class SwitchCli(CliBase):
    """
        Throw the specified switch.

        Currently only available via the TMCC1 command format
    """
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        self._switch = self._args.switch
        self._switch_state = SwitchState.OUT if self._args.out else SwitchState.THROUGH
        try:
            SwitchCmd(self._switch, self._switch_state, baudrate=self._args.baudrate, port=self._args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Fire specified switch (1 - 99)", parents=[cli_parser_factory()])
    parser.add_argument("switch", metavar='Switch Number', type=int, help="switch to fire")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-t", "--through", action="store_const", const=True,
                       help="Throw Through")
    group.add_argument("-o", "--out", action="store_const", const=True,
                       help="Throw Out")
    SwitchCli(parser)
