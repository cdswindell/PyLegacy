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
        sp = effects_parser.add_subparsers(dest="sub_command", help="Effects sub-commands")

        coal = sp.add_parser("coal", aliases=["co"], help="Pantograph options")
        coal_group = coal.add_mutually_exclusive_group()
        coal_group.add_argument(
            "-empty",
            action="store_const",
            const=TMCC2EffectsControl.COAL_EMPTY,
            dest="option",
            help="Coal empty effect",
        )
        coal_group.add_argument(
            "-filling",
            action="store_const",
            const=TMCC2EffectsControl.COAL_FILLING,
            dest="option",
            help="Coal filling effect",
        )
        coal_group.add_argument(
            "-full",
            action="store_const",
            const=TMCC2EffectsControl.COAL_FULL,
            dest="option",
            help="Coal full effect",
        )
        coal_group.add_argument(
            "-unloading",
            action="store_const",
            const=TMCC2EffectsControl.COAL_EMPTYING,
            dest="option",
            help="Coal emptying/unloading effect",
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
            help="Pantograph control - both up",
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
        scene = sp.add_parser("scene", aliases=["sc"], help="Stock car scenes")
        scene.add_argument(
            "scene_no",
            type=int,
            action="store",
            choices=range(0, 4),
            help="Scene 0, 1, 2, or 3",
        )
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
        stock = sp.add_parser("stock", aliases=["st"], help="Stock car options")
        stock_group = stock.add_mutually_exclusive_group()
        stock_group.add_argument(
            "-load",
            action="store_const",
            const=TMCC2EffectsControl.STOCK_LOAD,
            dest="option",
            help="Load stock car",
        )
        stock_group.add_argument(
            "-unload",
            action="store_const",
            const=TMCC2EffectsControl.STOCK_UNLOAD,
            dest="option",
            help="Unload stock car",
        )
        stock_group.add_argument(
            "-fred",
            choices=["on", "off"],
            nargs="?",
            type=str,
            dest="fred",
            const="on",
            help="Stock car FRED on/off",
        )
        stock_group.add_argument(
            "-game",
            choices=["on", "off"],
            nargs="?",
            type=str,
            dest="game",
            const="on",
            help="Stock car game mode on/off",
        )
        stock_group.add_argument(
            "-wheel",
            choices=["on", "off"],
            nargs="?",
            type=str,
            dest="flat_wheel",
            const="on",
            help="Stock car flat wheel effect on/off",
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
            help="Subway both doors open",
        )
        subway_group.add_argument(
            "-bc",
            "--both_close",
            action="store_const",
            const=TMCC2EffectsControl.SUBWAY_BOTH_DOOR_CLOSE,
            dest="option",
            help="Subway both doors close",
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

        # TODO: Coal options

        return PyTrainArgumentParser(
            "Engine/train/car effects control",
            parents=[effects_parser, cls.multi_parser(), cls.train_parser(), cls.cli_parser()],
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        engine: int = self._args.engine
        option = self._args.option if "option" in self._args else None
        try:
            scope = self._determine_scope()
            if option is None:
                if self._args.sub_command.startswith("st"):
                    if self._args.game:
                        option = (
                            TMCC2EffectsControl.STOCK_GAME_ON
                            if self._args.game == "on"
                            else TMCC2EffectsControl.STOCK_GAME_OFF
                        )
                    if self._args.flat_wheel:
                        option = (
                            TMCC2EffectsControl.STOCK_WHEEL_ON
                            if self._args.flat_wheel == "on"
                            else TMCC2EffectsControl.STOCK_WHEEL_OFF
                        )
                    if self._args.fred:
                        option = (
                            TMCC2EffectsControl.STOCK_FRED_ON
                            if self._args.fred == "on"
                            else TMCC2EffectsControl.STOCK_FRED_OFF
                        )
                elif self._args.sub_command.startswith("sc") and self._args.scene_no is not None:
                    if self._args.scene_no == 0:
                        option = TMCC2EffectsControl.STOCK_SCENE_ZERO
                    elif self._args.scene_no == 1:
                        option = TMCC2EffectsControl.STOCK_SCENE_ONE
                    elif self._args.scene_no == 2:
                        option = TMCC2EffectsControl.STOCK_SCENE_TWO
                    elif self._args.scene_no == 3:
                        option = TMCC2EffectsControl.STOCK_SCENE_THREE
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
