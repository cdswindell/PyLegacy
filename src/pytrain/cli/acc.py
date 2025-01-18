#!/usr/bin/env python3
#
import logging
from typing import List

from . import CliBase, DataAction
from ..protocol.tmcc1.acc_cmd import AccCmd

from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.argument_parser import ArgumentParser

log = logging.getLogger(__name__)

AUX_OPTIONS_MAP = {
    "on": "ON",
    "off": "OFF",
    "opt1": "OPT_ONE",
    "opt2": "OPT_TWO",
}


class AccCli(CliBase):
    @classmethod
    def command_parser(cls) -> ArgumentParser:
        acc_parser = ArgumentParser(add_help=False)
        acc_parser.add_argument("acc", metavar="Accessory Number", type=int, help="accessory to fire")

        aux_group = acc_parser.add_mutually_exclusive_group()
        aux_group.add_argument(
            "-aux1",
            dest="aux1",
            choices=["on", "off", "opt1", "opt2"],
            nargs="?",
            type=str,
            const="opt1",
        )
        aux_group.add_argument(
            "-aux2",
            dest="aux2",
            choices=["on", "off", "opt1", "opt2"],
            nargs="?",
            type=str,
            const="opt1",
        )
        aux_group.add_argument(
            "-n",
            action=DataAction,
            dest="data",
            choices=range(0, 10),
            metavar="0 - 9",
            type=int,
            nargs="?",
            default=1,
            const=TMCC1AuxCommandEnum.NUMERIC,
            help="Numeric value",
        )
        aux_group.add_argument(
            "-address",
            action="store_const",
            const=TMCC1AuxCommandEnum.SET_ADDRESS,
            dest="command",
            help="Set accessory address",
        )
        # fire command
        return ArgumentParser("Operate specified accessory (1 - 99)", parents=[acc_parser, cls.cli_parser()])

    """
        Issue Accessory Commands.

        Currently only available via the TMCC1 command format
    """

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._acc = self._args.acc
        self._command = self._args.command
        self._data = self._args.data if "data" in self._args else 0
        self._aux1 = self._args.aux1
        self._aux2 = self._args.aux2
        if self._args.aux1 and self._args.aux1 in AUX_OPTIONS_MAP:
            self._command = TMCC1AuxCommandEnum.by_name(f"AUX1_{AUX_OPTIONS_MAP[self._args.aux1]}")
        elif self._args.aux2 and self._args.aux2 in AUX_OPTIONS_MAP:
            self._command = TMCC1AuxCommandEnum.by_name(f"AUX2_{AUX_OPTIONS_MAP[self._args.aux2]}")
        try:
            if self._command is None or not isinstance(self._command, TMCC1AuxCommandEnum):
                raise ValueError("Must specify an option, use -h for help")
            cmd = AccCmd(
                self._acc, self._command, self._data, baudrate=self._baudrate, port=self._port, server=self._server
            )
            if self.do_fire:
                cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
