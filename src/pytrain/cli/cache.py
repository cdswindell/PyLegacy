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
from typing import List

from ..db.cache_sync import CacheSyncManager
from ..db.prod_info import ProdInfo
from ..protocol.command_base import CommandBase
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope
from ..utils.argument_parser import PyTrainArgumentParser, UniqueChoice
from . import CliBase

log = logging.getLogger(__name__)


class CacheClearCmd(CommandBase):
    """
    Clear cache directories

    This is a special case of CommandBase where no actual requests are created nor sent.
    """

    def __init__(self, cli: CacheCli) -> None:
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


class CacheCmd(CommandBase):
    """
    Command to clear Lionel Base 3 database records.

    This is a special case of CommandBase where no actual requests are created nor sent.
    """

    def __init__(self, cli: CacheCli) -> None:
        self._cli = cli
        self._scope: CommandScope = cli.scope

        if self._cli.cache_command is None:
            raise ValueError("Cache command required")

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

        if self._cli.cache_command == "sync":
            log.info("Syncing cache...")
            cache_sync = CacheSyncManager.current()
            if cache_sync is None:
                if self.pytrain.is_client:
                    log.warning(
                        "Cache sync skipped: the connected server does not advertise cache sync support. "
                        "Upgrade the server or restart it with cache sync enabled to accept client cache files."
                    )
                else:
                    log.warning(
                        "Cache sync skipped: cache sync is disabled or unavailable. Restart without -no_cache_sync."
                    )
                return
            cache_sync.force_sync()
        else:
            raise NotImplementedError(f"Cache command '{self._cli.cache_command}' not implemented.")

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class CacheCli(CliBase):
    """
    Cache commands
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument(
            "command",
            metavar="Record type",
            nargs="?",
            type=UniqueChoice(["clear", "sync"]),
            default="engine",
            help="Cache operation",
        )

        parser.add_argument(
            "-verbose",
            action="store_true",
            help="Verbose",
        )

        # Return parser
        return PyTrainArgumentParser("Cache options", parents=[parser, cls.cli_parser()])

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._args = self._args
        self._cache_command = self._args.command
        self._verbose = self._args.verbose
        self._scope = CommandScope.SYSTEM
        try:
            if self._cache_command == "clear":
                cmd = CacheClearCmd(self)
            else:
                cmd = CacheCmd(self)
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM

    @property
    def cache_command(self) -> str:
        return self._cache_command

    @property
    def is_verbose(self) -> bool:
        return self._verbose


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        CacheCli(cmd_line=args)
        return 0
    except Exception as e:
        sys.exit(f"{__file__}: error: {e}\n")
