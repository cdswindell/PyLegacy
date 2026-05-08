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
import time
from argparse import ArgumentParser
from threading import Condition, Event, Thread
from typing import List

from . import CliBase
from ..pdi.base_req import BaseReq
from ..pdi.constants import PdiCommand
from ..pdi.pdi_req import PdiReq
from ..protocol.command_base import CommandBase
from ..protocol.constants import CommandScope, DEFAULT_BAUDRATE, DEFAULT_PORT
from ..utils.argument_parser import PyTrainArgumentParser, UniqueChoice

log = logging.getLogger(__name__)


class ReindexCmd(CommandBase, Thread):
    """
    Command to reindex Lionel Base 3 database records.

    This is a special case of CommandBase where no actual requests are created nor sent.
    """

    def __init__(self, cli: ReindexCli) -> None:
        from .pytrain import PyTrain

        self._cli = cli
        self._scope: CommandScope = cli.scope()
        if self._cli.scope is None:
            raise ValueError("Scope must be specified")
        CommandBase.__init__(self, None, None, 1, scope=self._scope, server=None)
        Thread.__init__(self, daemon=True, name="ReindexCmdThread")
        self._command = self._build_command()
        self._pytrain = PyTrain.current()
        self._entries = None
        self._waiting_for = dict()
        self._cv = Condition()
        self._ev = Event()

    @property
    def is_verbose(self) -> bool:
        return self._cli.verbose()

    def __call__(self, cmd: PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if cmd and cmd.scope == self._scope:
            with self._cv:
                self._waiting_for.pop(cmd.as_key, None)
        else:
            return

        if isinstance(cmd, BaseReq) and cmd.pdi_command == PdiCommand.BASE_MEMORY:
            print(f"Received PDI command: {cmd} {cmd.forward_link}")
            req = None
            if cmd.forward_link not in {255, 101}:
                print(f"Next {self._scope.title} {cmd.forward_link}")
                req = BaseReq(cmd.forward_link, PdiCommand.BASE_MEMORY, scope=self._scope)

            if req:
                with self._cv:
                    self._waiting_for[req.as_key] = req
                self._pytrain.pdi_dispatcher.enqueue_command(req)
            else:
                with self._cv:
                    if not self._waiting_for:
                        self._ev.set()
                        self._cv.notify_all()

    def run(self) -> None:
        self._pytrain.pdi_listener.subscribe_any(self)
        req = BaseReq(100, PdiCommand.BASE_MEMORY, scope=self._scope)
        if req:
            with self._cv:
                self._waiting_for[req.as_key] = req
            self._pytrain.pdi_dispatcher.enqueue_command(req)

        # now wait for all responses; this will not track LCS devices reporting their config
        # because of the AllReq
        total_time = 0
        started_at = time.monotonic()
        ev_set = False
        incr = 0.25
        timeout = 15
        while total_time < timeout:  # only listen for 2 minutes
            self._ev.wait(incr)
            elapsed = round(time.monotonic() - started_at)
            # Awaits responses with timeout; forces sync completion if prolonged
            if self._ev.is_set() or (ev_set is True) or len(self._waiting_for) == 0:
                self._ev.clear()
                ev_set = True
                total_time = 0
                if elapsed >= 0:
                    log.info(f"Initial state loaded from Lionel Base: {elapsed:.2f} seconds elapsed.")
                    break
            else:
                total_time += incr
        if total_time >= timeout:
            log.warning("Timed out waiting for database state from Lionel Base")

        self._pytrain.pdi_listener.unsubscribe_any(self)

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
        kw = "Checking" if self._cli.check() else "Reindexing"
        log.info(f"{kw} Base 3 2-digit {self._scope.title} database records...")

        entries = self._pytrain.store.get_all(self._scope)
        if entries:
            # strip out 4D entries
            entries = [e for e in entries if 1 <= e.tmcc_id < 99]

        if entries is None:
            log.warning(f"No {self._scope.title} records found")
            return
        entries.sort(key=lambda e: (e.road_name, e.road_number, e.tmcc_id))
        if self.is_verbose:
            log.info(f"Evaluating {len(entries)} {self._scope.title} records...")
        self._entries = entries
        self.start()

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


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
            nargs="?",
            type=UniqueChoice(["engine", "train"]),
            default="engine",
            help="Base 3 record type to reindex",
        )

        parser.add_argument(
            "-check",
            action="store_true",
            help="Verbose",
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
        self._args = self._args
        self._verbose = self._args.verbose
        self._check = self._args.check
        try:
            self._scope = CommandScope.by_name(self._args.scope, True)
            cmd = ReindexCmd(self)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)

    def scope(self) -> CommandScope:
        return self._scope

    def check(self) -> bool:
        return self._check

    def verbose(self) -> bool:
        return self._verbose
