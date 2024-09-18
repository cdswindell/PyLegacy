#!/usr/bin/env python3
from typing import List

from src.cli.cli_base import CliBaseTMCC, train_parser, cli_parser
from src.protocol.tmcc2.sound_effects_cmd import SoundEffectsCmd
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2RailSoundsEffectsControl
from src.utils.argument_parser import ArgumentParser


class SoundEffectsCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        sounds_parser = ArgumentParser(add_help=False)
        sounds_parser.add_argument("engine",
                                   metavar='Engine/Train',
                                   type=int,
                                   help="Engine/Train to control")
        sounds_parser.add_argument("-v+", "--volume_up",
                                   action="store_const",
                                   const=TMCC2RailSoundsEffectsControl.VOLUME_UP,
                                   dest='option',
                                   help="Increase master volume")
        sounds_parser.add_argument("-v-", "--volume_down",
                                   action="store_const",
                                   const=TMCC2RailSoundsEffectsControl.VOLUME_DOWN,
                                   dest='option',
                                   help="Decrease master volume")
        sounds_parser.add_argument("-b+", "--blend_up",
                                   action="store_const",
                                   const=TMCC2RailSoundsEffectsControl.BLEND_UP,
                                   dest='option',
                                   help="Blend level up")
        sounds_parser.add_argument("-b-", "--blend_down",
                                   action="store_const",
                                   const=TMCC2RailSoundsEffectsControl.BLEND_DOWN,
                                   dest='option',
                                   help="Blend level down")

        sp = sounds_parser.add_subparsers(dest='sub_command', help='Engine/train sub-commands')

        pm = sp.add_parser('prime_mover', aliases=['pm'], help='Prime mover options')
        pm_group = pm.add_mutually_exclusive_group()
        pm_group.add_argument("-on",
                              action="store_const",
                              const=TMCC2RailSoundsEffectsControl.PRIME_ON,
                              dest='option',
                              default=TMCC2RailSoundsEffectsControl.PRIME_ON,
                              help="Prime mover sound on")

        pm_group.add_argument("-off",
                              action="store_const",
                              const=TMCC2RailSoundsEffectsControl.PRIME_OFF,
                              dest='option',
                              help="Prime mover sound off")

        pm = sp.add_parser('sequence', aliases=['s'], help='Sequence control options')
        pm_group = pm.add_mutually_exclusive_group()
        pm_group.add_argument("-on",
                              action="store_const",
                              const=TMCC2RailSoundsEffectsControl.SEQUENCE_CONTROL_ON,
                              dest='option',
                              default=TMCC2RailSoundsEffectsControl.SEQUENCE_CONTROL_ON,
                              help="Enable RailSounds sequence control")

        pm_group.add_argument("-off",
                              action="store_const",
                              const=TMCC2RailSoundsEffectsControl.SEQUENCE_CONTROL_OFF,
                              dest='option',
                              help="Disable RailSounds sequence control")

        return ArgumentParser("RailSounds sound controls",
                              parents=[sounds_parser,
                                       train_parser(),
                                       cli_parser()
                                       ])

    def __init__(self,
                 arg_parser: ArgumentParser,
                 cmd_line: List[str] = None,
                 do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        engine: int = self._args.engine
        option = self._args.option
        try:
            scope = self._determine_scope()
            cmd = SoundEffectsCmd(engine,
                                  TMCC2RailSoundsEffectsControl(option),
                                  0,
                                  scope,
                                  baudrate=self._baudrate,
                                  port=self._port,
                                  server=self._server)
            if self.do_fire:
                cmd.fire()
            self._command = cmd
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    SoundEffectsCli(SoundEffectsCli.command_parser())
