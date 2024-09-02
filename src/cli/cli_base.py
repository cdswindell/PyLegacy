import argparse
import abc
from abc import ABC

from src.protocol.constants import CommandFormat


class CliBase(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        self._args = arg_parser.parse_args()
        self._command_format = CommandFormat.TMCC2  # Use TMCC2-style commands by default, if supported
        print(self._args)


class CliBaseTMCC(CliBase):
    __metaclass__ = abc.ABCMeta

    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        if 'format' in self._args and self._args.format:
            self._command_format = self._args.format
        else:
            self._command_format = CommandFormat.TMCC2

    @property
    def use_tmcc1_format(self) -> bool:
        return self._command_format == CommandFormat.TMCC1

    @property
    def use_tmcc2_format(self) -> bool:
        return self._command_format == CommandFormat.TMCC2


def cli_parser() -> argparse.ArgumentParser:
    """
        Add options common to all CLI commands here. Command handlers
        can inherit from this parser to add other command-specific options.
    """
    # define arguments common to all Legacy CLI commands
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument('-b', '--baudrate', action='store',
                        type=int, default=9600, help='''Baud Rate (9600)''')
    parser.add_argument('-p', '--port', action='store',
                        default="/dev/ttyUSB0", help='''Serial Port (/dev/ttyUSB0)''')
    return parser


def tmcc1_cli_parser(default: CommandFormat = CommandFormat.TMCC2) -> argparse.ArgumentParser:
    """
        Add option to run command using TMCC1 command syntax
    """
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-tmcc", "--tmcc1",
                       action="store_const",
                       const=CommandFormat.TMCC1,
                       dest='format',
                       help="Use TMCC1 command syntax.")
    group.add_argument("-legacy", "--tmcc2",
                       action="store_const",
                       const=CommandFormat.TMCC2,
                       dest='format',
                       help="Use TMCC2/Legacy command syntax.")
    group.set_defaults(format=default)

    return parser


def train_cli_parser() -> argparse.ArgumentParser:
    """
        Add option to run command TMCC2 command as train rather than engine
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-t", "--train",
                        action="store_const",
                        const=True,
                        help="Direct command to addressed train rather than engine (for TMCC2 commands)")
    return parser
