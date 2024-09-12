#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBase, cli_parser
from src.protocol.constants import TMCC1SwitchState
from src.protocol.tmcc1.switch_cmd import SwitchCmd


class SwitchCli(CliBase):
    """
        Throw the specified switch.

        Currently only available via the TMCC1 command format
    """
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        self._switch = self._args.switch
        self._switch_state = self._args.command
        try:
            SwitchCmd(self._switch, self._switch_state, baudrate=self._args.baudrate, port=self._args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    sw_parser = argparse.ArgumentParser(add_help=False)
    sw_parser.add_argument("switch", metavar='Switch Number', type=int, help="switch to fire")
    group = sw_parser.add_mutually_exclusive_group()
    group.add_argument("-t", "--through",
                       action="store_const",
                       const=TMCC1SwitchState.THROUGH,
                       dest="command",
                       help="Throw Through")
    group.add_argument("-o", "--out",
                       action="store_const",
                       const=TMCC1SwitchState.OUT,
                       dest="command",
                       help="Throw Out")
    group.add_argument("-a", "--set_address",
                       action="store_const",
                       const=TMCC1SwitchState.SET_ADDRESS,
                       dest="command",
                       help="Set switch address")
    group.set_defaults(command=TMCC1SwitchState.THROUGH)
    parser = argparse.ArgumentParser("Fire specified switch (1 - 99)", parents=[sw_parser, cli_parser()])
    SwitchCli(parser)
