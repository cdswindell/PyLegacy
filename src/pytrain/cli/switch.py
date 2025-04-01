#!/usr/bin/env python3

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

#
import logging
from argparse import ArgumentParser
from typing import List

from ..protocol.tmcc1.switch_cmd import SwitchCmd
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum
from ..utils.argument_parser import PyTrainArgumentParser
from . import CliBase

log = logging.getLogger(__name__)


class SwitchCli(CliBase):
    @classmethod
    def command_parser(cls) -> ArgumentParser:
        sw_parser = PyTrainArgumentParser(add_help=False)
        sw_parser.add_argument("switch", metavar="Switch Number", type=int, help="switch to fire")
        group = sw_parser.add_mutually_exclusive_group()
        group.add_argument(
            "-through",
            action="store_const",
            const=TMCC1SwitchCommandEnum.THRU,
            dest="command",
            help="Throw Through",
        )
        group.add_argument(
            "-out", action="store_const", const=TMCC1SwitchCommandEnum.OUT, dest="command", help="Throw Out"
        )
        group.add_argument(
            "-address",
            action="store_const",
            const=TMCC1SwitchCommandEnum.SET_ADDRESS,
            dest="command",
            help="Set switch address",
        )
        group.set_defaults(command=TMCC1SwitchCommandEnum.THRU)
        return PyTrainArgumentParser("Throw specified switch (1 - 99)", parents=[sw_parser, cls.cli_parser()])

    """
        Throw the specified switch.

        Currently only available via the TMCC1 command format
    """

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._switch = self._args.switch
        self._switch_state = self._args.command
        try:
            cmd = SwitchCmd(
                self._switch, self._switch_state, baudrate=self._baudrate, port=self._port, server=self._server
            )
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
