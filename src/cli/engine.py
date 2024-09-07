#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBaseTMCC, DataAction, cli_parser, command_format_parser, train_parser
from src.protocol.constants import EngineOptionEnum, TMCC1EngineOption, TMCC2EngineOption
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
            option: EngineOptionEnum = self._decode_engine_option()  # raise ValueError if can't decode
            if option is None:
                raise ValueError("Must specify an option, use -h for help")
            print(self._args)
            scope = self._determine_scope()
            if self.is_tmcc2 or isinstance(option, TMCC2EngineOption):
                cmd = EngineCmdTMCC2(engine,
                                     TMCC2EngineOption(option),
                                     option_data,
                                     scope,
                                     baudrate=self._args.baudrate,
                                     port=self._args.port)
            else:
                cmd = EngineCmdTMCC1(engine,
                                     TMCC1EngineOption(option),
                                     option_data,
                                     scope,
                                     baudrate=self._args.baudrate,
                                     port=self._args.port)
            cmd.fire()
        except ValueError as ve:
            print(ve)

    def _decode_engine_option(self) -> EngineOptionEnum | None:
        """
            Decode the 'option' argument, if present, into a valid
            TMCC1EngineOption or TMCC2EngineOption enum. Use the specified
            command format, if present, to help resolve, as the two enum
            classes share element names
        """
        if 'option' not in self._args:
            return None

        # if option is None, check if an aux command was specified via
        # the aux1/aux2 arguments; only one should have a value
        option = self._args.option
        if not option or not option.strip():
            # construct the EngineOptionEnum by prepending the aux choice
            # (AUX1/AUX2) to the suffix based on the argument value
            # (on, off, opt1, opt2)
            if 'aux1' in self._args and self._args.aux1 is not None:
                option = f"AUX1{AUX_COMMAND_MAP[self._args.aux1.lower()]}"
            elif 'aux2' in self._args and self._args.aux2 is not None:
                option = f"AUX2{AUX_COMMAND_MAP[self._args.aux2.lower()]}"
            else:
                raise ValueError("Must specify an option, use -h for help")
        else:
            option = option.strip().upper()

        # reset option in args, for display purposes
        self._args.option = option

        # if scope is TMCC1, resolve via TMCC1EngineOption
        if self.is_tmcc1:
            enum_class = TMCC1EngineOption
        else:
            enum_class = TMCC2EngineOption
        if option in dir(enum_class):
            return enum_class[option]
        else:
            raise ValueError(f'Invalid {self.command_format.name} option: {option}')


