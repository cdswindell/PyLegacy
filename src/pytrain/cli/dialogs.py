#!/usr/bin/env python3

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import logging
from argparse import ArgumentParser
from typing import List

from ..protocol.multibyte.dialog_cmd import DialogCmd
from ..protocol.multibyte.multibyte_constants import TMCC2RailSoundsDialogControl
from ..utils.argument_parser import PyTrainArgumentParser
from . import CliBaseTMCC

log = logging.getLogger(__name__)


class DialogsCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        dialog_parser = PyTrainArgumentParser(add_help=False)
        dialog_parser.add_argument("engine", metavar="Engine/Train/Car", type=int, help="Engine/Train/Car to control")
        dialog_parser.add_argument(
            "-emergency",
            action="store_const",
            dest="option",
            const=TMCC2RailSoundsDialogControl.EMERGENCY_CONTEXT_DEPENDENT,
            help="Emergency context-dependent dialog",
        )
        dialog_parser.add_argument(
            "-sd",
            "-conventional_shutdown",
            action="store_const",
            dest="option",
            const=TMCC2RailSoundsDialogControl.CONVENTIONAL_SHUTDOWN,
            help="Conventional mode SHUTDOWN dialog",
        )
        dialog_parser.add_argument(
            "-sh",
            "-short_horn",
            action="store_const",
            dest="option",
            const=TMCC2RailSoundsDialogControl.SHORT_HORN,
            help="Conventional mode short horn dialog",
        )
        dialog_parser.add_argument(
            "-2",
            "-scene_two",
            action="store_const",
            dest="option",
            const=TMCC2RailSoundsDialogControl.SCENE_TWO,
            help="Scene <2> key context-dependent trigger",
        )
        dialog_parser.add_argument(
            "-5",
            "-scene_five",
            action="store_const",
            dest="option",
            const=TMCC2RailSoundsDialogControl.SCENE_FIVE,
            help="Scene <5> key context-dependent trigger",
        )
        dialog_parser.add_argument(
            "-7",
            "-scene_seven",
            action="store_const",
            dest="option",
            const=TMCC2RailSoundsDialogControl.SCENE_SEVEN,
            help="Scene <7> key context-dependent trigger",
        )
        sp = dialog_parser.add_subparsers(dest="sub_command", help="Engine/train sub-commands")

        eng = sp.add_parser("engineer", aliases=["en"], help="Engineer dialogs")
        eng_group = eng.add_mutually_exclusive_group()
        eng_group.add_argument(
            "-ac",
            "-all_clear",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ALL_CLEAR,
            dest="option",
            help="Engineer: first all clear",
        )
        eng_group.add_argument(
            "-ar",
            "-arriving",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ARRIVING,
            dest="option",
            help="Engineer: first departure denied",
        )
        eng_group.add_argument(
            "-ad",
            "-arrived",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ARRIVED,
            dest="option",
            help="Engineer: arrived",
        )
        eng_group.add_argument(
            "-ack",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ACK,
            dest="option",
            help="Engineer: acknowledge communication",
        )
        eng_group.add_argument(
            "-asb",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ACK_STAND_BY,
            dest="option",
            help="Engineer: ACK standing by",
        )
        eng_group.add_argument(
            "-aac",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ACK_CLEARED,
            dest="option",
            help="Engineer: ACK cleared to go",
        )
        eng_group.add_argument(
            "-aca",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ACK_CLEAR_AHEAD,
            dest="option",
            help="Engineer: ACK clear ahead",
        )
        eng_group.add_argument(
            "-aci",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ACK_CLEAR_INBOUND,
            dest="option",
            help="Engineer: ACK clear inbound",
        )
        eng_group.add_argument(
            "-awb",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ACK_WELCOME_BACK,
            dest="option",
            help="Engineer: ACK welcome back",
        )
        eng_group.add_argument(
            "-aid",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ACK_ID,
            dest="option",
            help="Engineer: ACK identify & out",
        )
        eng_group.add_argument(
            "-dd",
            "-departure_denied",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_DEPARTURE_DENIED,
            dest="option",
            help="Engineer: first departure denied",
        )
        eng_group.add_argument(
            "-dg",
            "-departure_granted",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_DEPARTURE_GRANTED,
            dest="option",
            help="Engineer: first departure granted",
        )
        eng_group.add_argument(
            "-de",
            "-departed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_DEPARTED,
            dest="option",
            help="Engineer: first have departed",
        )
        eng_group.add_argument(
            "-fl",
            "-fuel_level",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_FUEL_LEVEL,
            dest="option",
            help="Engineer: speaks fuel level",
        )
        eng_group.add_argument(
            "-fr",
            "-fuel_refilled",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_FUEL_REFILLED,
            dest="option",
            help="Engineer: speaks fuel refilled",
        )
        eng_group.add_argument(
            "-id",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_ID,
            dest="option",
            help="Engineer: identify",
        )
        eng_group.add_argument(
            "-s",
            "-speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SPEED,
            dest="option",
            help="Engineer: speaks speed",
        )
        eng_group.add_argument(
            "-sd",
            "-shutdown",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SHUTDOWN,
            dest="option",
            help="Engineer: shut down",
        )
        eng_group.add_argument(
            "-sh",
            "-stop_hold",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SPEED_STOP_HOLD,
            dest="option",
            help="Engineer: first stop and hold ack",
        )
        eng_group.add_argument(
            "-sr",
            "-restricted_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SPEED_RESTRICTED,
            dest="option",
            help="Engineer: first restricted speed ack",
        )
        eng_group.add_argument(
            "-ss",
            "-std_step_to_data",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SPEED_SLOW,
            dest="option",
            help="Engineer: first slow speed ack",
        )
        eng_group.add_argument(
            "-sm",
            "-medium_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SPEED_MEDIUM,
            dest="option",
            help="Engineer: first medium speed ack",
        )
        eng_group.add_argument(
            "-sl",
            "-limited_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SPEED_LIMITED,
            dest="option",
            help="Engineer: first limited speed ack",
        )
        eng_group.add_argument(
            "-sn",
            "-normal_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SPEED_NORMAL,
            dest="option",
            help="Engineer: first normal speed ack",
        )
        eng_group.add_argument(
            "-sx",
            "-highball_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_SPEED_HIGHBALL,
            dest="option",
            help="Engineer: first highball speed ack",
        )
        eng_group.add_argument(
            "-wl",
            "-water_level",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_WATER_LEVEL,
            dest="option",
            help="Engineer: speaks water level",
        )
        eng_group.add_argument(
            "-wr",
            "-water_refilled",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.ENGINEER_WATER_REFILLED,
            dest="option",
            help="Engineer: speaks water refilled",
        )

        tower = sp.add_parser("tower", aliases=["to"], help="Tower dialogs")
        tower_group = tower.add_mutually_exclusive_group()
        tower_group.add_argument(
            "-su",
            "-start_up",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_STARTUP,
            dest="option",
            help="Tower: first engine startup dialog",
        )
        tower_group.add_argument(
            "-sh",
            "-stop_hold",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_SPEED_STOP_HOLD,
            dest="option",
            help="Tower: first stop and hold dialog (non-emergency)",
        )
        tower_group.add_argument(
            "-sr",
            "-restricted_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_SPEED_RESTRICTED,
            dest="option",
            help="Tower: first restricted speed",
        )
        tower_group.add_argument(
            "-ss",
            "-std_step_to_data",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_SPEED_SLOW,
            dest="option",
            help="Tower: first slow speed",
        )
        tower_group.add_argument(
            "-sm",
            "-medium_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_SPEED_MEDIUM,
            dest="option",
            help="Tower: first medium speed",
        )
        tower_group.add_argument(
            "-sl",
            "-limited_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_SPEED_LIMITED,
            dest="option",
            help="Tower: first limited speed",
        )
        tower_group.add_argument(
            "-sn",
            "-normal_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_SPEED_NORMAL,
            dest="option",
            help="Tower: first normal speed",
        )
        tower_group.add_argument(
            "-sx",
            "-highball_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_SPEED_HIGHBALL,
            dest="option",
            help="Tower: first highball speed",
        )
        tower_group.add_argument(
            "-dd",
            "-departure_denied",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_DEPARTURE_DENIED,
            dest="option",
            help="Tower: departure denied",
        )
        tower_group.add_argument(
            "-dg",
            "-departure_granted",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_DEPARTURE_GRANTED,
            dest="option",
            help="Tower: departure granted",
        )
        tower_group.add_argument(
            "-de",
            "-departed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_DEPARTED,
            dest="option",
            help="Tower: departed",
        )
        tower_group.add_argument(
            "-ac",
            "-all_clear",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_ALL_CLEAR,
            dest="option",
            help="Tower: all clear",
        )
        tower_group.add_argument(
            "-ar",
            "-arriving",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_ARRIVING,
            dest="option",
            help="Tower: arriving",
        )
        tower_group.add_argument(
            "-ad",
            "-arrived",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_ARRIVED,
            dest="option",
            help="Tower: arrived",
        )
        tower_group.add_argument(
            "-sd",
            "-shutdown",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.TOWER_SHUTDOWN,
            dest="option",
            help="Tower: shut down",
        )
        seq = sp.add_parser("sequence", aliases=["sq"], help="Sequence control dialogs")
        seq_group = seq.add_mutually_exclusive_group()
        seq_group.add_argument(
            "-off",
            "-sequence_off",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.SEQUENCE_OFF,
            dest="option",
            help="SeqCtl: sequence control off",
        )
        seq_group.add_argument(
            "-on",
            "-sequence_on",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.SEQUENCE_ON,
            dest="option",
            help="SeqCtl: sequence control on",
        )
        seq_group.add_argument(
            "-c",
            "-clear",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.SEQUENCE_CLEAR,
            dest="option",
            help="SeqCtl: cleared out bound",
        )
        seq_group.add_argument(
            "-d",
            "-departed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.SEQUENCE_DEPARTED,
            dest="option",
            help="SeqCtl: have departed",
        )
        seq_group.add_argument(
            "-t",
            "-in_transit",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.SEQUENCE_TRANSIT,
            dest="option",
            help="SeqCtl: in transit",
        )
        seq_group.add_argument(
            "-x",
            "-max_speed",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.SEQUENCE_MAX_SPEED,
            dest="option",
            help="SeqCtl: max authorized speed",
        )

        cond = sp.add_parser("conductor", aliases=["co"], help="Conductor dialogs")
        cond_group = cond.add_mutually_exclusive_group()
        cond_group.add_argument(
            "-aa",
            "-all_aboard",
            action="store_const",
            const=TMCC2RailSoundsDialogControl.CONDUCTOR_ALL_ABOARD,
            dest="option",
            help="Conductor: all aboard",
        )

        return PyTrainArgumentParser(
            "Engine/train/car dialogs",
            parents=[dialog_parser, cls.multi_parser(), cls.train_parser(), cls.cli_parser()],
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        engine: int = self._args.engine
        option = self._args.option
        try:
            scope = self._determine_scope()
            cmd = DialogCmd(
                engine,
                TMCC2RailSoundsDialogControl(option),
                0,
                scope,
                baudrate=self._baudrate,
                port=self._port,
                server=self._server,
            )
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
