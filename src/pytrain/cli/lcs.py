#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
pylcs: open the LCS module configuration panel in its own window.

Follows the pycache pattern exactly: a CliBase subclass parses the arguments, and a
CommandBase subclass brings PyTrain up as a client, against a named server, or directly
against a Base 3, then runs the GUI. No requests are built here -- the panel itself is
what sends anything, through the GUI's own request queue.
"""

from __future__ import annotations

import logging
import sys
from argparse import ArgumentParser
from typing import List

from ..protocol.command_base import CommandBase
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope
from ..utils.argument_parser import PyTrainArgumentParser
from . import CliBase

log = logging.getLogger(__name__)


class LcsGuiCmd(CommandBase):
    """
    Run the stand-alone LCS configuration window.

    A special case of CommandBase where no requests are created nor sent: PyTrain
    initialization is all that is wanted from it.
    """

    def __init__(self, cli: LcsCli) -> None:
        self._cli = cli
        self._scope: CommandScope = cli.scope
        self._gui = None

        # with PyTrain initialization sorted out, initialize CommandBase.
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
    def gui(self):
        return self._gui

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
        from ..gui.controller.lcs_gui import LcsGui

        log.info("Opening LCS configuration window...")
        # No wait_for_sync(): the window opens now and populates when the Base 3 syncs.
        self._gui = LcsGui(
            width=self._cli.gui_width,
            height=self._cli.gui_height,
            scale_by=self._cli.scale_by,
            full_screen=self._cli.is_full_screen,
        )
        # The Tk event loop must own the process main thread; macOS aborts on an NSWindow
        # built anywhere else. This blocks here until the window is closed.
        self._gui.run_window()
        if self.pytrain is not None:
            self.pytrain.shutdown()

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class LcsCli(CliBase):
    """
    LCS module configuration window
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument(
            "-width",
            action="store",
            type=int,
            default=None,
            help="Window width, in pixels (480)",
        )
        parser.add_argument(
            "-height",
            action="store",
            type=int,
            default=None,
            help="Window height, in pixels (800)",
        )
        parser.add_argument(
            "-scale_by",
            action="store",
            type=float,
            default=1.0,
            help="Scale fonts and buttons by this factor (1.0)",
        )
        parser.add_argument(
            "-full_screen",
            action="store_true",
            help="Open the window full screen",
        )

        # Return parser
        return PyTrainArgumentParser("LCS configuration options", parents=[parser, cls.cli_parser()])

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._gui_width = self._args.width
        self._gui_height = self._args.height
        self._scale_by = self._args.scale_by
        self._full_screen = self._args.full_screen
        self._scope = CommandScope.SYSTEM
        try:
            cmd = LcsGuiCmd(self)
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)

    @property
    def scope(self) -> CommandScope:
        return CommandScope.SYSTEM

    @property
    def gui_width(self) -> int | None:
        return self._gui_width

    @property
    def gui_height(self) -> int | None:
        return self._gui_height

    @property
    def scale_by(self) -> float:
        return self._scale_by

    @property
    def is_full_screen(self) -> bool:
        return self._full_screen


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        LcsCli(cmd_line=args)
        return 0
    except Exception as e:
        sys.exit(f"{__file__}: error: {e}\n")
