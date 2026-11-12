"""Standalone Qt cab launcher using the existing PyTrain runtime lifecycle."""

from __future__ import annotations

import sys
from argparse import ArgumentParser

from pytrain.cli import CliBase
from pytrain.protocol.command_base import CommandBase
from pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, CommandScope
from pytrain.utils.argument_parser import PyTrainArgumentParser

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
            debug=getattr(cli.args, "debug", False),
            echo=getattr(cli.args, "echo", False),
            gui_admin_close=self._close_for_admin_action,
            gui_owns_admin_lifecycle=True,
        )
        self._command = self._build_command()

    def _close_for_admin_action(self) -> None:
        from PySide6.QtCore import QCoreApplication, QMetaObject, Qt

        self._sc.set()
        app = QCoreApplication.instance()
        if app is not None:
            QMetaObject.invokeMethod(app, "quit", Qt.ConnectionType.QueuedConnection)

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
        try:
            self.wait_for_sync()
            if self.pytrain is not None and self.pytrain.admin_exit_requested:
                return 0
            return run_cab(self._cli.scope, self._cli.tmcc_id, [])
        finally:
            if self.pytrain is not None:
                watcher = getattr(self, "_sync_watcher", None)
                if watcher is not None:
                    watcher.shutdown()
                self.pytrain.shutdown()
                if self.pytrain.admin_exit_requested:
                    self.pytrain.perform_gui_admin_action()

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
            help="Initial engine or train TMCC ID (default: 1); target can be changed in the UI",
        )
        parser.add_argument(
            "-train",
            action="store_true",
            help="Start on a train instead of an engine",
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
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        sys.exit(f"{__file__}: error: {exc}\n")
