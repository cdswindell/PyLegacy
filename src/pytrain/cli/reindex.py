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

from ..pdi.base_req import BaseReq
from ..pdi.constants import PdiCommand
from ..pdi.pdi_req import PdiReq
from ..protocol.command_base import CommandBase
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope
from ..utils.argument_parser import PyTrainArgumentParser, UniqueChoice
from . import CliBase

log = logging.getLogger(__name__)


class ReindexCmd(CommandBase, Thread):
    """
    Command to reindex Lionel Base 3 database records.

    This is a special case of CommandBase where no actual requests are created nor sent.
    """

    def __init__(self, cli: ReindexCli) -> None:
        self._cli = cli
        self._scope: CommandScope = cli.scope

        if self._cli.scope is None:
            raise ValueError("Scope must be specified")

        # with PyTrain initialization sorted out, initialize CommandBase and Thread
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
        Thread.__init__(self, daemon=self.is_daemon, name="ReindexCmdThread")

        self._command = self._build_command()
        self._entries = None
        self._entries_map = {}
        self._frm_found = self._lrm_found = self._bad_found = False
        self._waiting_for = dict()
        self._db_order = None
        self._correct_order = []
        self._cv = Condition()
        self._ev = Event()
        self._first_pass_complete = False

    @property
    def scope(self) -> CommandScope:
        return self._cli.scope

    @property
    def is_force(self) -> bool:
        return self._cli.is_force

    @property
    def is_verbose(self) -> bool:
        return self._cli.is_verbose

    @property
    def is_validate(self) -> bool:
        return self._cli.is_validate

    def __call__(self, cmd: PdiReq) -> None:
        """
        Callback specified in the Subscriber protocol used to send events to listeners
        """
        if not self.is_synchronized():
            return

        if cmd and cmd.scope == self._scope:
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f"Received: {cmd}")
            with self._cv:
                key = cmd.as_key
                if key not in self._waiting_for:
                    log.warning(f"Unexpected response: {key}: {cmd}")
                self._waiting_for.pop(key, None)
        else:
            return

        if not self._first_pass_complete and isinstance(cmd, BaseReq) and cmd.pdi_command == PdiCommand.BASE_MEMORY:
            if self.is_verbose:
                log.info(f"{self._scope.title} {cmd.tmcc_id} prev: {cmd.reverse_link} next: {cmd.forward_link}")

            if cmd.tmcc_id == 100 and cmd.reverse_link == 101 and 1 <= cmd.forward_link < 99:
                self._frm_found = True
                self._db_order = self._walk_links(cmd.forward_link)
            elif cmd.tmcc_id < 99:
                self._db_order.append(cmd.tmcc_id)
            else:
                self._bad_found = True
                log.warning(f"Unexpected Base 3 record: {cmd.tmcc_id} {cmd.reverse_link} {cmd.forward_link}")

        with self._cv:
            if not self._waiting_for:
                self._ev.set()
                self._cv.notify_all()

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

        kw = "Validating" if self._cli.is_validate else "Reindexing"
        log.info(f"{kw} Base 3 2-Digit {self._scope.title} database records...")

        entries = self._pytrain.store.get_all(self._scope)
        if entries:
            # strip out 4D entries and entries that have empty database records
            entries = [e for e in entries if 1 <= e.tmcc_id < 99 and e.is_road_name]

        if entries is None:
            log.warning(f"No {self._scope.title} records found")
            return
        entries.sort(key=lambda e: (e.road_name, e.road_number, e.tmcc_id))
        if self.is_verbose:
            log.info(f"Evaluating {len(entries)} {self._scope.title} records...")
        self._entries = entries
        self._entries_map = {e.tmcc_id: e for e in entries}
        self._correct_order = [e.tmcc_id for e in entries]
        self.start()

    def run(self) -> None:
        try:
            self.pytrain.pdi_listener.subscribe_any(self)

            # get record 100; it contains a link to the first engine, alphabetically
            self._dispatch_req(BaseReq(100, PdiCommand.BASE_MEMORY, scope=self._scope))

            timeout = 15
            total_time = self._wait_for_responses(timeout=timeout)
            if total_time >= timeout:
                log.warning("Timed out waiting for database state from Lionel Base")
            self._first_pass_complete = True

            if self._db_order is None and self._entries and self._entries[0].tmcc_id:
                self._db_order = self._walk_links(self._entries[0].tmcc_id)
            elif self._db_order is None:
                self._db_order = []

            all_good = (
                not self._bad_found and self._frm_found and self._lrm_found and self._db_order == self._correct_order
            )
            if self._cli.is_validate:
                if not all_good:
                    num_obs = len(self._db_order)
                    log.warning(f"{self._scope.title} record(s) mismatch:")
                    if not self._frm_found:
                        log.warning("First record link not found")
                    if not self._lrm_found:
                        log.warning("Last record link not found")
                    if self._db_order != self._correct_order:
                        log.warning(f"{len(self._entries)} records found, only {num_obs} linked; reindex needed")
                        if self.is_verbose:
                            for i, e in enumerate(self._entries):
                                if i >= num_obs or e.tmcc_id != self._db_order[i]:
                                    log.warning(
                                        f"{e.tmcc_id:02} {e.road_name} {e.road_number} "
                                        f"prev:{e.prev_link} next:{e.next_link}"
                                    )
                else:
                    log.info(f"All {self._scope.title} records match; no re-index needed.")
            else:
                if all_good and not self.is_force:
                    log.info(f"All {self._scope.title} records match; re-index not done.")
                    log.info(
                        f"Use -force to re-index {self._scope.title} records; "
                        f"this may take a while depending on the number of records"
                    )
                else:
                    self._do_reindex()
                    log.info(f"{self._scope.title} records re-indexed and successfully written to the Base 3 database")
        finally:
            self.pytrain.pdi_listener.unsubscribe_any(self)

    def _wait_for_responses(self, incr: float = 0.25, timeout: int = 15) -> float:
        # now wait for all responses;
        total_time = 0
        started_at = time.monotonic()
        ev_set = False
        self._ev.clear()
        if self.is_verbose:
            log.info(f"Waiting for {len(self._waiting_for)} responses...")
        while total_time < timeout:  # only listen for 2 minutes
            self._ev.wait(incr)
            elapsed = round(time.monotonic() - started_at)
            # Awaits responses with timeout; forces sync completion if prolonged
            if self._ev.is_set() or (ev_set is True) or len(self._waiting_for) == 0:
                self._ev.clear()
                ev_set = True
                total_time = 0
                if elapsed >= 0:
                    break
            else:
                total_time += incr
        if self.is_verbose:
            log.info(f"{len(self._waiting_for)} responses remain...")
        return total_time

    def _do_reindex(self, pause_for: float = 0.06):
        log.warning(f"Reindexing {len(self._correct_order)} {self._scope.title} records...")
        prev_rec = 100
        num_entries = len(self._correct_order)
        for i, tmcc_id in enumerate(self._correct_order):
            if i < num_entries - 1:
                next_rec = self._correct_order[i + 1]
            else:
                next_rec = 101
            if self.is_verbose:
                log.info(f"Reindexing {self._scope.title} {tmcc_id:02} prev: {prev_rec} next: {next_rec}")
            req = self._build_links_update_req(tmcc_id, prev_rec, next_rec)
            self._dispatch_req(req, wait_for=False)
            time.sleep(pause_for)
            prev_rec = tmcc_id

        # write final record
        tmcc_id = 100
        prev_rec = 101
        next_rec = self._correct_order[0]
        if self.is_verbose:
            log.info(f"Setting {self._scope.title} {tmcc_id:02} to prev: {prev_rec} next: {next_rec}")
        req = self._build_links_update_req(tmcc_id, prev_rec, next_rec)
        self._dispatch_req(req, wait_for=False)

        # requery records
        for tmcc_id in self._correct_order:
            time.sleep(pause_for)
            self._dispatch_req(BaseReq(tmcc_id, PdiCommand.BASE_MEMORY, scope=self._scope))

        # wait for requery responses to post
        timeout = 15
        total_time = self._wait_for_responses(timeout=timeout)
        if total_time >= timeout:
            log.warning("Timed out waiting for reindex responses from Lionel Base 3")
        else:
            log.warning("... Reindexing complete.")

    def _dispatch_req(self, req: BaseReq, wait_for: bool = True) -> None:
        if req:
            with self._cv:
                if wait_for:
                    self._waiting_for[req.as_key] = req
            self.pytrain.pdi_dispatcher.enqueue_command(req)

    def _build_links_update_req(self, tmcc_id: int, prev_link: int, next_link: int) -> BaseReq:
        # Note: this is hard-wired to update the prev and next record links that are stored in
        # bytes 0 and 1 of the Base 3 database record.
        data_bytes = bytes([prev_link, next_link])
        assert len(data_bytes) == 2
        return BaseReq(
            tmcc_id,
            pdi_command=PdiCommand.BASE_MEMORY,
            flags=0xC2,
            scope=self._scope,
            start=0,
            data_length=2,
            data_bytes=data_bytes,
        )

    def _walk_links(self, first_tmcc_id: int) -> List[int]:
        db_list = []
        entry = self._entries_map.get(first_tmcc_id, None)
        while entry:
            db_list.append(entry.tmcc_id)
            if entry.next_link == 101:
                self._lrm_found = True
            if self.is_verbose:
                log.info(
                    f"Walking {entry.tmcc_id} {entry.road_name} {entry.road_number} {entry.prev_link} {entry.next_link}"
                )
            if entry.next_link not in {100, 101, 255}:
                entry = self._entries_map.get(entry.next_link, None)
            else:
                entry = None

        return db_list

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
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument(
            "scope",
            metavar="Record type",
            nargs="?",
            type=UniqueChoice(["acc", "engine", "route", "switch", "train"]),
            default="engine",
            help="Base 3 record type to reindex",
        )

        parser.add_argument(
            "-check",
            action="store_true",
            help="Validate record order only; do not re-index",
        )

        parser.add_argument(
            "-force",
            action="store_true",
            help="Force reindexing",
        )

        parser.add_argument(
            "-verbose",
            action="store_true",
            help="Verbose",
        )

        # Return parser
        return PyTrainArgumentParser("Reindex Lionel Base 3 database records", parents=[parser, cls.cli_parser()])

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._args = self._args
        self._verbose = self._args.verbose
        self._check = self._args.check
        self._force = self._args.force
        try:
            self._scope = CommandScope.by_name(self._args.scope, True)
            cmd = ReindexCmd(self)
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def is_validate(self) -> bool:
        return self._check

    @property
    def is_force(self) -> bool:
        return self._force

    @property
    def is_verbose(self) -> bool:
        return self._verbose
