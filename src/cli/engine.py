#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import CliBaseTMCC, cli_parser, command_format_parser, train_parser
from src.protocol.constants import EngineOption, TMCC1EngineOption, TMCC2EngineOption
from src.protocol.tmcc1.engine_cmd import EngineCmd as EngineCmdTMCC1
from src.protocol.tmcc2.engine_cmd import EngineCmd as EngineCmdTMCC2


class EngineCli(CliBaseTMCC):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        engine: int = self._args.engine
        option_data: int = self._args.data if 'data' in self._args else 0
        try:
            option: EngineOption = self._decode_option()  # raise ValueError if can't decode
            if self.is_train_command or self.is_tmcc2 or isinstance(option, TMCC2EngineOption):
                scope = self._determine_scope()
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
                                     baudrate=self._args.baudrate,
                                     port=self._args.port)
            cmd.fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Control specified engine/train (1 - 99)",
                                     parents=[train_parser(), command_format_parser(), cli_parser()])
    parser.add_argument("engine", metavar='Engine/Train', type=int, help="Engine/Train to control")

    ops = parser.add_mutually_exclusive_group()
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

    # create subparsers to handle train/engine-specific operations
    sp = parser.add_subparsers(dest='command', help='sub-command help')

    # Speed operations
    speed = sp.add_parser('speed', help='Speed of engine/train')
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
    bell = sp.add_parser('bell', help='Bell operations')
    bell_group = bell.add_mutually_exclusive_group()
    bell_group.add_argument("-r", "--ring",
                            action="store_const",
                            const='RING_BELL',
                            dest='option',
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
    bell_group.set_defaults(option='RING_BELL')

    EngineCli(parser)
