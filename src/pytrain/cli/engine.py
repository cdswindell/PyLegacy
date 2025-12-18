#!/usr/bin/env python3

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

#
import logging
from argparse import ArgumentError, ArgumentParser
from typing import List

from ..protocol.constants import CommandScope, CommandSyntax
from ..protocol.multibyte.multibyte_constants import (
    TMCC2EffectsControl,
    TMCC2LightingControl,
    TMCC2MultiByteEnum,
    TMCC2RailSoundsDialogControl,
    TMCC2RailSoundsEffectsControl,
    TMCC2VariableEnum,
)
from ..protocol.sequence.sequence_constants import SequenceCommandEnum
from ..protocol.tmcc1.engine_cmd import EngineCmd as EngineCmdTMCC1
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum, TMCC1RRSpeedsEnum
from ..protocol.tmcc2.engine_cmd import EngineCmd as EngineCmdTMCC2
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2RRSpeedsEnum
from ..utils.argument_parser import PyTrainArgumentParser, ranged_int
from . import CliBase, CliBaseTMCC, DataAction

log = logging.getLogger(__name__)

AUX_COMMAND_MAP = {
    "on": "_ON",
    "off": "_OFF",
    "opt1": "_OPTION_ONE",
    "opt2": "_OPTION_TWO",
}


class EngineCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls) -> ArgumentParser:
        engine_parser = PyTrainArgumentParser(add_help=False)
        engine_parser.add_argument("engine", metavar="Engine/Train", type=int, help="Engine/Train to operate")

        ops = engine_parser.add_mutually_exclusive_group()
        ops.add_argument(
            "-a", "-set_address", action="store_const", const="SET_ADDRESS", dest="option", help="Set engine address"
        )

        ops.add_argument("-aux1", dest="aux1", choices=["on", "off", "opt1", "opt2"], nargs="?", type=str, const="opt1")
        ops.add_argument("-aux2", dest="aux2", choices=["on", "off", "opt1", "opt2"], nargs="?", type=str, const="opt1")
        ops.add_argument("-aux3", dest="aux3", choices=["on", "off", "opt1", "opt2"], nargs="?", type=str, const="opt1")
        ops.add_argument(
            "-b", "-blow_horn", action="store_const", const="BLOW_HORN_ONE", dest="option", help="Blow horn"
        )
        ops.add_argument(
            "-bl",
            "-boost_level",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=3,
            const="BOOST_LEVEL",
            help="Boost level",
        )
        ops.add_argument(
            "-br", "-brake_speed", action="store_const", const="BRAKE_SPEED", dest="option", help="Boost speed"
        )
        ops.add_argument(
            "-bs", "-boost_speed", action="store_const", const="BOOST_SPEED", dest="option", help="Brake speed"
        )
        ops.add_argument(
            "-fc",
            "-front_coupler",
            action="store_const",
            const="FRONT_COUPLER",
            dest="option",
            help="Open front coupler",
        )
        ops.add_argument(
            "-fwd",
            "-forward_direction",
            action="store_const",
            const="FORWARD_DIRECTION",
            dest="option",
            help="Set forward direction",
        )
        ops.add_argument(
            "-hiss",
            "-cylinder_hiss",
            action="store_const",
            const="CYLINDER_HISS",
            dest="option",
            help="Cylinder cock hiss sound",
        )
        ops.add_argument(
            "-kl",
            "-brake_level",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            type=ranged_int(0, 7),
            nargs="?",
            default=3,
            const="BRAKE_LEVEL",
            help="Brake level (0-7)",
        )
        ops.add_argument(
            "-l",
            "-engine_labor",
            action=DataAction,
            dest="option",
            choices=range(0, 32),
            type=ranged_int(0, 31),
            nargs="?",
            default=0,
            const="ENGINE_LABOR",
            help="Engine labor (0 - 31)",
        )
        ops.add_argument(
            "-n",
            action=DataAction,
            dest="option",
            choices=range(0, 10),
            metavar="0 - 9",
            type=ranged_int(0, 9),
            nargs="?",
            default=7,  # random radio chatter
            const="NUMERIC",
            help="Send numeric value",
        )
        ops.add_argument(
            "-pm",
            "-prime_mover",
            choices=["on", "off"],
            nargs="?",
            type=str,
            dest="prime_mover",
            const="on",
            help="Prime mover sound on/off",
        )
        ops.add_argument(
            "-pop",
            "-pop_off",
            action="store_const",
            const="POP_OFF",
            dest="option",
            help="Pop off sounds",
        )
        ops.add_argument("-r", "-ring_bell", action="store_const", const="RING_BELL", dest="option", help="Ring bell")
        ops.add_argument("-reset", action="store_const", const="RESET", dest="option", help="Reset engine/train")
        ops.add_argument(
            "-rc", "-rear_coupler", action="store_const", const="REAR_COUPLER", dest="option", help="Open rear coupler"
        )
        ops.add_argument(
            "-rev",
            "-reverse_direction",
            action="store_const",
            const="REVERSE_DIRECTION",
            dest="option",
            help="Set reverse direction",
        )
        ops.add_argument(
            "-rpm",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=0,
            const="DIESEL_RPM",
            help="Diesel RPM Level",
        )
        ops.add_argument(
            "-s", "-stop_immediate", action="store_const", const="STOP_IMMEDIATE", dest="option", help="Stop immediate"
        )
        ops.add_argument("-stall", action="store_const", const="STALL", dest="option", help="Set stall")
        ops.add_argument(
            "-sdd",
            "-shutdown_delayed",
            action="store_const",
            const="SHUTDOWN_DELAYED",
            dest="option",
            help="Shutdown delayed with announcement",
        )
        ops.add_argument(
            "-sdi",
            "-shutdown_immediate",
            action="store_const",
            const="SHUTDOWN_IMMEDIATE",
            dest="option",
            help="Shutdown Immediate",
        )
        ops.add_argument(
            "-sound",
            choices=["on", "off"],
            nargs="?",
            type=str,
            const="on",
            dest="sound",
            help="Sound on/off",
        )
        ops.add_argument(
            "-sq",
            "-sequence_control",
            choices=["on", "off"],
            nargs="?",
            type=str,
            const="on",
            dest="sequence_control",
            help="Sequence control on/off",
        )
        ops.add_argument(
            "-sud",
            "-start_up_delayed",
            action="store_const",
            const="START_UP_DELAYED",
            dest="option",
            help="Start up delayed (prime mover)",
        )
        ops.add_argument(
            "-sui",
            "-start_up_immediate",
            action="store_const",
            const="START_UP_IMMEDIATE",
            dest="option",
            help="Start up immediate",
        )
        ops.add_argument(
            "-t",
            "-toggle_direction",
            action="store_const",
            const="TOGGLE_DIRECTION",
            dest="option",
            help="Toggle direction",
        )
        ops.add_argument(
            "-tb",
            "-train_brake",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=1,
            const="TRAIN_BRAKE",
            help="Train brake",
        )
        ops.add_argument(
            "-v-", "-volume_down", action="store_const", const="VOLUME_DOWN", dest="option", help="Master volume down"
        )
        ops.add_argument(
            "-v+", "-volume_up", action="store_const", const="VOLUME_UP", dest="option", help="Master volume up"
        )

        # create subparsers to handle train/engine-specific operations
        sp = engine_parser.add_subparsers(dest="sub_command", help="Engine/train sub-commands")

        # Bell operations
        bell = sp.add_parser("bell", aliases=["be"], help="Bell operations", parent=engine_parser)
        bell_group = bell.add_mutually_exclusive_group()
        bell_group.add_argument(
            "-r",
            "-ring",
            action="store_const",
            const="RING_BELL",
            dest="option",
            default="RING_BELL",
            help="Ring bell",
        )
        bell_group.add_argument("-on", action="store_const", const="BELL_ON", dest="option", help="Turn bell on")
        bell_group.add_argument("-off", action="store_const", const="BELL_OFF", dest="option", help="Turn bell off")
        bell_group.add_argument(
            "-d",
            "-ding",
            action=DataAction,
            dest="option",
            choices=range(0, 4),
            metavar="0 - 3",
            type=int,
            nargs="?",
            default=3,
            const="BELL_ONE_SHOT_DING",
            help="Bell one shot ding",
        )
        bell_group.add_argument(
            "-s",
            "-slider",
            action=DataAction,
            dest="option",
            choices=range(2, 6),
            metavar="2 - 5",
            type=int,
            nargs="?",
            default=2,
            const="BELL_SLIDER_POSITION",
            help="Bell slider position",
        )

        # Horn operations
        horn = sp.add_parser("horn", aliases=["ho"], help="Horn operations", parent=engine_parser)
        horn_group = horn.add_mutually_exclusive_group()
        horn_group.add_argument(
            "-1",
            "-blow_horn_one",
            action="store_const",
            const="BLOW_HORN_ONE",
            dest="option",
            default="BLOW_HORN_ONE",
            help="Blow horn one",
        )
        horn_group.add_argument(
            "-2", "-blow_horn_two", action="store_const", const="BLOW_HORN_TWO", dest="option", help="Blow horn two"
        )
        horn_group.add_argument(
            "-grade_crossing",
            action="store_const",
            const="GRADE_CROSSING_SEQ",
            dest="option",
            help="Grade crossing horn sequence",
        )
        horn_group.add_argument(
            "-i",
            "-intensity",
            action=DataAction,
            dest="option",
            choices=range(0, 16),
            metavar="0 - 15",
            type=ranged_int(0, 15),
            nargs="?",
            default=1,
            const="QUILLING_HORN",
            help="Quilling horn intensity",
        )

        # Momentum operations
        momentum = sp.add_parser("momentum", aliases=["mo"], help="Momentum operations", parent=engine_parser)
        mom_group = momentum.add_mutually_exclusive_group()
        mom_group.add_argument(
            "-low",
            action="store_const",
            const="MOMENTUM_LOW",
            dest="option",
            default="MOMENTUM_MEDIUM",  # strange, but default actions only applied if placed
            help="Set momentum to low",
        )  # on first argument of mutual group
        mom_group.add_argument(
            "-medium",
            action="store_const",
            const="MOMENTUM_MEDIUM",
            dest="option",
            help="Set momentum to medium",
        )
        mom_group.add_argument(
            "-high",
            "-maximum",
            "-x",
            action="store_const",
            const="MOMENTUM_HIGH",
            dest="option",
            help="Set momentum to high",
        )
        mom_group.add_argument("-off", action="store_const", const="MOMENTUM", dest="option", help="Set momentum off")

        mom_group.add_argument(
            "-absolute",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=0,
            const="MOMENTUM",
            help="Set absolute momentum",
        )

        # Smoke operations
        smoke = sp.add_parser("smoke", aliases=["sm"], help="Smoke operations", parent=engine_parser)
        smoke_group = smoke.add_mutually_exclusive_group()
        smoke_group.add_argument(
            "-low",
            action="store_const",
            const="SMOKE_LOW",
            dest="option",
            default="SMOKE_LOW",  # strange, but default actions only applied if placed
            help="Set smoke level to low",
        )  # on first argument of mutual group
        smoke_group.add_argument(
            "-medium",
            action="store_const",
            const="SMOKE_MEDIUM",
            dest="option",
            help="Set smoke level to medium",
        )
        smoke_group.add_argument(
            "-high",
            "-maximum",
            "-x",
            action="store_const",
            const="SMOKE_HIGH",
            dest="option",
            help="Set smoke level to high",
        )
        smoke_group.add_argument("-off", action="store_const", const="SMOKE_OFF", dest="option", help="Set smoke off")

        sound = sp.add_parser("sound", aliases=["so"], help="Sound operations", parent=engine_parser)
        sound_group = sound.add_mutually_exclusive_group()
        sound_group.add_argument("-auger", action="store_const", const="AUGER", dest="option", help="Auger sound")
        sound_group.add_argument(
            "-b", "-brake_squeal", action="store_const", const="BRAKE_SQUEAL", dest="option", help="Brake squeal sound"
        )
        sound_group.add_argument(
            "-r",
            "-brake_air_release",
            action="store_const",
            const="BRAKE_AIR_RELEASE",
            dest="option",
            help="Brake air release sound",
        )
        sound_group.add_argument(
            "-rpm",
            "-diesel_rpm",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=0,
            const="DIESEL_RPM",
            help="Diesel run level sound",
        )
        sound_group.add_argument(
            "-f",
            "-fu",
            "-fue",
            "-fuel",
            "-refueling",
            action="store_const",
            const="REFUELLING",
            dest="option",
            help="Refueling sound",
        )
        sound_group.add_argument(
            "-l", "-let_off", action="store_const", const="LET_OFF", dest="option", help="Short let-off sound"
        )
        sound_group.add_argument(
            "-ll",
            "-long_let_off",
            action="store_const",
            const="LET_OFF_LONG",
            dest="option",
            help="Long let-off sound",
        )
        sound_group.add_argument(
            "-water_injector",
            action="store_const",
            const="WATER_INJECTOR",
            dest="option",
            help="Water injector sound",
        )
        sound_group.add_argument(
            "-off", action="store_const", const="SOUND_OFF", dest="option", help="Turn all sounds off"
        )
        sound_group.add_argument(
            "-on", action="store_const", const="SOUND_ON", dest="option", help="Turn all sounds on"
        )

        # Speed operations
        sp_metavar = (
            "Engine/Train speed: 0 - 199 (Legacy) or 0 - 31 (TMCC) or stop, roll, restricted, "
            "slow, medium, limited, normal, or highball"
        )
        speed = sp.add_parser("speed", aliases=["sp"], help="Speed of engine/train", parent=engine_parser)
        speed.add_argument(
            "data", type=CliBase._validate_speed, action="store", metavar=sp_metavar, help="Absolute/Relative speed"
        )

        speed.add_argument(
            "-dialog",
            action="store_const",
            const="RAMPED_SPEED_DIALOG_SEQ",
            dest="option",
            help="Trigger tower/engineer dialog",
        )

        speed_group = speed.add_mutually_exclusive_group()
        speed_group.add_argument(
            "-absolute",
            action="store_const",
            const="RAMPED_SPEED_SEQ",
            dest="option",
            help="Set absolute speed (using ramp)",
        )
        speed_group.add_argument(
            "-immediate",
            action="store_const",
            const="SET_SPEED_RPM",
            dest="option",
            help="Set absolute speed (immediate)",
        )
        speed_group.add_argument(
            "-relative",
            action="store_const",
            const="RELATIVE_SPEED",
            dest="option",
            help="Set relative speed (-5 to 5)",
        )
        speed_group.set_defaults(option="RAMPED_SPEED_SEQ")

        volume = sp.add_parser("volume", aliases=["vo"], help="Volume Operations", parent=engine_parser)
        vg = volume.add_mutually_exclusive_group()

        vg.add_argument(
            "-bell",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=4,
            const="BELL_DIRECT",
            help="Set bell volume (0 - 7)",
        )
        vg.add_argument(
            "-blend",
            action=DataAction,
            dest="option",
            choices=range(0, 256),
            metavar="0 - 255",
            type=ranged_int(0, 255),
            nargs="?",
            default=128,
            const="BLEND_VOLUME",
            help="Set blend volume (0 - 255)",
        )
        vg.add_argument(
            "-dialog",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=4,
            const="DIALOG_DIRECT",
            help="Set dialog volume (0 - 7)",
        )
        vg.add_argument(
            "-horn",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=4,
            const="HORN_DIRECT",
            help="Set horn volume (0 - 7)",
        )
        vg.add_argument(
            "-master",
            action=DataAction,
            dest="option",
            choices=range(0, 256),
            metavar="0 - 255",
            type=ranged_int(0, 255),
            nargs="?",
            default=128,
            const="MASTER_VOLUME",
            help="Set master volume (0 - 255)",
        )
        vg.add_argument(
            "-md",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=4,
            const="MASTER_DIRECT",
            help="Set master volume direct (0 - 7)",
        )
        vg.add_argument(
            "-bd",
            action=DataAction,
            dest="option",
            choices=range(0, 8),
            metavar="0 - 7",
            type=ranged_int(0, 7),
            nargs="?",
            default=4,
            const="BLEND_DIRECT",
            help="Set blend volume direct (0 - 7)",
        )
        vg.add_argument(
            "-info",
            action="store_const",
            dest="option",
            const="GET_INFO",
            help="Get Info",
        )
        vg.add_argument(
            "-status",
            action="store_const",
            dest="option",
            const="GET_STATUS",
            help="Get Status",
        )

        # construct final parser with all components in order
        return PyTrainArgumentParser(
            "Control specified engine/train (1 - 99)",
            parents=[
                engine_parser,
                cls.multi_parser(),
                cls.train_parser(),
                cls.command_format_parser(),
                cls.cli_parser(),
            ],
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        engine: int = self._args.engine
        try:
            scope = self._determine_scope()
            self._determine_command_format(scope, engine)
            option = self._decode_engine_option()  # raise ValueError if you can't decode
            if option is None:
                raise ValueError("Must specify an option, use -h for help")
            option_data: int = self._args.data if "data" in self._args else 0

            if self.is_tmcc2 or option.is_tmcc2:
                cmd = EngineCmdTMCC2(
                    engine, option, option_data, scope, baudrate=self._baudrate, port=self._port, server=self._server
                )
            else:
                cmd = EngineCmdTMCC1(
                    engine,
                    TMCC1EngineCommandEnum(option),
                    option_data,
                    scope,
                    baudrate=self._baudrate,
                    port=self._port,
                    server=self._server,
                )
            if self.do_fire:
                cmd.fire(
                    repeat=self._args.repeat,
                    delay=self._args.delay,
                    baudrate=self._baudrate,
                    port=self._port,
                    server=self._server,
                )
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)

    def _determine_command_format(self, scope: CommandScope, tmcc_id: int) -> None:
        if "format" in self._args and self._args.format:
            pass  # use user-provided format
        else:
            from ..db.component_state_store import ComponentStateStore

            state = ComponentStateStore.get_state(scope, tmcc_id, False)
            if state and state.is_legacy:
                self._command_format = CommandSyntax.LEGACY
            else:
                self._command_format = CommandSyntax.TMCC

    def _decode_engine_option(self) -> TMCC1EngineCommandEnum | TMCC2EngineCommandEnum | TMCC2MultiByteEnum | None:
        """
        Decode the 'option' argument, if present, into a valid
        TMCC1EngineCommandDef, TMCC2EngineCommandDef, or one of the multiword TMCC2
        parameter enums. Use the specified command format, if present, to help resolve,
        as the enum classes share element names
        """
        if "option" not in self._args:
            return None

        # if option is None, check if an aux command was specified via
        # the aux1/aux2 arguments; only one should have a value
        option = self._args.option
        if not option or not option.strip():
            # construct the EngineOptionEnum by prepending the aux choice
            # (AUX1/AUX2) to the suffix based on the argument value
            # (on, off, opt1, opt2)
            if "aux1" in self._args and self._args.aux1 is not None:
                option = f"AUX1{AUX_COMMAND_MAP[self._args.aux1.lower()]}"
            elif "aux2" in self._args and self._args.aux2 is not None:
                option = f"AUX2{AUX_COMMAND_MAP[self._args.aux2.lower()]}"
            elif "aux3" in self._args and self._args.aux3 is not None:
                option = f"AUX3{AUX_COMMAND_MAP[self._args.aux3.lower()]}"
            elif "sound" in self._args and self._args.sound is not None:
                option = f"sound_{self._args.sound}".upper()
            elif "sequence_control" in self._args and self._args.sequence_control is not None:
                option = f"sequence_control_{self._args.sequence_control}".upper()
            elif "prime_mover" in self._args:
                if self._args.prime_mover is not None:
                    option = f"prime_{self._args.prime_mover}".upper()
                else:
                    raise ArgumentError(None, "Must specify 'on' or 'off', for -prime_mover; use -h for help")
            else:
                raise ArgumentError(None, "Must specify a valid option, use -h for help")
        else:
            option = str(option).strip().upper()

        # reset option in args, for display purposes
        self._args.option = option

        # vet data argument, if string
        if "data" in self._args and isinstance(self._args.data, str):
            rr_enums = TMCC2RRSpeedsEnum if self.is_tmcc2 else TMCC1RRSpeedsEnum
            rr_value = rr_enums.by_name(self._args.data, False)
            if rr_value is None:
                raise ArgumentError(None, f"Invalid speed: {self._args.data}")
            self._args.data = min(rr_value.value)

        # if scope is TMCC1, resolve via TMCC1EngineCommandDef
        if self.is_tmcc1:
            enum_classes = [TMCC1EngineCommandEnum, SequenceCommandEnum]
        else:
            enum_classes = [
                TMCC2EngineCommandEnum,
                TMCC2RailSoundsDialogControl,
                TMCC2RailSoundsEffectsControl,
                TMCC2EffectsControl,
                TMCC2LightingControl,
                TMCC2VariableEnum,
                SequenceCommandEnum,
            ]
        for enum_class in enum_classes:
            if option in dir(enum_class):
                return enum_class[option]
        raise ArgumentError(None, f"Invalid {self.command_format.name} option: {option}")
