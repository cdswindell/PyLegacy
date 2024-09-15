#!/usr/bin/env python3
#
import argparse
from typing import List

from src.cli.cli_base import command_format_parser, CliBaseTMCC, train_parser, cli_parser
from src.protocol.constants import CommandSyntax
from src.protocol.tmcc1.halt_cmd import HaltCmd as HaltCmdTMCC1
from src.protocol.tmcc2.halt_cmd import HaltCmd as HaltCmdTMCC2


class HaltCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        return argparse.ArgumentParser("Emergency halt; stop all engines and trains",
                                       parents=[train_parser(),
                                                command_format_parser(CommandSyntax.TMCC1),
                                                cli_parser()
                                                ])

    def __init__(self,
                 arg_parser: argparse.ArgumentParser,
                 cmd_line: List[str] = None,
                 do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        try:
            if self.is_train_command or self.is_tmcc2:
                cmd = HaltCmdTMCC2(baudrate=self._args.baudrate, port=self._args.port)
            else:
                cmd = HaltCmdTMCC1(baudrate=self._args.baudrate, port=self._args.port)
            if self.do_fire:
                cmd.fire()
            self._command = cmd
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    HaltCli(HaltCli.command_parser())
