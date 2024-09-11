#!/usr/bin/env python3
#
import argparse
import sys
from typing import Any

from src.cli.cli_base import CliBaseTMCC, DataAction, cli_parser, command_format_parser, train_parser
from src.protocol.constants import CommandDefEnum, TMCC1EngineCommandDef, TMCC2EngineCommandDef
from src.protocol.constants import TMCC2_SPEED_MAP, TMCC1_SPEED_MAP
from src.protocol.tmcc1.engine_cmd import EngineCmd as EngineCmdTMCC1
from src.protocol.tmcc2.engine_cmd import EngineCmd as EngineCmdTMCC2

AUX_COMMAND_MAP = {
    'on': '_ON',
    'off': '_OFF',
    'opt1': '_OPTION_ONE',
    "opt2": "_OPTION_TWO",
}


class EngineCli(CliBaseTMCC):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        engine: int = self._args.engine
        option_data: int = self._args.data if 'data' in self._args else 0
        try:
            option: CommandDefEnum = self._decode_engine_option()  # raise ValueError if can't decode
            if option is None:
                raise ValueError("Must specify an command_def, use -h for help")
            print(self._args)
            scope = self._determine_scope()
            if self.is_tmcc2 or isinstance(option, TMCC2EngineCommandDef):
                cmd = EngineCmdTMCC2(engine,
                                     TMCC2EngineCommandDef(option),
                                     option_data,
                                     scope,
                                     baudrate=self._args.baudrate,
                                     port=self._args.port)
            else:
                cmd = EngineCmdTMCC1(engine,
                                     TMCC1EngineCommandDef(option),
                                     option_data,
                                     scope,
                                     baudrate=self._args.baudrate,
                                     port=self._args.port)
            cmd.fire(repeat=self._args.repeat, delay=self._args.delay)
        except ValueError as ve:
            print(ve)

    def _decode_engine_option(self) -> CommandDefEnum | None:
        """
            Decode the 'command_def' argument, if present, into a valid
            TMCC1EngineCommandDef or TMCC2EngineCommandDef enum. Use the specified
            command format, if present, to help resolve, as the two enum
            classes share element names
        """
        if 'command_def' not in self._args:
            return None

        # if command_def is None, check if an aux command was specified via
        # the aux1/aux2 arguments; only one should have a value
        option = self._args.command_def
        if not option or not option.strip():
            # construct the EngineOptionEnum by prepending the aux choice
            # (AUX1/AUX2) to the suffix based on the argument value
            # (on, off, opt1, opt2)
            if 'aux1' in self._args and self._args.aux1 is not None:
                option = f"AUX1{AUX_COMMAND_MAP[self._args.aux1.lower()]}"
            elif 'aux2' in self._args and self._args.aux2 is not None:
                option = f"AUX2{AUX_COMMAND_MAP[self._args.aux2.lower()]}"
            else:
                raise ValueError("Must specify an command_def, use -h for help")
        else:
            option = str(option).strip().upper()

        # reset command_def in args, for display purposes
        self._args.command_def = option

        # if scope is TMCC1, resolve via TMCC1EngineCommandDef
        if self.is_tmcc1:
            enum_class = TMCC1EngineCommandDef
        else:
            enum_class = TMCC2EngineCommandDef
        if option in dir(enum_class):
            return enum_class[option]
        else:
            raise ValueError(f'Invalid {self.command_format.name} command_def: {option}')


def _validate_speed(arg: Any) -> int:
    try:
        return int(arg)  # try convert to int
    except ValueError:
        pass
    uc_arg = str(arg).upper()
    if uc_arg in TMCC2_SPEED_MAP:
        # feels a little hacky, but need a way to use a different map for TMCC commands
        if '-tmcc' in sys.argv or '--tmcc1' in sys.argv:
            return TMCC1_SPEED_MAP[uc_arg]
        return TMCC2_SPEED_MAP[uc_arg]
    raise argparse.ArgumentTypeError("Speed must be between 0 and 199 (0 and 31, for tmcc)")


