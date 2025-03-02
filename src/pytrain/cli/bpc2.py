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
from ..pdi.bpc2_req import Bpc2Req
from ..pdi.constants import PdiCommand, Bpc2Action
from ..protocol.command_base import CommandBase
from ..protocol.constants import CommandScope, PROGRAM_NAME
from ..utils.argument_parser import PyTrainArgumentParser

log = logging.getLogger(__name__)


class Bpc2Cmd(CommandBase):
    def __init__(self, tmcc_id: int, req: Bpc2Req, server: str = None) -> None:
        if tmcc_id < 1 or tmcc_id > 99:
            raise ValueError("Bpc2 ID must be between 1 and 99")
        super().__init__(None, req, tmcc_id, CommandScope.BPC2, server=server)
        self._command = self._build_command()

    def _build_command(self) -> bytes | None:
        return self.command_req.as_bytes

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class Bpc2Cli(CliBase):
    """
    Issue Bpc2 Commands.
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument("bpc2", metavar="Bbc2 TMCC ID", type=int, help="Bpc2 to fire")

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-on",
            action="store_true",
            help="Turn block on",
        )
        group.add_argument(
            "-off",
            action="store_true",
            help="Turn block off",
        )

        parser.add_argument(
            "-server",
            action="store",
            help=f"IP Address of {PROGRAM_NAME} server, if client. Server communicates with Base 3/LCS SER2",
        )
        # fire command
        return PyTrainArgumentParser("Operate specified Bpc2 Track power district (1 - 99)", parents=[parser])

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._bpc2 = self._args.bpc2
        self._state = 1 if self._args.on is True else 0
        req = Bpc2Req(self._bpc2, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, state=self._state)

        try:
            cmd = Bpc2Cmd(self._bpc2, req, server=self._server)
            if self.do_fire:
                cmd.fire(server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
