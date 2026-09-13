"""Standalone Qt cab launcher using the existing PyTrain runtime lifecycle."""

from __future__ import annotations

import sys
from argparse import ArgumentParser

from pytrain.cli import CliBase
from pytrain.protocol.command_base import CommandBase
from pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope
from pytrain.utils.argument_parser import PyTrainArgumentParser

from pytrain_ui.adapters import PyTrainCabCommandAdapter, PyTrainCabStateAdapter

from .app import run_cab


class QtCabCommand(CommandBase):
    def __init__(self, cli: "QtCabCli") -> None:
        self._cli = cli
        CommandBase.__init__(
            self,
            None,
            None,
            1,
            scope=cli.scope,
            server=cli.args.server if "server" in cli.args else None,
            client=cli.args.client if "client" in cli.args else False,
            base=cli.args.base if "base" in cli.args else None,
            cache_sync=True,
        )
        self._command = self._build_command()

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
        self.wait_for_sync()
        state_port = PyTrainCabStateAdapter(self._cli.scope, self._cli.tmcc_id)
        command_port = PyTrainCabCommandAdapter(state_port)
        try:
            return run_cab(state_port, command_port, [])
        finally:
            state_port.shutdown()
            if self.pytrain is not None:
                self.pytrain.shutdown()

    def _build_command(self) -> bytes | None:
        return None

    def _command_prefix(self) -> bytes | None:
        return None

    def _encode_address(self, command_op: int) -> bytes | None:
        return None


class QtCabCli(CliBase):
    @classmethod
    def command_parser(cls) -> ArgumentParser:
        parser = PyTrainArgumentParser(add_help=False)
        parser.add_argument(
            "tmcc_id",
            nargs="?",
            type=int,
            default=1,
            help="Engine or train TMCC ID (default: 1)",
        )
        parser.add_argument(
            "-train",
            action="store_true",
            help="Control a train instead of an engine",
        )
        return PyTrainArgumentParser("Qt cab options", parents=[parser, cls.cli_parser()])

    def __init__(self, arg_parser: ArgumentParser = None, cmd_line: list[str] = None, do_fire: bool = True) -> None:
        super().__init__(arg_parser, cmd_line, do_fire)
        self._scope = CommandScope.TRAIN if self._args.train else CommandScope.ENGINE
        self._tmcc_id = self._args.tmcc_id
        cmd = QtCabCommand(self)
        if self.do_fire:
            cmd.fire(baudrate=self._baudrate, port=self._port, server=self._server)
        self._command = cmd

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        QtCabCli(cmd_line=args)
        return 0
    except Exception as exc:
        sys.exit(f"{__file__}: error: {exc}\n")