def _validate_delay(arg: Any) -> int:
    try:
        arg = int(arg)  # try convert to int
        if arg >= 0:
            return arg
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Delay must be 0 or greater")


def _validate_repeat(arg: Any) -> int:
    try:
        arg = int(arg)  # try convert to int
        if arg > 0:
            return arg
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Delay must be 1 or greater")


if __name__ == '__main__':
    engine_parser = argparse.ArgumentParser(add_help=False)
    engine_parser.add_argument("engine",
                               metavar='Engine/Train',
                               type=int,
                               help="Engine/Train to operate")
    engine_parser.add_argument("-re", "--repeat",
                               action="store",
                               type=_validate_repeat,
                               default=1,
                               help="Number of times to repeat command (default: 1)")

    engine_parser.add_argument("-de", "--delay",
                               action="store",
                               type=_validate_delay,
                               default=0,
                               help="Second(s) to delay between repeated commands (default: 0)")

    ops = engine_parser.add_mutually_exclusive_group()
    ops.add_argument("-a", "--set_address",
                     action="store_const",
                     const='SET_ADDRESS',
                     dest='command_def',
                     help="Set engine address")

    ops.add_argument("-s", "--stop_immediate",
                     action="store_const",
                     const='STOP_IMMEDIATE',
                     dest='command_def',
                     help="Stop immediate")

    ops.add_argument("-fwd", "--forward_direction",
                     action="store_const",
                     const='FORWARD_DIRECTION',
                     dest='command_def',
                     help="Set forward direction")

    ops.add_argument("-rev", "--reverse_direction",
                     action="store_const",
                     const='REVERSE_DIRECTION',
                     dest='command_def',
                     help="Set reverse direction")

    ops.add_argument("-t", "--toggle_direction",
                     action="store_const",
                     const='TOGGLE_DIRECTION',
                     dest='command_def',
                     help="Toggle direction")

    ops.add_argument("-fc", "--front_coupler",
                     action="store_const",
                     const='FRONT_COUPLER',
                     dest='command_def',
                     help="Open front coupler")

    ops.add_argument("-rc", "--rear_coupler",
                     action="store_const",
                     const='REAR_COUPLER',
                     dest='command_def',
                     help="Open rear coupler")

    ops.add_argument("-r", "--ring_bell",
                     action="store_const",
                     const='RING_BELL',
                     dest='command_def',
                     help="Ring bell")

    ops.add_argument("-b", "--blow_horn",
                     action="store_const",
                     const='BLOW_HORN_ONE',
                     dest='command_def',
                     help="Blow horn")

    ops.add_argument("-boost", "--boost_speed",
                     action="store_const",
                     const='BOOST_SPEED',
                     dest='command_def',
                     help="Brake speed")

    ops.add_argument("-bl", "--boost_level",
                     action=DataAction,
                     dest='command_def',
                     choices=range(0, 8),
                     metavar="0 - 7",
                     type=int,
                     nargs='?',
                     default=3,
                     const='BOOST_LEVEL',
                     help="Boost level")

    ops.add_argument("-brake", "--brake_speed",
                     action="store_const",
                     const='BRAKE_SPEED',
                     dest='command_def',
                     help="Boost speed")

    ops.add_argument("-kl", "--brake_level",
                     action=DataAction,
                     dest='command_def',
                     choices=range(0, 8),
                     metavar="0 - 7",
                     type=int,
                     nargs='?',
                     default=3,
                     const='BRAKE_LEVEL',
                     help="Brake level")
    ops.add_argument("-tb", "--train_brake",
                     action=DataAction,
                     dest='command_def',
                     choices=range(0, 8),
                     metavar="0 - 7",
                     type=int,
                     nargs='?',
                     default=1,
                     const='TRAIN_BRAKE',
                     help="Train brake")

    ops.add_argument("-n",
                     action=DataAction,
                     dest='command_def',
                     choices=range(0, 10),
                     metavar="0 - 9",
                     type=int,
                     nargs='?',
                     default=7,  # random radio chatter
                     const='NUMERIC',
                     help="Send numeric value")

    ops.add_argument("-stall",
                     action="store_const",
                     const='STALL',
                     dest='command_def',
                     help="Set stall")

    ops.add_argument("-sui", "--start_up_immediate",
                     action="store_const",
                     const='START_UP_IMMEDIATE',
                     dest='command_def',
                     help="Start up immediate")

    ops.add_argument("-sud", "--start_up_delayed",
                     action="store_const",
                     const='START_UP_DELAYED',
                     dest='command_def',
                     help="Start up delayed (prime mover)")

    ops.add_argument("-sdi", "--shutdown_immediate",
                     action="store_const",
                     const='SHUTDOWN_IMMEDIATE',
                     dest='command_def',
                     help="Shutdown Immediate")

    ops.add_argument("-sdd", "--shutdown_delayed",
                     action="store_const",
                     const='SHUTDOWN_DELAYED',
                     dest='command_def',
                     help="Shutdown delayed with announcement")
    ops.add_argument("-e", "--engine_labor",
                     action=DataAction,
                     dest='command_def',
                     choices=range(0, 32),
                     metavar="0 - 31",
                     type=int,
                     nargs='?',
                     default=0,
                     const='ENGINE_LABOR',
                     help="Engine labor")
    ops.add_argument("-aux1",
                     dest='aux1',
                     choices=['on', 'off', 'opt1', 'opt2'],
                     nargs='?',
                     type=str,
                     const='opt1')
    ops.add_argument("-aux2",
                     dest='aux2',
                     choices=['on', 'off', 'opt1', 'opt2'],
                     nargs='?',
                     type=str,
                     const='opt1')

    # create subparsers to handle train/engine-specific operations
    sp = engine_parser.add_subparsers(dest='sub_command', help='Engine/train sub-commands')

    # Speed operations
    sp_metavar = ("Engine/Train speed: 0 - 199 (Legacy) or 0 - 31 (TMCC) or roll, restricted, slow, medium, limited, "
                  "normal, or highball")
    speed = sp.add_parser('speed', aliases=['sp'], help='Speed of engine/train')
    speed.add_argument('data',
                       type=_validate_speed,
                       action='store',
                       metavar=sp_metavar,
                       help="Absolute/Relative speed")

    speed_group = speed.add_mutually_exclusive_group()
    speed_group.add_argument("-a", "--absolute",
                             action="store_const",
                             const='ABSOLUTE_SPEED',
                             dest='command_def',
                             help="Set absolute speed")
    speed_group.add_argument("-r", "--relative",
                             action="store_const",
                             const='RELATIVE_SPEED',
                             dest='command_def',
                             help="Set relative speed speed (-5 to 5)")
    speed_group.set_defaults(option='ABSOLUTE_SPEED')

    # Bell operations
    bell = sp.add_parser('bell', aliases=['be'], help='Bell operations')
    bell_group = bell.add_mutually_exclusive_group()
    bell_group.add_argument("-r", "--ring",
                            action="store_const",
                            const='RING_BELL',
                            dest='command_def',
                            default='RING_BELL',
                            help="Ring bell")
    bell_group.add_argument("-on",
                            action="store_const",
                            const='BELL_ON',
                            dest='command_def',
                            help="Turn bell on")
    bell_group.add_argument("-off",
                            action="store_const",
                            const='BELL_OFF',
                            dest='command_def',
                            help="Turn bell off")
    bell_group.add_argument("-d", "--ding",
                            action=DataAction,
                            dest='command_def',
                            choices=range(0, 4),
                            metavar="0 - 3",
                            type=int,
                            nargs='?',
                            default=3,
                            const='BELL_ONE_SHOT_DING',
                            help="Bell one shot ding")
    bell_group.add_argument("-s", "--slider",
                            action=DataAction,
                            dest='command_def',
                            choices=range(2, 6),
                            metavar="2 - 5",
                            type=int,
                            nargs='?',
                            default=2,
                            const='BELL_SLIDER_POSITION',
                            help="Bell slider position")

    # Horn operations
    horn = sp.add_parser('horn', aliases=['ho'], help='Horn operations')
    horn_group = horn.add_mutually_exclusive_group()
    horn_group.add_argument("-1", "--blow_horn_one",
                            action="store_const",
                            const='BLOW_HORN_ONE',
                            dest='command_def',
                            default='BLOW_HORN_ONE',
                            help="Blow horn One")
    horn_group.add_argument("-2", "--blow_horn_two",
                            action="store_const",
                            const='BLOW_HORN_TWO',
                            dest='command_def',
                            help="Blow horn two")
    horn_group.add_argument("-i", "--intensity",
                            action=DataAction,
                            dest='command_def',
                            choices=range(0, 17),
                            metavar="0 - 16",
                            type=int,
                            nargs='?',
                            default=1,
                            const='QUILLING_HORN_INTENSITY',
                            help="Quilling horn intensity")

    # Momentum operations
    momentum = sp.add_parser('momentum', aliases=['mo'], help='Momentum operations')
    mom_group = momentum.add_mutually_exclusive_group()
    mom_group.add_argument("-l", "--low",
                           action="store_const",
                           const='MOMENTUM_LOW',
                           dest='command_def',
                           default='MOMENTUM_MEDIUM',  # strange, but default actions only applied if placed
                           help="Set momentum to low")  # on first argument of mutual group
    mom_group.add_argument("-m", "--medium",
                           action="store_const",
                           const='MOMENTUM_MEDIUM',
                           dest='command_def',
                           help="Set momentum to medium")
    mom_group.add_argument("-x", "--high",
                           action="store_const",
                           const='MOMENTUM_HIGH',
                           dest='command_def',
                           help="Set momentum to high")
    mom_group.add_argument("-off",
                           action="store_const",
                           const='MOMENTUM',
                           dest='command_def',
                           help="Set momentum off")

    mom_group.add_argument("-a", "--absolute",
                           action=DataAction,
                           dest='command_def',
                           choices=range(0, 8),
                           metavar="0 - 7",
                           type=int,
                           nargs='?',
                           default=0,
                           const='MOMENTUM',
                           help="Set absolute momentum")

    sound = sp.add_parser('sound', aliases=['so'], help='Sound operations')
    sound_group = sound.add_mutually_exclusive_group()
    sound_group.add_argument("-a", "--auger",
                             action="store_const",
                             const='AUGER',
                             dest='command_def',
                             help="Auger sound")
    sound_group.add_argument("-b", "--brake_squeal",
                             action="store_const",
                             const='BRAKE_SQUEAL',
                             dest='command_def',
                             help="Brake squeal sound")
    sound_group.add_argument("-r", "--brake_air_release",
                             action="store_const",
                             const='BRAKE_AIR_RELEASE',
                             dest='command_def',
                             help="Brake air release sound")
    sound_group.add_argument("-d", "--diesel_run_level",
                             action=DataAction,
                             dest='command_def',
                             choices=range(0, 8),
                             metavar="0 - 7",
                             type=int,
                             nargs='?',
                             default=0,
                             const='DIESEL_LEVEL',
                             help="Diesel run level sound")
    sound_group.add_argument("-f", "--refueling",
                             action="store_const",
                             const='REFUELLING',
                             dest='command_def',
                             help="Refueling sound")
    sound_group.add_argument("-l", "--let_off",
                             action="store_const",
                             const='LET_OFF',
                             dest='command_def',
                             help="Short let-off sound")
    sound_group.add_argument("-ll", "--let_off_long",
                             action="store_const",
                             const='LET_OFF_LONG',
                             dest='command_def',
                             help="Long let-off sound")
    sound_group.add_argument("-w", "--water_injector",
                             action="store_const",
                             const='WATER_INJECTOR',
                             dest='command_def',
                             help="Water injector sound")
    # construct final parser with all components in order
    parser = argparse.ArgumentParser("Control specified engine/train (1 - 99)",
                                     parents=[engine_parser,
                                              train_parser(),
                                              command_format_parser(),
                                              cli_parser()])
    EngineCli(parser)
