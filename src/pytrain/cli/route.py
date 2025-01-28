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

from . import CliBaseTMCC
from ..protocol.tmcc1.route_cmd import RouteCmd as RouteCmdTMCC1
from ..protocol.tmcc2.route_cmd import RouteCmd as RouteCmdTMCC2
from ..utils.argument_parser import PyTrainArgumentParser

log = logging.getLogger(__name__)


class RouteCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        route_parser = PyTrainArgumentParser(add_help=False)
        route_parser.add_argument("route", metavar="Route", type=int, help="route to fire")
        return PyTrainArgumentParser(
            "Fire specified route (1 - 99)", parents=[route_parser, cls.command_format_parser(), cls.cli_parser()]
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self.route = self._args.route
        try:
            if self.is_tmcc1:
                cmd = RouteCmdTMCC1(self.route, baudrate=self._baudrate, port=self._port, server=self._server)
            else:
                cmd = RouteCmdTMCC2(self.route, baudrate=self._baudrate, port=self._port, server=self._server)
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
