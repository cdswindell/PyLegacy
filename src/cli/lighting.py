#!/usr/bin/env python3
#
import argparse
from typing import List

from src.cli.cli_base import CliBaseTMCC, train_parser, cli_parser
from src.protocol.tmcc2.lighting_cmd import LightingCmd
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2LightingControl


class LightingCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        lighting_parser = argparse.ArgumentParser(add_help=False)
        lighting_parser.add_argument("engine",
                                     metavar='Engine/Train',
                                     type=int,
                                     help="Engine/Train to control")
        sp = lighting_parser.add_subparsers(dest='sub_command', help='Engine/train sub-commands')
        cab = sp.add_parser('cab', help='Cab lighting options')
        cab_group = cab.add_mutually_exclusive_group()
        cab_group.add_argument("-a", "--auto",
                               action="store_const",
                               const=TMCC2LightingControl.CAB_AUTO,
                               dest='option',
                               default=TMCC2LightingControl.CAB_AUTO,
                               help="Cab light auto")
        cab_group.add_argument("-on",
                               action="store_const",
                               const=TMCC2LightingControl.CAB_ON,
                               dest='option',
                               help="Cab light on")
        cab_group.add_argument("-off",
                               action="store_const",
                               const=TMCC2LightingControl.CAB_OFF,
                               dest='option',
                               help="Cab light off")

        return argparse.ArgumentParser("Lighting control",
                                       parents=[lighting_parser,
                                                train_parser(),
                                                cli_parser()
                                                ])

    def __init__(self,
                 arg_parser: argparse.ArgumentParser,
                 cmd_line: List[str] = None,
                 do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        engine: int = self._args.engine
        option = self._args.option
        try:
            scope = self._determine_scope()
            cmd = LightingCmd(engine,
                              TMCC2LightingControl(option),
                              0,
                              scope,
                              baudrate=self._args.baudrate,
                              port=self._args.port)
            if self.do_fire:
                cmd.fire()
            self._command = cmd
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    LightingCli(LightingCli.command_parser())
