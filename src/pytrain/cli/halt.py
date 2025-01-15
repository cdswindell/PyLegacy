#!/usr/bin/env python3
#
import logging
from typing import List

from . import CliBaseTMCC
from ..protocol.constants import CommandSyntax
from ..protocol.tmcc1.halt_cmd import HaltCmd as HaltCmdTMCC1
from ..protocol.tmcc2.halt_cmd import HaltCmd as HaltCmdTMCC2
from ..utils.argument_parser import ArgumentParser

log = logging.getLogger(__name__)


class HaltCli(CliBaseTMCC):
    @classmethod
    def command_parser(cls):
        return ArgumentParser(
            "Emergency halt; stop all engines and trains",
            parents=[cls.train_parser(), cls.command_format_parser(CommandSyntax.TMCC), cls.cli_parser()],
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        try:
            if self.is_train_command or self.is_tmcc2:
                cmd = HaltCmdTMCC2(baudrate=self._baudrate, port=self._port, server=self._server)
            else:
                cmd = HaltCmdTMCC1(baudrate=self._baudrate, port=self._port, server=self._server)
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
