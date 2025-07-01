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
from typing import List, Sequence

from ..pdi.amc2_req import Amc2Req
from ..pdi.constants import Amc2Action, PdiCommand
from ..protocol.command_base import CommandBase
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.argument_parser import IntRange, PyTrainArgumentParser
from . import CliBase

log = logging.getLogger(__name__)


class Amc2Cmd(CommandBase):
    def __init__(self, tmcc_id: int, req: Amc2Req | CommandReq, server: str = None) -> None:
        if tmcc_id < 1 or tmcc_id > 99:
            raise ValueError("Amc2 ID must be between 1 and 99")
        super().__init__(None, req, tmcc_id, CommandScope.AMC2, server=server)
        self._command = self._build_command()

    def _build_command(self) -> bytes | None:
        if isinstance(self.command_req, CommandReq) or isinstance(self.command_req, Amc2Req):
            reqs = [self.command_req]
        elif isinstance(self.command_req, Sequence):
            reqs = self.command_req
        else:
            raise ValueError(f"Invalid command request: {type(self.command_req)}")
        byte_str = bytes()
        for req in reqs:
            byte_str += req.as_bytes
        return byte_str

    def _command_prefix(self) -> bytes | None:
        pass

    def _encode_address(self, command_op: int) -> bytes | None:
        pass


class Amc2Cli(CliBase):
    """
    Issue Amc2 Commands.
    """

    @classmethod
    def command_parser(cls) -> ArgumentParser:
        from . import PROGRAM_NAME

        amc2_parser = PyTrainArgumentParser(add_help=False)
        amc2_parser.add_argument("amc2", metavar="Amc2 TMCC ID", type=int, help="Amc2 to operate")

        obj_group = amc2_parser.add_argument_group(
            "Motor or Lamp",
            "Specify the motor or lamp to control",
        )
        obj = obj_group.add_mutually_exclusive_group()
        obj.add_argument(
            "-motor",
            nargs=1,
            type=int,
            choices=[1, 2],
            action="store",
            help="Motor 1 or 2",
        )
        obj.add_argument(
            "-lamp",
            nargs=1,
            type=int,
            choices=[1, 2, 3, 4],
            action="store",
            help="Lamp 1 - 4",
        )

        opts_group = amc2_parser.add_argument_group(
            "Control options",
            "Turn the motor/lamp on or off, or set the speed/brightness level",
        )
        opts = opts_group.add_mutually_exclusive_group()
        opts.add_argument(
            "-off",
            action="store_true",
            help="Turn Amc2 port off",
        )
        opts.add_argument(
            "-on",
            action="store_true",
            help="Turn Amc2 port on",
        )
        opts.add_argument(
            "-level",
            nargs=1,
            type=IntRange(0, 100),
            action="store",
            help="Set level (speed) of Amc2 port (0 - 100)",
        )
        opts.add_argument(
            "-speed",
            nargs=1,
            type=IntRange(0, 100),
            action="store",
            help="Set speed (level) of Amc2 port (0 - 100)",
        )

        amc2_parser.add_argument(
            "-server",
            action="store",
            help=f"IP Address of {PROGRAM_NAME} server, if client. Server communicates with Base 3/LCS SER2",
        )
        # fire command
        return PyTrainArgumentParser(
            "Operate specified Amc2 (1 - 99)",
            parents=[amc2_parser],
        )

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: List[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._amc2 = self._args.amc2
        self._motor = self._args.motor[0] - 1 if self._args.motor else None
        self._lamp = self._args.lamp[0] - 1 if self._args.lamp else None
        self._mag = self._args.level[0] if self._args.level else self._args.speed[0] if self._args.speed else None

        if self._motor is not None:
            if self._args.on or self._args.off:
                req1 = CommandReq(TMCC1AuxCommandEnum.NUMERIC, self._amc2, data=self._motor + 1)
                if self._args.on:
                    req2 = CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, self._amc2)
                else:
                    req2 = CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, self._amc2)
                req = [req1, req2]
            else:
                req = Amc2Req(
                    self._amc2,
                    PdiCommand.AMC2_SET,
                    Amc2Action.MOTOR,
                    motor=self._motor,
                    speed=self._mag,
                )
        elif self._lamp is not None:
            if self._args.on or self._args.off:
                req1 = CommandReq(TMCC1AuxCommandEnum.NUMERIC, self._amc2, data=self._lamp + 3)
                if self._args.on:
                    req2 = CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, self._amc2)
                else:
                    req2 = CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, self._amc2)
                req = [req1, req2]
            else:
                req = Amc2Req(
                    self._amc2,
                    PdiCommand.AMC2_SET,
                    Amc2Action.LAMP,
                    lamp=self._lamp,
                    level=self._mag,
                )
        else:
            raise ValueError("Must specify motor or lamp")
        try:
            cmd = Amc2Cmd(self._amc2, req, server=self._server)
            if self.do_fire:
                cmd.fire(server=self._server)
            self._command = cmd
        except ValueError as ve:
            log.exception(ve)
