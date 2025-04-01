#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import logging
import sys
from abc import ABC, ABCMeta
from argparse import Action, ArgumentParser, ArgumentTypeError, Namespace
from typing import Any, List

from ..comm.comm_buffer import CommBuffer
from ..protocol.command_base import CommandBase
from ..protocol.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_DURATION_INTERVAL_MSEC,
    DEFAULT_PORT,
    DEFAULT_VALID_BAUDRATES,
    PROGRAM_NAME,
    CommandScope,
    CommandSyntax,
)
from ..protocol.tmcc1.tmcc1_constants import TMCC1_SPEED_MAP
from ..protocol.tmcc2.tmcc2_constants import TMCC2_SPEED_MAP
from ..utils.argument_parser import PyTrainArgumentParser

log = logging.getLogger(__name__)


class CliBase(ABC):
    """
    Base class for PyTrain CLI commands
    """

    __metaclass__ = ABCMeta

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
        parser = PyTrainArgumentParser(add_help=False)

        parser.add_argument(
            "-baudrate",
            action="store",
            type=int,
            choices=DEFAULT_VALID_BAUDRATES,
            default=DEFAULT_BAUDRATE,
            help=f"Baud Rate ({DEFAULT_BAUDRATE})",
        )
        parser.add_argument("-port", action="store", default=DEFAULT_PORT, help=f"Serial Port ({DEFAULT_PORT})")
        parser.add_argument(
            "-server",
            action="store",
            help=f"IP Address of {PROGRAM_NAME} server, if client. Server communicates with Base 3/LCS SER2",
        )
        return parser

    @staticmethod
    def multi_parser() -> ArgumentParser:
        """
        Add options to allow command repetition and delay
        """
        # define arguments common to all Legacy CLI commands
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument(
            "-repeat",
            action="store",
            type=CliBase._validate_repeat,
            default=1,
            help="Number of times to repeat command (default: 1)",
        )

        parser.add_argument(
            "-delay",
            action="store",
            type=CliBase._validate_time,
            default=0.0,
            help="Second(s) to delay between repeated commands (default: 0)",
        )

        parser.add_argument(
            "-duration",
            action="store",
            type=CliBase._validate_time,
            default=0.0,
            help="Second(s) to continue firing the command",
        )

        parser.add_argument(
            "-interval",
            action="store",
            type=CliBase._validate_interval,
            default=None,
            help=f"Milliseconds to pause between commands with -duration (default: {DEFAULT_DURATION_INTERVAL_MSEC})",
        )
        return parser

    @staticmethod
    def command_format_parser(default: CommandSyntax = CommandSyntax.LEGACY) -> ArgumentParser:
        """
        Add command_def to run command using TMCC1 command syntax
        """
        parser = PyTrainArgumentParser(add_help=False)
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-tmcc",
            "--tmcc1",
            action="store_const",
            const=CommandSyntax.TMCC,
            dest="format",
            help="Use TMCC1 command syntax.",
        )
        group.add_argument(
            "-legacy",
            "--tmcc2",
            action="store_const",
            const=CommandSyntax.LEGACY,
            dest="format",
            help="Use TMCC2/Legacy command syntax.",
        )
        group.set_defaults(format=default)
        return parser

    @staticmethod
    def train_parser() -> ArgumentParser:
        """
        Add command_def to run command TMCC2 command as train rather than engine
        """
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument(
            "-train",
            action="store_const",
            const=True,
            help="Direct command to addressed train rather than engine (for TMCC2 commands)",
        )
        return parser

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        if arg_parser is None:
            arg_parser = self.command_parser()
        if cmd_line is None:
            self._args = arg_parser.parse_args()
        else:
            self._args = arg_parser.parse_args(cmd_line)
        self._command = None
        self._command_format = CommandSyntax.LEGACY  # Use TMCC2-style commands by default, if supported
        self._command_line: List[str] = cmd_line
        self._do_fire = do_fire
        # as the TrainControl cli strips out some commands, we need to restore them
        if "baudrate" in self._args:
            self._baudrate = self._args.baudrate
        else:
            self._baudrate = DEFAULT_BAUDRATE
        if "port" in self._args:
            self._port = self._args.port
        else:
            self._port = DEFAULT_PORT
        if "server" in self._args:
            self._server = self._args.server
        else:
            self._server = None

        # are we a server or a client, or do we just not know?
        if CommBuffer.is_built:
            self._is_server = CommBuffer.is_server()
        else:
            self._is_server = False
        log.debug(self._args)

    def send(self) -> None:
        repeat = self._args.repeat if "repeat" in self._args else 1
        delay = self._args.delay if "delay" in self._args else 0
        duration = self._args.duration if "duration" in self._args else 0
        interval = self._args.interval if "interval" in self._args and self._args.interval else None
        self.command.send(
            repeat=repeat,
            delay=delay,
            duration=duration,
            interval=interval,
            baudrate=self._baudrate,
            port=self._port,
            server=self._server,
        )

    @property
    def command(self) -> CommandBase:
        return self._command

    @property
    def command_line(self) -> List[str]:
        return self._command_line

    @property
    def args(self) -> Namespace:
        return self._args

    @property
    def do_fire(self) -> bool:
        return self._do_fire

    @property
    def is_tmcc1(self) -> bool:
        return self._command_format == CommandSyntax.TMCC

    @property
    def is_tmcc2(self) -> bool:
        return self._command_format == CommandSyntax.LEGACY

    @property
    def command_format(self) -> CommandSyntax:
        return self._command_format

    @property
    def is_server(self) -> bool:
        return self._is_server

    @staticmethod
    def _validate_speed(arg: Any) -> int:
        try:
            return int(arg)  # try convert to int
        except ValueError:
            pass
        uc_arg = str(arg).upper()
        if uc_arg in TMCC2_SPEED_MAP:
            # feels a little hacky, but need a way to use a different map for TMCC commands
            if "-tmcc" in sys.argv or "-tmcc1" in sys.argv:
                return TMCC1_SPEED_MAP[uc_arg]
            return TMCC2_SPEED_MAP[uc_arg]
        raise ArgumentTypeError("Speed must be between 0 and 199 (0 and 31, for tmcc)")

    @staticmethod
    def _validate_time(arg: Any) -> float:
        try:
            arg = float(arg)  # try convert to float
            if arg >= 0.0:
                return arg
        except ValueError:
            pass
        raise ArgumentTypeError("Delay/Duration must be >= 0.0")

    @staticmethod
    def _validate_interval(arg: Any) -> int:
        try:
            arg = int(arg)  # try convert to float
            if arg >= DEFAULT_DURATION_INTERVAL_MSEC:
                return arg
        except ValueError:
            pass
        raise ArgumentTypeError(f"Interval must be >= {DEFAULT_DURATION_INTERVAL_MSEC}")

    @staticmethod
    def _validate_repeat(arg: Any) -> int:
        try:
            arg = int(arg)  # try convert to int
            if arg >= 1:
                return arg
        except ValueError:
            pass
        raise ArgumentTypeError("Repeat must be >= 1")


class CliBaseTMCC(CliBase):
    __metaclass__ = ABCMeta

    def __init__(self, arg_parser: ArgumentParser, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        if "format" in self._args and self._args.format:
            self._command_format = self._args.format
        else:
            self._command_format = CommandSyntax.LEGACY

    def _determine_scope(self):
        return CommandScope.TRAIN if self._args.train else CommandScope.ENGINE

    @property
    def is_train_command(self) -> bool:
        if "train" in self._args:
            return bool(self._args.train)
        else:
            return False


class DataAction(Action):
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
        self._default = kwargs.get("default")
        self._command_op = kwargs.get("const")
        kwargs["const"] = self._default
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, psr, namespace, values, option_string=None) -> None:
        setattr(namespace, self.dest, self._command_op)
        if values is not None:
            setattr(namespace, "data", values)
        else:
            setattr(namespace, "data", self._default)
