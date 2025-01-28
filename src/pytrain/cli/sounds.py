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
from ..protocol.multibyte.multibyte_constants import TMCC2RailSoundsEffectsControl
from ..protocol.multibyte.sound_effects_cmd import SoundEffectsCmd
from ..utils.argument_parser import PyTrainArgumentParser

log = logging.getLogger(__name__)


class SoundEffectsCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        sounds_parser = PyTrainArgumentParser(add_help=False)
        sounds_parser.add_argument("engine", metavar="Engine/Train", type=int, help="Engine/Train to control")
        sounds_parser.add_argument(
            "-add_fuel",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.ADD_FUEL,
            dest="option",
            help="Increment diesel fuel load by 10 gallons",
        )
        sounds_parser.add_argument(
            "-b+",
            "-blend_up",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.BLEND_UP,
            dest="option",
            help="Blend level up",
        )
        sounds_parser.add_argument(
            "-b-",
            "-blend_down",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.BLEND_DOWN,
            dest="option",
            help="Blend level down",
        )
        sounds_parser.add_argument(
            "-reset_odometer",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.RESET_ODOMETER,
            dest="option",
            help="Reset odometer to zero (0)",
        )
        sounds_parser.add_argument(
            "-wheel_slip",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.WHEEL_SLIP,
            dest="option",
            help="Wheel slip trigger",
        )
        sounds_parser.add_argument(
            "-m+",
            "-volume_up",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.VOLUME_UP_RS,
            dest="option",
            help="Increase master volume",
        )
        sounds_parser.add_argument(
            "-m-",
            "-volume_down",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.VOLUME_DOWN_RS,
            dest="option",
            help="Decrease master volume",
        )
        # sounds_parser.add_argument("-off",
        #                            action="store_const",
        #                            const='SOUND_OFF',
        #                            dest='option',
        #                            help="Turn all sounds off")
        # sounds_parser.add_argument("-on",
        #                            action="store_const",
        #                            const='SOUND_ON',
        #                            dest='option',
        #                            help="Turn all sounds on")

        sp = sounds_parser.add_subparsers(dest="sub_command", help="Engine/train sub-commands")

        breaker = sp.add_parser("breaker", aliases=["br"], help="Circuit Breaker RailSounds options")
        breaker_group = breaker.add_mutually_exclusive_group()
        breaker_group.add_argument(
            "-main",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.MAIN_BREAKER,
            dest="option",
            default=TMCC2RailSoundsEffectsControl.MAIN_BREAKER,
            help="Circuit Breaker sound - Main Lights",
        )
        breaker_group.add_argument(
            "-cab",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.CAB_BREAKER,
            dest="option",
            help="Circuit Breaker sound - CAB Lights",
        )
        breaker_group.add_argument(
            "-work_lights",
            "-ground_lights",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.WORK_BREAKER,
            dest="option",
            help="Circuit Breaker sound - Work/Ground Lights",
        )

        coupler = sp.add_parser("coupler", aliases=["co"], help="Coupler impact RailSounds options")
        coupler_group = coupler.add_mutually_exclusive_group()
        coupler_group.add_argument(
            "-compress",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.COUPLER_COMPRESS,
            dest="option",
            help="Force Coupler Impact - compress",
        )
        coupler_group.add_argument(
            "-stretch",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.COUPLER_STRETCH,
            dest="option",
            help="Force Coupler Impact - stretch",
        )

        cyl = sp.add_parser("cylinder", aliases=["cy"], help="Cylinder cock clearing RailSounds options")
        cyl_group = cyl.add_mutually_exclusive_group()
        cyl_group.add_argument(
            "-on",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.CYLINDER_ON,
            dest="option",
            default=TMCC2RailSoundsEffectsControl.CYLINDER_ON,
            help="Cylinder clearing sound on",
        )
        cyl_group.add_argument(
            "-off",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.CYLINDER_OFF,
            dest="option",
            help="Cylinder clearing sound off",
        )

        pm = sp.add_parser("prime_mover", aliases=["pm"], help="Prime mover RailSounds options")
        pm_group = pm.add_mutually_exclusive_group()
        pm_group.add_argument(
            "-on",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.PRIME_ON,
            dest="option",
            default=TMCC2RailSoundsEffectsControl.PRIME_ON,
            help="Prime mover sound on",
        )
        pm_group.add_argument(
            "-off",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.PRIME_OFF,
            dest="option",
            help="Prime mover sound off",
        )

        seq = sp.add_parser("sequence", aliases=["se"], help="Sequence control RailSounds options")
        seq_group = seq.add_mutually_exclusive_group()
        seq_group.add_argument(
            "-on",
            "-enable",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.SEQUENCE_CONTROL_ON,
            dest="option",
            default=TMCC2RailSoundsEffectsControl.SEQUENCE_CONTROL_ON,
            help="Enable RailSounds sequence control",
        )
        seq_group.add_argument(
            "-off",
            "-disable",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.SEQUENCE_CONTROL_OFF,
            dest="option",
            help="Disable RailSounds sequence control",
        )

        standby = sp.add_parser("standby", aliases=["st"], help="Standby mode RailSounds options")
        standby_group = standby.add_mutually_exclusive_group()
        standby_group.add_argument(
            "-on",
            "-enable",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.STANDBY_ENABLE,
            dest="option",
            default=TMCC2RailSoundsEffectsControl.STANDBY_ENABLE,
            help="Enable RailSounds standby mode",
        )
        standby_group.add_argument(
            "-off",
            "-disable",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.STANDBY_DISABLE,
            dest="option",
            help="Disable RailSounds standby mode",
        )
        standby_group.add_argument(
            "-warning_bell",
            action="store_const",
            const=TMCC2RailSoundsEffectsControl.STANDBY_BELL,
            dest="option",
            help="Standby warning bell on",
        )

        return PyTrainArgumentParser(
            "RailSounds sound controls",
            parents=[sounds_parser, cls.multi_parser(), cls.train_parser(), cls.cli_parser()],
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        engine: int = self._args.engine
        option = self._args.option
        try:
            scope = self._determine_scope()
            cmd = SoundEffectsCmd(
                engine,
                TMCC2RailSoundsEffectsControl(option),
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
