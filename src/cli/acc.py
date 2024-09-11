#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBase, cli_parser, DataAction
from src.protocol.constants import TMCC1AuxOption
from src.protocol.tmcc1.acc_cmd import AccCmd as AccCmdTMCC1

AUX_OPTIONS_MAP = {
    'on': 'ON',
    'off': 'OFF',
    'opt1': 'OPTION_ONE',
    'opt2': 'OPTION_TWO',
}


class AccCli(CliBase):
    """
        Issue Accessory Commands.

        Currently only available via the TMCC1 command format
    """

    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        self._acc = self._args.acc
        self._option = self._args.command_def
        self._data = self._args.data if 'data' in self._args else 0
        self._aux1 = self._args.aux1
        self._aux2 = self._args.aux2
        if self._args.aux1 and self._args.aux1 in AUX_OPTIONS_MAP:
            self._option = TMCC1AuxOption.by_name(f"AUX1_{AUX_OPTIONS_MAP[self._args.aux1]}")
        if self._args.aux2 and self._args.aux2 in AUX_OPTIONS_MAP:
            self._option = TMCC1AuxOption.by_name(f"AUX2_{AUX_OPTIONS_MAP[self._args.aux2]}")
        try:
            if self._option is None or not isinstance(self._option, TMCC1AuxOption):
                raise ValueError("Must specify an command_def, use -h for help")
            AccCmdTMCC1(self._acc, self._option, self._data,
                        baudrate=self._args.baudrate, port=self._args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    acc_parser = argparse.ArgumentParser(add_help=False)
    acc_parser.add_argument("acc", metavar='Accessory Number', type=int, help="accessory to fire")

    aux_group = acc_parser.add_mutually_exclusive_group()
    aux_group.add_argument("-aux1",
                           dest='aux1',
                           choices=['on', 'off', 'opt1', 'opt2'],
                           nargs='?',
                           type=str,
                           const='opt1')
    aux_group.add_argument("-aux2",
                           dest='aux2',
                           choices=['on', 'off', 'opt1', 'opt2'],
                           nargs='?',
                           type=str,
                           const='opt1')
    aux_group.add_argument("-n",
                           action=DataAction,
                           dest='command_def',
                           choices=range(0, 10),
                           metavar="0 - 9",
                           type=int,
                           nargs='?',
                           default=1,
                           const=TMCC1AuxOption.NUMERIC,
                           help="Numeric value")
    aux_group.add_argument("-a", "--set_address",
                           action="store_const",
                           const=TMCC1AuxOption.SET_ADDRESS,
                           dest='command_def',
                           help="Set Accessory Address")
    # fire command
    parser = argparse.ArgumentParser("Fire specified accessory (1 - 99)",
                                     parents=[acc_parser, cli_parser()])
    AccCli(parser)
