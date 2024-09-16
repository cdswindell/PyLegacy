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

        ditch = sp.add_parser('ditch', aliases=['di'], help='Ditch lighting options')
        ditch_group = ditch.add_mutually_exclusive_group()
        ditch_group.add_argument("-on",
                                 action="store_const",
                                 const=TMCC2LightingControl.DITCH_ON,
                                 dest='option',
                                 default=TMCC2LightingControl.DITCH_ON,
                                 help="Ditch lights on")
        ditch_group.add_argument("-onh", "--on_off_w_horn",
                                 action="store_const",
                                 const=TMCC2LightingControl.DITCH_ON_PULSE_OFF_WITH_HORN,
                                 dest='option',
                                 help="Ditch lights on, pulse off w/ horn")
        ditch_group.add_argument("-ofh", "--off_on_w_horn",
                                 action="store_const",
                                 const=TMCC2LightingControl.DITCH_OFF_PULSE_ON_WITH_HORN,
                                 dest='option',
                                 help="Ditch lights off, pulse on w/ horn")
        ditch_group.add_argument("-off",
                                 action="store_const",
                                 const=TMCC2LightingControl.DITCH_OFF,
                                 dest='option',
                                 help="Ditch lights off")

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

        loco = sp.add_parser('engine_marker', aliases=['em'], help='Engine marker lighting options')
        loco_group = loco.add_mutually_exclusive_group()

        loco_group.add_argument("-on",
                                action="store_const",
                                const=TMCC2LightingControl.LOCO_MARKER_ON,
                                dest='option',
                                default=TMCC2LightingControl.LOCO_MARKER_ON,
                                help="Engine marker lights on")
        loco_group.add_argument("-off",
                                action="store_const",
                                const=TMCC2LightingControl.LOCO_MARKER_OFF,
                                dest='option',
                                help="Engine marker lights off")

        mars = sp.add_parser('mars', aliases=['ma'], help='Mars lighting options')
        mars_group = mars.add_mutually_exclusive_group()

        mars_group.add_argument("-on",
                                action="store_const",
                                const=TMCC2LightingControl.MARS_ON,
                                dest='option',
                                default=TMCC2LightingControl.MARS_ON,
                                help="Mars lights on")
        mars_group.add_argument("-off",
                                action="store_const",
                                const=TMCC2LightingControl.MARS_OFF,
                                dest='option',
                                help="Mars lights off")

        r17 = sp.add_parser('rule17', aliases=['17'], help='Rule 17 lighting options')
        r17_group = r17.add_mutually_exclusive_group()
        r17_group.add_argument("-a", "--auto",
                               action="store_const",
                               const=TMCC2LightingControl.RULE_17_AUTO,
                               dest='option',
                               default=TMCC2LightingControl.RULE_17_AUTO,
                               help="Rule 17 auto")
        r17_group.add_argument("-on",
                               action="store_const",
                               const=TMCC2LightingControl.RULE_17_ON,
                               dest='option',
                               help="Rule 17 on")
        r17_group.add_argument("-off",
                               action="store_const",
                               const=TMCC2LightingControl.RULE_17_OFF,
                               dest='option',
                               help="Rule 17 off")

        strobe = sp.add_parser('strobe', aliases=['st'], help='Strobe lighting options')
        strobe_group = strobe.add_mutually_exclusive_group()
        strobe_group.add_argument("-on",
                                  action="store_const",
                                  const=TMCC2LightingControl.STROBE_LIGHT_ON,
                                  dest='option',
                                  default=TMCC2LightingControl.STROBE_LIGHT_ON,
                                  help="Strobe lights on, single-flash")
        strobe_group.add_argument("-df", "--double_flash",
                                  action="store_const",
                                  const=TMCC2LightingControl.STROBE_LIGHT_ON_DOUBLE,
                                  dest='option',
                                  help="Strobe lights on, double-flash")
        strobe_group.add_argument("-off",
                                  action="store_const",
                                  const=TMCC2LightingControl.STROBE_LIGHT_OFF,
                                  dest='option',
                                  help="Strobe lights off")

        tender = sp.add_parser('tender_marker', aliases=['tm'], help='Tender marker lighting options')
        tender_group = tender.add_mutually_exclusive_group()

        tender_group.add_argument("-on",
                                  action="store_const",
                                  const=TMCC2LightingControl.TENDER_MARKER_ON,
                                  dest='option',
                                  default=TMCC2LightingControl.TENDER_MARKER_ON,
                                  help="Tender marker lights on")
        tender_group.add_argument("-off",
                                  action="store_const",
                                  const=TMCC2LightingControl.TENDER_MARKER_OFF,
                                  dest='option',
                                  help="Tender marker lights off")

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