if __name__ == '__main__':
    engine_parser = argparse.ArgumentParser(add_help=False)
    engine_parser.add_argument("engine",
                               metavar='Engine/Train',
                               type=int,
                               help="Engine/Train to operate")

    ops = engine_parser.add_mutually_exclusive_group()
    ops.add_argument("-a", "--set_address",
                     action="store_const",
                     const='SET_ADDRESS',
                     dest='option',
                     help="Set engine address")

    ops.add_argument("-s", "--stop_immediate",
                     action="store_const",
                     const='STOP_IMMEDIATE',
                     dest='option',
                     help="Stop immediate")

    ops.add_argument("-fwd", "--forward_direction",
                     action="store_const",
                     const='FORWARD_DIRECTION',
                     dest='option',
                     help="Set forward direction")

    ops.add_argument("-rev", "--reverse_direction",
                     action="store_const",
                     const='REVERSE_DIRECTION',
                     dest='option',
                     help="Set reverse direction")

    ops.add_argument("-t", "--toggle_direction",
                     action="store_const",
                     const='TOGGLE_DIRECTION',
                     dest='option',
                     help="Toggle direction")

    ops.add_argument("-fc", "--front_coupler",
                     action="store_const",
                     const='FRONT_COUPLER',
                     dest='option',
                     help="Open front coupler")

    ops.add_argument("-rc", "--rear_coupler",
                     action="store_const",
                     const='REAR_COUPLER',
                     dest='option',
                     help="Open rear coupler")

    ops.add_argument("-r", "--ring_bell",
                     action="store_const",
                     const='RING_BELL',
                     dest='option',
                     help="Ring bell")

    ops.add_argument("-b", "--blow_horn",
                     action="store_const",
                     const='BLOW_HORN_ONE',
                     dest='option',
                     help="Blow horn")

    ops.add_argument("-boost", "--boost_speed",
                     action="store_const",
                     const='BOOST_SPEED',
                     dest='option',
                     help="Brake speed")

    ops.add_argument("-bl", "--boost_level",
                     action=DataAction,
                     dest='option',
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
                     dest='option',
                     help="Boost speed")

    ops.add_argument("-kl", "--brake_level",
                     action=DataAction,
                     dest='option',
                     choices=range(0, 8),
                     metavar="0 - 7",
                     type=int,
                     nargs='?',
                     default=3,
                     const='BRAKE_LEVEL',
                     help="Brake level")
    ops.add_argument("-tb", "--train_brake",
                     action=DataAction,
                     dest='option',
                     choices=range(0, 8),
                     metavar="0 - 7",
                     type=int,
                     nargs='?',
                     default=3,
                     const='TRAIN_BRAKE',
                     help="Train brake")

    ops.add_argument("-sui", "--start_up_immediate",
                     action="store_const",
                     const='START_UP_IMMEDIATE',
                     dest='option',
                     help="Start up immediate")

    ops.add_argument("-sud", "--start_up_delayed",
                     action="store_const",
                     const='START_UP_DELAYED',
                     dest='option',
                     help="Start up delayed (prime mover)")

    ops.add_argument("-sdi", "--shutdown_immediate",
                     action="store_const",
                     const='SHUTDOWN_IMMEDIATE',
                     dest='option',
                     help="Shutdown Immediate")

    ops.add_argument("-sdd", "--shutdown_delayed",
                     action="store_const",
                     const='SHUTDOWN_DELAYED',
                     dest='option',
                     help="Shutdown delayed with announcement")
    ops.add_argument("-e", "--engine_labor",
                     action=DataAction,
                     dest='option',
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
    speed = sp.add_parser('speed', aliases=['sp'], help='Speed of engine/train')
    speed.add_argument('data',
                       type=int,
                       action='store',
                       help="Absolute/Relative speed")
    speed_group = speed.add_mutually_exclusive_group()
    speed_group.add_argument("-a", "--absolute",
                             action="store_const",
                             const='ABSOLUTE_SPEED',
                             dest='option',
                             help="Set absolute speed")
    speed_group.add_argument("-r", "--relative",
                             action="store_const",
                             const='RELATIVE_SPEED',
                             dest='option',
                             help="Set relative speed speed (-5 to 5)")
    speed_group.set_defaults(option='ABSOLUTE_SPEED')

    # Bell operations
    bell = sp.add_parser('bell', aliases=['be'], help='Bell operations')
    bell_group = bell.add_mutually_exclusive_group()
    bell_group.add_argument("-r", "--ring",
                            action="store_const",
                            const='RING_BELL',
                            dest='option',
                            default='RING_BELL',
                            help="Ring bell")
    bell_group.add_argument("-on",
                            action="store_const",
                            const='BELL_ON',
                            dest='option',
                            help="Turn bell on")
    bell_group.add_argument("-off",
                            action="store_const",
                            const='BELL_OFF',
                            dest='option',
                            help="Turn bell off")
    bell_group.add_argument("-d", "--ding",
                            action=DataAction,
                            dest='option',
                            choices=range(0, 4),
                            metavar="0 - 3",
                            type=int,
                            nargs='?',
                            default=3,
                            const='BELL_ONE_SHOT_DING',
                            help="Bell one shot ding")
    bell_group.add_argument("-s", "--slider",
                            action=DataAction,
                            dest='option',
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
                            dest='option',
                            default='BLOW_HORN_ONE',
                            help="Blow horn One")
    horn_group.add_argument("-2", "--blow_horn_two",
                            action="store_const",
                            const='BLOW_HORN_TWO',
                            dest='option',
                            help="Blow horn two")
    horn_group.add_argument("-i", "--intensity",
                            action=DataAction,
                            dest='option',
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
                           dest='option',
                           default='MOMENTUM_MEDIUM',  # strange, but default actions only applied if placed
                           help="Set momentum to low")  # on first argument of mutual group
    mom_group.add_argument("-m", "--medium",
                           action="store_const",
                           const='MOMENTUM_MEDIUM',
                           dest='option',
                           help="Set momentum to medium")
    mom_group.add_argument("-x", "--high",
                           action="store_const",
                           const='MOMENTUM_HIGH',
                           dest='option',
                           help="Set momentum to high")
    mom_group.add_argument("-off",
                           action="store_const",
                           const='MOMENTUM',
                           dest='option',
                           help="Set momentum off")

    mom_group.add_argument("-a", "--absolute",
                           action=DataAction,
                           dest='option',
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
                             dest='option',
                             help="Auger sound")
    sound_group.add_argument("-b", "--brake_squeal",
                             action="store_const",
                             const='BRAKE_SQUEAL',
                             dest='option',
                             help="Brake squeal sound")
    sound_group.add_argument("-r", "--brake_air_release",
                             action="store_const",
                             const='BRAKE_AIR_RELEASE',
                             dest='option',
                             help="Brake air release sound")
    sound_group.add_argument("-d", "--diesel_run_level",
                             action=DataAction,
                             dest='option',
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
                             dest='option',
                             help="Refueling sound")
    sound_group.add_argument("-l", "--let_off",
                             action="store_const",
                             const='LET_OFF',
                             dest='option',
                             help="Short let-off sound")
    sound_group.add_argument("-ll", "--let_off_long",
                             action="store_const",
                             const='LET_OFF_LONG',
                             dest='option',
                             help="Long let-off sound")
    sound_group.add_argument("-w", "--water_injector",
                             action="store_const",
                             const='WATER_INJECTOR',
                             dest='option',
                             help="Water injector sound")
    # construct final parser with all components in order
    parser = argparse.ArgumentParser("Control specified engine/train (1 - 99)",
                                     parents=[engine_parser,
                                              train_parser(),
                                              command_format_parser(),
                                              cli_parser()])
    EngineCli(parser)
