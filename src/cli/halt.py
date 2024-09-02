#!/usr/bin/env python3
#
import argparse

from src.cli.cli_base import tmcc1_cli_parser_factory, CliBaseTMCC
from src.protocol.constants import CommandFormat
from src.protocol.tmcc1.halt_cmd import HaltCmd as HaltCmdTMCC1
from src.protocol.tmcc2.halt_cmd import HaltCmd as HaltCmdTMCC2


class HaltCli(CliBaseTMCC):
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        super().__init__(arg_parser)
        try:
            if self.use_tmcc1_format:
                HaltCmdTMCC1(baudrate=self._args.baudrate, port=self._args.port).fire()
            else:
                HaltCmdTMCC2(baudrate=self._args.baudrate, port=self._args.port).fire()
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Emergency halt; stop all trains",
                                     parents=[tmcc1_cli_parser_factory(CommandFormat.TMCC1)])
    HaltCli(parser)
