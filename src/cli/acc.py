#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBase, cli_parser_factory
from src.protocol.constants import AuxChoice, AuxOption
from src.protocol.tmcc1.acc_cmd import AccCmd as AccCmdTMCC1


class AccCli(CliBase):
    """
        Issue Accessory Commands.

        Currently only available via the TMCC1 command format
    """

    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        self._acc = self._args.acc
        self._choice = self._args.choice
        self._option = self._args.option
        try:
            AccCmdTMCC1(self._acc, self._choice, self._option,
                        baudrate=self._args.baudrate, port=self._args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Fire specified accessory (1 - 99)",
                                     parents=[cli_parser_factory()])
    parser.add_argument("acc", metavar='Accessory Number', type=int, help="accessory to fire")

    aux_group = parser.add_mutually_exclusive_group(required=True)
    aux_group.add_argument("-a1", "--aux1",
                           action="store_const",
                           const=AuxChoice.AUX1,
                           dest='choice',
                           help="Aux 1")
    aux_group.add_argument("-a2", "--aux2",
                           action="store_const",
                           const=AuxChoice.AUX2,
                           dest='choice',
                           help="Aux 2")
    aux_group.add_argument("-ao", "--acc_on",
                           action="store_const",
                           const=AuxChoice.ON,
                           dest='choice',
                           help="Accessory On")
    aux_group.add_argument("-af", "--acc_off",
                           action="store_const",
                           const=AuxChoice.OFF,
                           dest='choice',
                           help="Accessory Off")
    aux_group.add_argument("-s", "--set_address",
                           action="store_const",
                           const=AuxChoice.SET_ADDRESS,
                           dest='choice',
                           help="Set Accessory Address")

    option_group = parser.add_mutually_exclusive_group()
    option_group.add_argument("-on", "--on",
                              action="store_const",
                              const=AuxOption.ON,
                              dest='option',
                              help="Aux1/Aux2 On")
    option_group.add_argument("-off", "--off",
                              action="store_const",
                              const=AuxOption.OFF,
                              dest='option',
                              help="Aux1/Aux2 Off")
    option_group.add_argument("-o1", "--option1",
                              action="store_const",
                              const=AuxOption.OPTION1,
                              dest='option',
                              help="Aux1/Aux2 Option 1 (Aux 1/Aux 2 button")
    option_group.add_argument("-o2", "--option2",
                              action="store_const",
                              const=AuxOption.OPTION2,
                              dest='option',
                              help="Aux1/Aux2 Option 2")
    option_group.set_defaults(option=AuxOption.OPTION1)

    # fire command
    AccCli(parser)
