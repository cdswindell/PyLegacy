#!/usr/bin/env python3
#
import logging
from datetime import datetime
from typing import List

from . import CliBase
from ..comm.command_listener import CommandListener
from ..protocol.command_req import CommandReq
from ..utils.argument_parser import ArgumentParser

log = logging.getLogger(__name__)


class EchoCli:
    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None) -> None:
        if arg_parser is None:
            arg_parser = ArgumentParser("Echo LCS SER2 output to console", parents=[CliBase.cli_parser()])
        if cmd_line is None:
            self._args = arg_parser.parse_args()
        else:
            self._args = arg_parser.parse_args(cmd_line)
        try:
            print(f"Echoing commands received by the LCS Ser2 on {self._args.port} (Ctrl-C to quit)")
            self._listener = CommandListener(self._args.baudrate, self._args.port)
            self._listener.subscribe_any(self)
        except KeyboardInterrupt:
            self._listener.shutdown()

    def __call__(self, cmd: CommandReq) -> None:
        log.info(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {cmd}")
