#!/usr/bin/env python3
#
from typing import List

from src.cli.cli_base import CliBase
from src.protocol.tmcc1.switch_cmd import SwitchCmd
from src.protocol.tmcc1.tmcc1_constants import TMCC1SwitchState
from src.utils.argument_parser import ArgumentParser


class SwitchCli(CliBase):
    @classmethod
    def command_parser(cls) -> ArgumentParser:
        sw_parser = ArgumentParser(add_help=False)
        sw_parser.add_argument("switch", metavar='Switch Number', type=int, help="switch to fire")
        group = sw_parser.add_mutually_exclusive_group()
        group.add_argument("-t", "--through",
                           action="store_const",
                           const=TMCC1SwitchState.THROUGH,
                           dest="command",
                           help="Throw Through")
        group.add_argument("-o", "--out",
                           action="store_const",
                           const=TMCC1SwitchState.OUT,
                           dest="command",
                           help="Throw Out")
        group.add_argument("-a", "--set_address",
                           action="store_const",
                           const=TMCC1SwitchState.SET_ADDRESS,
                           dest="command",
                           help="Set switch address")
        group.set_defaults(command=TMCC1SwitchState.THROUGH)
        return ArgumentParser("Fire specified switch (1 - 99)", parents=[sw_parser, cls.cli_parser()])

    """
        Throw the specified switch.

        Currently only available via the TMCC1 command format
    """

    def __init__(self,
                 arg_parser: ArgumentParser,
                 cmd_line: List[str] = None,
                 do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._switch = self._args.switch
        self._switch_state = self._args.command
        try:
            cmd = SwitchCmd(self._switch,
                            self._switch_state,
                            baudrate=self._baudrate,
                            port=self._port,
                            server=self._server)
            if self.do_fire:
                cmd.fire()
            self._command = cmd
        except ValueError as ve:
            print(ve)


if __name__ == '__main__':
    SwitchCli(SwitchCli.command_parser())
