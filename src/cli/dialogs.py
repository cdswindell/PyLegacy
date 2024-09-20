#!/usr/bin/env python3
from typing import List

from src.cli.cli_base import CliBaseTMCC
from src.protocol.tmcc2.dialog_cmd import DialogCmd
from src.protocol.tmcc2.tmcc2_param_constants import TMCC2RailSoundsDialogControl
from src.utils.argument_parser import ArgumentParser


class DialogsCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        dialog_parser = ArgumentParser(add_help=False)
        dialog_parser.add_argument("engine",
                                   metavar='Engine/Train/Car',
                                   type=int,
                                   help="Engine/Train/Car to control")
        dialog_parser.add_argument("-sd", "-conventional_shutdown",
                                   action="store_const",
                                   dest="option",
                                   const=TMCC2RailSoundsDialogControl.CONVENTIONAL_SHUTDOWN,
                                   help="Conventional mode SHUTDOWN dialog")
        dialog_parser.add_argument("-sh", "-short_horn",
                                   action="store_const",
                                   dest="option",
                                   const=TMCC2RailSoundsDialogControl.SHORT_HORN,
                                   help="Conventional mode short horn dialog")
        dialog_parser.add_argument("-2", "-scene_two",
                                   action="store_const",
                                   dest="option",
                                   const=TMCC2RailSoundsDialogControl.SCENE_TWO,
                                   help="Scene <2> key context-dependent trigger")
        dialog_parser.add_argument("-5", "-scene_five",
                                   action="store_const",
                                   dest="option",
                                   const=TMCC2RailSoundsDialogControl.SCENE_FIVE,
                                   help="Scene <5> key context-dependent trigger")
        dialog_parser.add_argument("-7", "-scene_seven",
                                   action="store_const",
                                   dest="option",
                                   const=TMCC2RailSoundsDialogControl.SCENE_SEVEN,
                                   help="Scene <7> key context-dependent trigger")
        sp = dialog_parser.add_subparsers(dest='sub_command', help='Engine/train sub-commands')

        eng = sp.add_parser('engineer', aliases=['en'], help='Engineer dialogs')
        eng_group = eng.add_mutually_exclusive_group()
        eng_group.add_argument("-dd", "-departure_denied",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_DEPARTURE_DENIED,
                               dest='option',
                               help="Engineer: first departure denied")
        eng_group.add_argument("-dg", "-departure_granted",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_DEPARTURE_GRANTED,
                               dest='option',
                               help="Engineer: first departure granted")
        eng_group.add_argument("-hd", "-have_departed",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_HAVE_DEPARTED,
                               dest='option',
                               help="Engineer: first have departed")
        eng_group.add_argument("-ac", "-all_clear",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_ALL_CLEAR,
                               dest='option',
                               help="Engineer: first all clear")
        eng_group.add_argument("-sh", "-stop_hold",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_STOP_HOLD,
                               dest='option',
                               help="Engineer: first stop and hold ack")
        eng_group.add_argument("-rs", "-restricted_speed",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_RESTRICTED_SPEED,
                               dest='option',
                               help="Engineer: first restricted speed ack")
        eng_group.add_argument("-ss", "-slow_speed",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_SLOW_SPEED,
                               dest='option',
                               help="Engineer: first slow speed ack")
        eng_group.add_argument("-ms", "-medium_speed",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_MEDIUM_SPEED,
                               dest='option',
                               help="Engineer: first medium speed ack")
        eng_group.add_argument("-ls", "-limited_speed",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_LIMITED_SPEED,
                               dest='option',
                               help="Engineer: first limited speed ack")
        eng_group.add_argument("-ns", "-normal_speed",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_NORMAL_SPEED,
                               dest='option',
                               help="Engineer: first normal speed ack")
        eng_group.add_argument("-hs", "-highball_speed",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_HIGHBALL_SPEED,
                               dest='option',
                               help="Engineer: first highball speed ack")
        eng_group.add_argument("-id",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_ID,
                               dest='option',
                               help="Engineer: identify")
        eng_group.add_argument("-ack",
                               action="store_const",
                               const=TMCC2RailSoundsDialogControl.ENGINEER_ACK,
                               dest='option',
                               help="Engineer: acknowledge communication")

        tower = sp.add_parser('tower', aliases=['to'], help='Tower dialogs')
        tower_group = tower.add_mutually_exclusive_group()
        tower_group.add_argument("-su", "-start_up",
                                 action="store_const",
                                 const=TMCC2RailSoundsDialogControl.TOWER_STARTUP,
                                 dest='option',
                                 help="Tower: first engine startup dialog")
        tower_group.add_argument("-sh", "-stop_hold",
                                 action="store_const",
                                 const=TMCC2RailSoundsDialogControl.TOWER_STOP_HOLD,
                                 dest='option',
                                 help="Tower: first stop and hold dialog (non-emergency)")
        tower_group.add_argument("-rs", "-restricted_speed",
                                 action="store_const",
                                 const=TMCC2RailSoundsDialogControl.TOWER_RESTRICTED_SPEED,
                                 dest='option',
                                 help="Tower: first restricted speed")
        tower_group.add_argument("-ss", "-slow_speed",
                                 action="store_const",
                                 const=TMCC2RailSoundsDialogControl.TOWER_SLOW_SPEED,
                                 dest='option',
                                 help="Tower: first slow speed")
        tower_group.add_argument("-ms", "-medium_speed",
                                 action="store_const",
                                 const=TMCC2RailSoundsDialogControl.TOWER_MEDIUM_SPEED,
                                 dest='option',
                                 help="Tower: first medium speed")
        tower_group.add_argument("-ls", "-limited_speed",
                                 action="store_const",
                                 const=TMCC2RailSoundsDialogControl.TOWER_LIMITED_SPEED,
                                 dest='option',
                                 help="Tower: first limited speed")
        tower_group.add_argument("-ns", "-normal_speed",
                                 action="store_const",
                                 const=TMCC2RailSoundsDialogControl.TOWER_NORMAL_SPEED,
                                 dest='option',
                                 help="Tower: first normal speed")
        tower_group.add_argument("-hs", "-highball_speed",
                                 action="store_const",
                                 const=TMCC2RailSoundsDialogControl.TOWER_HIGHBALL_SPEED,
                                 dest='option',
                                 help="Tower: first highball speed")

        return ArgumentParser("Engine/train/car dialogs",
                              parents=[dialog_parser,
                                       cls.multi_parser(),
                                       cls.train_parser(),
                                       cls.cli_parser()
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
            cmd = DialogCmd(engine,
                            TMCC2RailSoundsDialogControl(option),
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
    DialogsCli(DialogsCli.command_parser())
