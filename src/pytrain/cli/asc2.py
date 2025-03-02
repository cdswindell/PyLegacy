#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import logging
from argparse import ArgumentParser
from typing import List

from . import CliBase
from ..pdi.asc2_req import Asc2Req
from ..pdi.constants import PdiCommand, Asc2Action
from ..protocol.command_base import CommandBase
from ..protocol.constants import CommandScope
from ..utils.argument_parser import PyTrainArgumentParser

log = logging.getLogger(__name__)


class Asc2Cmd(CommandBase):
    def __init__(self, tmcc_id: int, req: Asc2Req, server: str = None) -> None:
        if tmcc_id < 1 or tmcc_id > 99:
            raise ValueError("Asc2 ID must be between 1 and 99")
        super().__init__(None, req, tmcc_id, CommandScope.ASC2, server=server)
        self._command = self._build_command()

    def _build_command(self) -> bytes | None:
        return self.command_req.as_bytes

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class Asc2Cli(CliBase):
    """
    Issue Asc2 Commands.
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        from . import PROGRAM_NAME

        asc2_parser = PyTrainArgumentParser(add_help=False)
        asc2_parser.add_argument("asc2", metavar="Asc2 TMCC ID", type=int, help="Asc2 to fire")

        group = asc2_parser.add_mutually_exclusive_group()
        group.add_argument(
            "-on",
            action="store_true",
            help="Turn Asc2 on",
        )
        group.add_argument(
            "-off",
            action="store_true",
            help="Turn Asc2 off",
        )
        group.add_argument(
            "-hold",
            nargs="?",
            type=float,
            const=1.0,
            help="Turn Asc2 on for specified time",
        )

        asc2_parser.add_argument(
            "-server",
            action="store",
            help=f"IP Address of {PROGRAM_NAME} server, if client. Server communicates with Base 3/LCS SER2",
        )
        # fire command
        return PyTrainArgumentParser(
            "Operate specified Asc2 (1 - 99)",
            parents=[asc2_parser, cls.multi_parser()],
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._asc2 = self._args.asc2
        self._time = self._args.hold if self._args.hold else 0.0
        self._state = 0 if self._args.off is True else 1
        # adjust time and duration parameters
        if self._state == 1:
            if self._time > 2.55 or (self._args.duration and self._args.duration > 2.55):
                # pik bigger number
                time = self._time if self._time else 0
                duration = self._args.duration if self._args.duration else 0
                self._args.duration = max(time, duration)
                self._time = 0.250 if self.is_server else 0.600
                self._args.duration -= self._time
                self._args.duration = self._args.duration if self._args.duration > 0.0 else 0.0
            elif self._args.duration and self._args.duration <= 2.55:
                self._time = self._args.duration
                self._args.duration = 0
            elif self._time:
                self._args.duration = 0
            else:
                self._time = self._args.duration = 0.0
        else:
            self._time = self._args.duration = 0.0
        req = Asc2Req(self._asc2, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=self._state, time=self._time)
        try:
            cmd = Asc2Cmd(self._asc2, req, server=self._server)
            if self.do_fire:
                cmd.fire(server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
