import abc
import argparse
from abc import ABC
from typing import List

from ..protocol.command_base import CommandBase
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope, CommandSyntax


class CliBase(ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def command_parser(cls) -> argparse.ArgumentParser | None:
        return None

    def __init__(self,
                 arg_parser: argparse.ArgumentParser,
                 cmd_line: List[str] = None,
                 do_fire: bool = True) -> None:
        if cmd_line is None:
            self._args = arg_parser.parse_args()
        else:
            self._args = arg_parser.parse_args(cmd_line)
        self._command = None
        self._command_format = CommandSyntax.TMCC2  # Use TMCC2-style commands by default, if supported
        self._command_line: List[str] = cmd_line
        self._do_fire = do_fire
        # print(self._args)

    @property
    def command(self) -> CommandBase:
        return self._command

    @property
    def command_line(self) -> List[str]:
        return self._command_line

    @property
    def args(self) -> argparse.Namespace:
        return self._args

    @property
    def do_fire(self) -> bool:
        return self._do_fire

    @property
    def is_tmcc1(self) -> bool:
        return self._command_format == CommandSyntax.TMCC1

    @property
    def is_tmcc2(self) -> bool:
        return self._command_format == CommandSyntax.TMCC2

    @property
    def command_format(self) -> CommandSyntax:
        return self._command_format


class CliBaseTMCC(CliBase):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 arg_parser: argparse.ArgumentParser,
                 cmd_line: List[str] = None,
                 do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        if 'format' in self._args and self._args.format:
            self._command_format = self._args.format
        else:
            self._command_format = CommandSyntax.TMCC2

    def _determine_scope(self):
        return CommandScope.TRAIN if self._args.train else CommandScope.ENGINE

    @property
    def is_train_command(self) -> bool:
        if 'train' in self._args:
            return bool(self._args.train)


class DataAction(argparse.Action):
    """
        Custom action that sets both the command_def and data fields
        with the command_def value specified by 'const', and the data value
        specified by the user-provided argument or 'default'
    """

    def __init__(self, option_strings, dest, **kwargs):
        """
            We need to capture both the values of const and default, as we use the
            'const' value to specify the command_op to execute if this action is taken.
            Once saved, we reset its value to the default value.
        """
        self._default = kwargs.get('default')
        self._command_op = kwargs.get('const')
        kwargs['const'] = self._default
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, psr, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, self._command_op)
        if values is not None:
            setattr(namespace, "data", values)
        else:
            setattr(namespace, "data", self._default)


def cli_parser() -> argparse.ArgumentParser:
    """
        Add options common to all CLI commands here. Command handlers
        can inherit from this parser to add other command-specific options.
    """
    # define arguments common to all Legacy CLI commands
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument('-baud', '--baudrate', action='store',
                        type=int, default=DEFAULT_BAUDRATE, help=f"Baud Rate ({DEFAULT_BAUDRATE})")
    parser.add_argument('-p', '--port', action='store',
                        default=DEFAULT_PORT, help=f"Serial Port ({DEFAULT_PORT})")
    parser.add_argument('-server', action='store',
                        help=f"IP Address of PyLegacy server, if client. Server communicates with LCS SER2")
    return parser


def command_format_parser(default: CommandSyntax = CommandSyntax.TMCC2) -> argparse.ArgumentParser:
    """
        Add command_def to run command using TMCC1 command syntax
    """
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-tmcc", "--tmcc1",
                       action="store_const",
                       const=CommandSyntax.TMCC1,
                       dest='format',
                       help="Use TMCC1 command syntax.")
    group.add_argument("-legacy", "--tmcc2",
                       action="store_const",
                       const=CommandSyntax.TMCC2,
                       dest='format',
                       help="Use TMCC2/Legacy command syntax.")
    group.set_defaults(format=default)
    return parser


def train_parser() -> argparse.ArgumentParser:
    """
        Add command_def to run command TMCC2 command as train rather than engine
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-tr", "--train",
                        action="store_const",
                        const=True,
                        help="Direct command to addressed train rather than engine (for TMCC2 commands)")
    return parser
