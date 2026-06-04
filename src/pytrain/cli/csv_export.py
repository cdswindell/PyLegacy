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
from pathlib import Path
from typing import List

from ..db.component_state import ComponentState
from ..protocol.command_base import CommandBase
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope
from ..utils.argument_parser import PyTrainArgumentParser, UniqueChoice
from . import CliBase

log = logging.getLogger(__name__)


class CsvCmd(CommandBase):
    """
    Command to clear Lionel Base 3 database records.

    This is a special case of CommandBase where no actual requests are created nor sent.
    """

    def __init__(self, cli: CsvCli) -> None:
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

        self._command = self._build_command()

    @property
    def scope(self) -> CommandScope:
        return self._cli.scope

    @property
    def is_real_time(self) -> bool:
        return self._cli.is_real_time

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

        if self.is_verbose:
            log.info(f"Exporting {self._scope.title} records to '{self._cli.output_file}'...")

        entries = self._pytrain.store.get_all(self._scope)
        if entries:
            cnt = 0
            with open(self._cli.output_file, "w", newline="") as f:
                dw = ComponentState.get_cvs_dict_writer(self.scope, f, include_state=self.is_real_time)
                if self._cli.is_header:
                    dw.writeheader()
                for entry in entries:
                    if entry.is_name:
                        dw.writerow(entry.as_csv(include_state=self.is_real_time))
                        cnt += 1
            if self.is_verbose:
                log.info(f"Exported {cnt} {self._scope.title} records(s)to '{self._cli.output_file}'")
        else:
            if self.is_verbose:
                log.info(f"No {self._scope.title} records found to export")

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class CsvCli(CliBase):
    """
    Export Lionel Base 3 Database records as CSV files
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument(
            "scope",
            metavar="Record type",
            nargs="?",
            type=UniqueChoice(["accessory", "engine", "route", "switch", "train"]),
            default="engine",
            help="Record type to export",
        )

        parser.add_argument(
            "-output",
            metavar="File Name",
            action="store",
            type=str,
            help="Output file path (default: <record type>.csv)",
        )

        parser.add_argument(
            "-no_header",
            action="store_true",
            help="Omit column headers",
        )

        parser.add_argument(
            "-state",
            action="store_true",
            help="Include real time state information",
        )

        parser.add_argument(
            "-verbose",
            action="store_true",
            help="Verbose",
        )

        # Return parser
        return PyTrainArgumentParser("Export Lionel Base 3 database in CSV format", parents=[parser, cls.cli_parser()])

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._args = self._args
        self._no_header = self._args.no_header
        self._real_time = self._args.state
        self._output_file = self._args.output
        self._verbose = self._args.verbose
        try:
            self._scope = CommandScope.by_prefix(self._args.scope, True)
            if self._output_file is None:
                self._output_file = Path(f"{self._scope.name.lower()}.csv")
            else:
                self._output_file = Path(self._output_file)
                if not self._output_file.suffix:
                    self._output_file = self._output_file.with_suffix(".csv")
            cmd = CsvCmd(self)
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def is_header(self) -> bool:
        return not self._no_header

    @property
    def output_file(self) -> Path:
        return self._output_file

    @property
    def is_verbose(self) -> bool:
        return self._verbose

    @property
    def is_real_time(self) -> bool:
        return self._real_time


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        CsvCli(cmd_line=args)
        return 0
    except Exception as e:
        sys.exit(f"{__file__}: error: {e}\n")
