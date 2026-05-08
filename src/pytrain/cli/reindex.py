#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import logging
from argparse import ArgumentParser
from typing import List

from . import CliBase
from ..protocol.command_base import CommandBase
from ..protocol.constants import CommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT
from ..utils.argument_parser import PyTrainArgumentParser, UniqueChoice

log = logging.getLogger(__name__)


class ReindexCmd(CommandBase):
    def __init__(self, scope: CommandScope, verbose: bool) -> None:
        self._verbose = verbose
        if scope is None:
            raise ValueError("Scope must be specified")
        super().__init__(None, None, 1, scope=scope, server=None)
        self._command = self._build_command()

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass

    def send(
        self,
        repeat: int = None,
        delay: float = None,
        duration: float = None,
        interval: int = None,
        shutdown: bool = False,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ):
        print("Hello World!!")


class ReindexCli(CliBase):
    """
    Reindex Lionel Base 3 Database
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        parser = PyTrainArgumentParser("Reindex Lionel Base 3 database records")
        parser.add_argument(
            "scope",
            metavar="Record type",
            type=UniqueChoice(["engine", "train"]),
            help="Base 3 record type to reindex",
        )

        parser.add_argument(
            "-verbose",
            action="store_true",
            help="Verbose",
        )

        # Return parser
        return parser

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._scope = self._args.scope
        self._verbose = self._args.verbose
        try:
            cmd = ReindexCmd(CommandScope.ENGINE, self._verbose)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
