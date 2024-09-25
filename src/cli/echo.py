#!/usr/bin/env python3
#
import time
from datetime import datetime
from typing import List

from src.cli.cli_base import CliBase
from src.comm.command_listener import CommandListener, _CommandDispatcher
from src.protocol.command_req import CommandReq
from src.protocol.tmcc1.tmcc1_constants import TMCC1SwitchState
from src.utils.argument_parser import ArgumentParser


class EchoCli:
    def __init__(self,
                 arg_parser: ArgumentParser,
                 cmd_line: List[str] = None) -> None:
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
        print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {cmd}")


if __name__ == '__main__':
    parser = ArgumentParser("Echo LCS SER2 output to console",
                            parents=[CliBase.cli_parser()])
    EchoCli(parser)

    r = CommandReq.build(TMCC1SwitchState.OUT, 20)
    time.sleep(5)
    _CommandDispatcher().offer(r)
