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

from . import CliBaseTMCC
from ..protocol.multibyte.effects_cmd import EffectsCmd
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..utils.argument_parser import PyTrainArgumentParser

log = logging.getLogger(__name__)


class EffectsCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        effects_parser = PyTrainArgumentParser(add_help=False)
        effects_parser.add_argument("engine", metavar="Engine/Train", type=int, help="Engine/Train to control")
        sp = effects_parser.add_subparsers(dest="sub_command", help="Engine/train sub-commands")
        smoke = sp.add_parser("smoke", aliases=["sm"], help="Smoke system options")
        smoke_group = smoke.add_mutually_exclusive_group()
        smoke_group.add_argument(
            "-low",
            action="store_const",
            const=TMCC2EffectsControl.SMOKE_LOW,
            dest="option",
            default=TMCC2EffectsControl.SMOKE_LOW,
            help="Smoke system low",
        )
        smoke_group.add_argument(
            "-medium",
            action="store_const",
            const=TMCC2EffectsControl.SMOKE_MEDIUM,
            dest="option",
            help="Smoke system medium",
        )
        smoke_group.add_argument(
            "-high",
            "-maximum",
            action="store_const",
            const=TMCC2EffectsControl.SMOKE_HIGH,
            dest="option",
            help="Smoke system high",
        )
        smoke_group.add_argument(
            "-off", action="store_const", const=TMCC2EffectsControl.SMOKE_OFF, dest="option", help="Smoke system off"
        )

        panto = sp.add_parser("pantograph", aliases=["pa"], help="Pantograph options")
        panto_group = panto.add_mutually_exclusive_group()
        panto_group.add_argument(
            "-fu",
            "--front_up",
            action="store_const",
            const=TMCC2EffectsControl.PANTO_FRONT_UP,
            dest="option",
            default=TMCC2EffectsControl.PANTO_FRONT_UP,
            help="Pantograph control - front up",
        )
        panto_group.add_argument(
            "-fd",
            "--front_down",
            action="store_const",
            const=TMCC2EffectsControl.PANTO_FRONT_DOWN,
            dest="option",
            help="Pantograph control - front down",
        )
        panto_group.add_argument(
            "-bu",
            "--both_up",
            action="store_const",
            const=TMCC2EffectsControl.PANTO_BOTH_UP,
            dest="option",
            help="Pantograph control -both up",
        )
        panto_group.add_argument(
            "-bd",
            "--both_down",
            action="store_const",
            const=TMCC2EffectsControl.PANTO_BOTH_DOWN,
            dest="option",
            help="Pantograph control - both down",
        )
        panto_group.add_argument(
            "-ru",
            "--rear_up",
            action="store_const",
            const=TMCC2EffectsControl.PANTO_REAR_UP,
            dest="option",
            help="Pantograph control - rear up",
        )
        panto_group.add_argument(
            "-rd",
            "--rear_down",
            action="store_const",
            const=TMCC2EffectsControl.PANTO_REAR_DOWN,
            dest="option",
            help="Pantograph control - rear down",
        )

        subway = sp.add_parser("subway", aliases=["su"], help="Subway door options")
        subway_group = subway.add_mutually_exclusive_group()
        subway_group.add_argument(
            "-lo",
            "--left_open",
            action="store_const",
            const=TMCC2EffectsControl.SUBWAY_LEFT_DOOR_OPEN,
            dest="option",
            default=TMCC2EffectsControl.SUBWAY_LEFT_DOOR_OPEN,
            help="Subway left door open",
        )
        subway_group.add_argument(
            "-lc",
            "--left_close",
            action="store_const",
            const=TMCC2EffectsControl.SUBWAY_LEFT_DOOR_CLOSE,
            dest="option",
            help="Subway left door close",
        )
        subway_group.add_argument(
            "-bo",
            "--both_open",
            action="store_const",
            const=TMCC2EffectsControl.SUBWAY_BOTH_DOOR_OPEN,
            dest="option",
            help="Subway both door open",
        )
        subway_group.add_argument(
            "-bc",
            "--both_close",
            action="store_const",
            const=TMCC2EffectsControl.SUBWAY_BOTH_DOOR_CLOSE,
            dest="option",
            help="Subway both door close",
        )
        subway_group.add_argument(
            "-ro",
            "--right_open",
            action="store_const",
            const=TMCC2EffectsControl.SUBWAY_RIGHT_DOOR_OPEN,
            dest="option",
            help="Subway right door open",
        )
        subway_group.add_argument(
            "-rc",
            "--right_close",
            action="store_const",
            const=TMCC2EffectsControl.SUBWAY_RIGHT_DOOR_CLOSE,
            dest="option",
            help="Subway right door close",
        )
        # TODO: Coal and stock car options

        return PyTrainArgumentParser(
            "Engine/train/car effects control",
            parents=[effects_parser, cls.multi_parser(), cls.train_parser(), cls.cli_parser()],
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        engine: int = self._args.engine
        option = self._args.option
        try:
            scope = self._determine_scope()
            cmd = EffectsCmd(
                engine,
                TMCC2EffectsControl(option),
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
