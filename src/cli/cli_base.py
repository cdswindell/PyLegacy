import abc
import argparse
import sys
from abc import ABC
from typing import List, Any

from ..comm.comm_buffer import CommBuffer
from ..protocol.command_base import CommandBase
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope, CommandSyntax
from ..protocol.tmcc1.tmcc1_constants import TMCC1_SPEED_MAP
from ..protocol.tmcc2.tmcc2_constants import TMCC2_SPEED_MAP
from ..utils.argument_parser import ArgumentParser


class CliBase(ABC):
    __metaclass__ = abc.ABCMeta

    @classmethod
    def command_parser(cls) -> ArgumentParser | None:
        return None

    @staticmethod
    def cli_parser() -> ArgumentParser:
        """
            Add options common to all CLI commands here. Command handlers
            can inherit from this parser to add other command-specific options.
        """
        # define arguments common to all Legacy CLI commands
        parser = ArgumentParser(add_help=False)

        parser.add_argument('-baud', '--baudrate', action='store',
                            type=int, default=DEFAULT_BAUDRATE, help=f"Baud Rate ({DEFAULT_BAUDRATE})")
        parser.add_argument('-p', '--port', action='store',
                            default=DEFAULT_PORT, help=f"Serial Port ({DEFAULT_PORT})")
        parser.add_argument('-server', action='store',
                            help=f"IP Address of PyLegacy server, if client. Server communicates with LCS SER2")
        return parser

    @staticmethod
    def multi_parser() -> ArgumentParser:
        """
            Add options to allow command repetition and delay
        """
        # define arguments common to all Legacy CLI commands
        parser = ArgumentParser(add_help=False)
        parser.add_argument("-re", "--repeat",
                            action="store",
                            type=CliBase._validate_repeat,
                            default=1,
                            help="Number of times to repeat command (default: 1)")

        parser.add_argument("-de", "--delay",
                            action="store",
                            type=CliBase._validate_delay,
                            default=0,
                            help="Second(s) to delay between repeated commands (default: 0)")
        return parser

    @staticmethod
    def command_format_parser(default: CommandSyntax = CommandSyntax.TMCC2) -> ArgumentParser:
        """
            Add command_def to run command using TMCC1 command syntax
        """
        parser = ArgumentParser(add_help=False)
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

    @staticmethod
    def train_parser() -> ArgumentParser:
        """
            Add command_def to run command TMCC2 command as train rather than engine
        """
        parser = ArgumentParser(add_help=False)
        parser.add_argument("-tr", "--train",
                            action="store_const",
                            const=True,
                            help="Direct command to addressed train rather than engine (for TMCC2 commands)")
        return parser

    def __init__(self,
                 arg_parser: ArgumentParser,
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
        # as the TrainControl cli strips out some commands, we need to restore them
        if 'baudrate' in self._args:
            self._baudrate = self._args.baudrate
        else:
            self._baudrate = DEFAULT_BAUDRATE
        if 'baudrate' in self._args:
            self._port = self._args.port
        else:
            self._port = DEFAULT_PORT
        if 'server' in self._args:
            self._server = self._args.server
        else:
            self._server = None
        # print(self._args)

    def send(self, buffer: CommBuffer = None) -> None:
        repeat = self._args.repeat if 'repeat' in self._args else 1
        delay = self._args.delay if 'delay' in self._args else 0
        self.command.send(repeat=repeat, delay=delay, buffer=buffer)

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

    @staticmethod
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

    @staticmethod
    def _validate_delay(arg: Any) -> int:
        try:
            arg = int(arg)  # try convert to int
            if arg >= 0:
                return arg
        except ValueError:
            pass
        raise argparse.ArgumentTypeError("Delay must be 0 or greater")

    @staticmethod
    def _validate_repeat(arg: Any) -> int:
        try:
            arg = int(arg)  # try convert to int
            if arg > 0:
                return arg
        except ValueError:
            pass
        raise argparse.ArgumentTypeError("Delay must be 1 or greater")


class CliBaseTMCC(CliBase):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 arg_parser: ArgumentParser,
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
