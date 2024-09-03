#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import command_format_parser, CliBaseTMCC, train_parser, cli_parser
from src.protocol.constants import CommandFormat
from src.protocol.tmcc1.halt_cmd import HaltCmd as HaltCmdTMCC1
from src.protocol.tmcc2.halt_cmd import HaltCmd as HaltCmdTMCC2


class HaltCli(CliBaseTMCC):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        try:
            if self.is_train_command or self.use_tmcc2_format:
                scope = self._determine_scope()
                HaltCmdTMCC2(scope=scope, baudrate=self._args.baudrate, port=self._args.port).fire()
            else:
                HaltCmdTMCC1(baudrate=self._args.baudrate, port=self._args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Emergency halt; stop all engines and trains",
                                     parents=[train_parser(),
                                              command_format_parser(CommandFormat.TMCC1),
                                              cli_parser()
                                              ])
    HaltCli(parser)
