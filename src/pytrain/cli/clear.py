#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

import logging
import sys
from argparse import ArgumentParser
from threading import Thread
from typing import List

from ..db.prod_info import ProdInfo
from ..protocol.command_base import CommandBase
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope, PROGRAM_NAME
from ..utils.argument_parser import PyTrainArgumentParser, UniqueChoice
from . import CliBase

log = logging.getLogger(__name__)


class ClearCacheCmd(CommandBase):
    """
    Clear cache directories

    This is a special case of CommandBase where no actual requests are created nor sent.
    """

    def __init__(self, cli: ClearCli) -> None:
        self._cli = cli
        self._scope: CommandScope = cli.scope

        # with PyTrain initialization sorted out, initialize CommandBase and Thread.
        # If we are stand-alone, set daemon to False, as we need the process to continue running.
        CommandBase.__init__(
            self,
            None,
            None,
            1,
            scope=self._scope,
            server=self._cli.args.server if "server" in self._cli.args else None,
            client=self._cli.args.client if "client" in self._cli.args else False,
            base=self._cli.args.base if "base" in self._cli.args else None,
        )
        self._command = self._build_command()

    @property
    def scope(self) -> CommandScope:
        return self._cli.scope

    @property
    def is_verbose(self) -> bool:
        return self._cli.is_verbose

    # noinspection PyTypeChecker
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
        log.info("Clearing cache...")
        ProdInfo.clear_caches(preserve_custom=True, verbose=self.is_verbose)

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class ClearCmd(CommandBase, Thread):
    """
    Command to clear Lionel Base 3 database records.

    This is a special case of CommandBase where no actual requests are created nor sent.
    """

    def __init__(self, cli: ClearCli) -> None:
        self._cli = cli
        self._scope: CommandScope = cli.scope

        if self._cli.scope is None:
            raise ValueError("Scope must be specified")

        # with PyTrain initialization sorted out, initialize CommandBase and Thread.
        # If we are stand-alone, set daemon to False, as we need the process to continue running.
        CommandBase.__init__(
            self,
            None,
            None,
            1,
            scope=self._scope,
            server=self._cli.args.server if "server" in self._cli.args else None,
            client=self._cli.args.client if "client" in self._cli.args else False,
            base=self._cli.args.base if "base" in self._cli.args else None,
        )
        Thread.__init__(self, daemon=self.is_daemon, name="ClearCmdThread")

        self._command = self._build_command()

    @property
    def scope(self) -> CommandScope:
        return self._cli.scope

    @property
    def is_force(self) -> bool:
        return self._cli.is_force

    @property
    def is_verbose(self) -> bool:
        return self._cli.is_verbose

    # noinspection PyTypeChecker
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
        # pause until Base 3 sync complete
        self.wait_for_sync()

        kw = "Clearing"
        log.info(f"{kw} Base 3 {self._scope.title} database record...")

        raise NotImplementedError(f"Clear command not implemented for {self._scope.plural}")

    def run(self) -> None:
        try:
            self.pytrain.pdi_listener.subscribe_any(self)
        finally:
            self.pytrain.pdi_listener.unsubscribe_any(self)

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class ClearCli(CliBase):
    """
    Clear Lionel Base 3 Database
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument(
            "scope",
            metavar="Record type",
            nargs="?",
            type=UniqueChoice(["accessory", "engine", "route", "switch", "train", "caches"]),
            default="engine",
            help="Element type to clear",
        )

        parser.add_argument(
            "-verbose",
            action="store_true",
            help="Verbose",
        )

        # Return parser
        return PyTrainArgumentParser(
            f"Clear {PROGRAM_NAME} database record or element", parents=[parser, cls.cli_parser()]
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._args = self._args
        self._verbose = self._args.verbose
        try:
            if self._args.scope == "caches":
                self._scope = CommandScope.SYSTEM
                cmd = ClearCacheCmd(self)
            else:
                self._scope = CommandScope.by_prefix(self._args.scope, True)
                cmd = ClearCmd(self)
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def is_verbose(self) -> bool:
        return self._verbose


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        ClearCli(cmd_line=args)
        return 0
    except Exception as e:
        sys.exit(f"{__file__}: error: {e}\n")
