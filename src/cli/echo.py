#!/usr/bin/env python3
#
from typing import List

from src.cli.cli_base import CliBase
from src.comm.serial_reader import SerialReader
from src.utils.argument_parser import ArgumentParser


class EchoCli:
    def __init__(self,
                 arg_parser: ArgumentParser,
                 cmd_line: List[str] = None) -> None:
        if cmd_line is None:
            self._args = arg_parser.parse_args()
        else:
            self._args = arg_parser.parse_args(cmd_line)
        self._reader = SerialReader(self._args.baudrate, self._args.port)
        self._reader.read_bytes()


if __name__ == '__main__':
    parser = ArgumentParser("Echo LCS SER2 output to console",
                            parents=[CliBase.cli_parser()])
    EchoCli(parser)
