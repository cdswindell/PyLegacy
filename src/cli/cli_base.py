import argparse
import abc
from abc import ABC

from src.protocol.constants import CommandFormat, DEFAULT_BAUDRATE, DEFAULT_PORT, TMCCCommandScope, EngineOptionEnum, \
    TMCC1EngineOption, TMCC2EngineOption


class CliBase(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        self._args = arg_parser.parse_args()
        self._command_format = CommandFormat.TMCC2  # Use TMCC2-style commands by default, if supported
        print(self._args)

    @property
    def is_tmcc1(self) -> bool:
        return self._command_format == CommandFormat.TMCC1

    @property
    def is_tmcc2(self) -> bool:
        return self._command_format == CommandFormat.TMCC2

    @property
    def command_format(self) -> CommandFormat:
        return self._command_format

    def _decode_option(self) -> EngineOptionEnum | None:
        """
            Decode the 'option' argument, if present, into a valid
            TMCC1EngineOption or TMCC2EngineOption enum. Use the specified
            command format, if present, to help resolve, as the two enum
            classes share element names
        """
        if 'option' not in self._args or self._args.option is None:
            return None

        # if scope is TMCC1, resolve via TMCC1EngineOption
        option = self._args.option.strip().upper()
        if self.is_tmcc1:
            enum_class = TMCC1EngineOption
        else:
            enum_class = TMCC2EngineOption
        if option in dir(enum_class):
            return enum_class[option]
        else:
            raise ValueError(f'Invalid {self.command_format.name} option: {option}')


class CliBaseTMCC(CliBase):
    __metaclass__ = abc.ABCMeta

    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        if 'format' in self._args and self._args.format:
            self._command_format = self._args.format
        else:
            self._command_format = CommandFormat.TMCC2

    def _determine_scope(self):
        return TMCCCommandScope.TRAIN if self._args.train else TMCCCommandScope.ENGINE

    @property
    def is_train_command(self) -> bool:
        if 'train' in self._args:
            return bool(self._args.train)


class DataAction(argparse.Action):
    """
        Custom action that sets both the option and data fields
        with the option value specified by 'const', and the data value
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
    return parser


def command_format_parser(default: CommandFormat = CommandFormat.TMCC2) -> argparse.ArgumentParser:
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


def train_parser() -> argparse.ArgumentParser:
    """
        Add option to run command TMCC2 command as train rather than engine
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-tr", "--train",
                        action="store_const",
                        const=True,
                        help="Direct command to addressed train rather than engine (for TMCC2 commands)")
    return parser
