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
                               help="Cab lights auto")
        cab_group.add_argument("-on",
                               action="store_const",
                               const=TMCC2LightingControl.CAB_ON,
                               dest='option',
                               help="Cab lights on")
        cab_group.add_argument("-off",
                               action="store_const",
                               const=TMCC2LightingControl.CAB_OFF,
                               dest='option',
                               help="Cab lights off")

        car = sp.add_parser('car', help='Car cabin lighting options')
        car_group = car.add_mutually_exclusive_group()
        car_group.add_argument("-a", "--auto",
                               action="store_const",
                               const=TMCC2LightingControl.CAR_AUTO,
                               dest='option',
                               default=TMCC2LightingControl.CAR_AUTO,
                               help="Car cabin lights auto")
        car_group.add_argument("-on",
                               action="store_const",
                               const=TMCC2LightingControl.CAR_ON,
                               dest='option',
                               help="Car cabin lights on")
        car_group.add_argument("-off",
                               action="store_const",
                               const=TMCC2LightingControl.CAR_OFF,
                               dest='option',
                               help="Car cabin lights off")

        ground = sp.add_parser('ground', aliases=['gr'], help='Ground lighting options')
        ground_group = ground.add_mutually_exclusive_group()
        ground_group.add_argument("-a", "--auto",
                                  action="store_const",
                                  const=TMCC2LightingControl.GROUND_AUTO,
                                  dest='option',
                                  default=TMCC2LightingControl.GROUND_AUTO,
                                  help="Ground lights auto")
        ground_group.add_argument("-on",
                                  action="store_const",
                                  const=TMCC2LightingControl.GROUND_ON,
                                  dest='option',
                                  help="Ground lights on")
        ground_group.add_argument("-off",
                                  action="store_const",
                                  const=TMCC2LightingControl.GROUND_OFF,
                                  dest='option',
                                  help="Ground lights off")
        hazard = sp.add_parser('hazard', aliases=['ha'], help='Hazard lighting options')
        hazard_group = hazard.add_mutually_exclusive_group()
        hazard_group.add_argument("-a", "--auto",
                                  action="store_const",
                                  const=TMCC2LightingControl.HAZARD_AUTO,
                                  dest='option',
                                  default=TMCC2LightingControl.HAZARD_AUTO,
                                  help="Hazard lights auto")
        hazard_group.add_argument("-on",
                                  action="store_const",
                                  const=TMCC2LightingControl.HAZARD_ON,
                                  dest='option',
                                  help="Hazard lights on")
        hazard_group.add_argument("-off",
                                  action="store_const",
                                  const=TMCC2LightingControl.HAZARD_OFF,
                                  dest='option',
                                  help="Hazard lights off")

        dog = sp.add_parser('doghouse', aliases=['dog'], help='Doghouse lighting options')
        dog_group = dog.add_mutually_exclusive_group()

        dog_group.add_argument("-on",
                               action="store_const",
                               const=TMCC2LightingControl.DOGHOUSE_ON,
                               dest='option',
                               default=TMCC2LightingControl.DOGHOUSE_ON,
                               help="Dog house light on")
        dog_group.add_argument("-off",
                               action="store_const",
                               const=TMCC2LightingControl.DOGHOUSE_OFF,
                               dest='option',
                               help="Dog house light off")

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
