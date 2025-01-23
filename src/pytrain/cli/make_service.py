#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import getpass
import os
import pwd
import sys
from argparse import ArgumentParser
from pathlib import Path

from src.pytrain import PROGRAM_NAME, is_package, get_version


class MakeService:
    def __init__(self, cmd_line: list[str] = None) -> None:
        self._user = getpass.getuser()
        self._home = Path.home()
        self._cwd = Path.cwd()
        self._prog = "make_service" if is_package() else "make_service.py"
        if cmd_line:
            args = self.command_line_parser().parse_args(cmd_line)
        else:
            args = self.command_line_parser().parse_args()
        self._args = args
        # verify username
        usr = self._user = args.user
        if self._user is None:
            raise AttributeError("A valid Raspberry Pi username is required")
        elif self.validate_username(self._user) is False:
            raise AttributeError(f"User '{usr}' does not exist on this system")
        self.confirm()

    @property
    def template_dir(self) -> str | None:
        for d in [".", "../", "src"]:
            if os.path.isdir(d):
                for root, dirs, _ in os.walk(d):
                    if root.startswith("./.") or root.startswith("./venv/"):
                        continue
                    for cd in dirs:
                        if cd.startswith(".") or cd in ["__pycache__"]:
                            continue
                        if cd == "installation":
                            return f"{root}/{cd}"
        return None

    @staticmethod
    def confirm(msg: str = None) -> bool:
        msg = msg if msg else "Continue? [y/n]"
        answer = input(msg)
        return True if answer.lower() in ["y", "yes"] else False

    def command_line_parser(self) -> ArgumentParser:
        parser = ArgumentParser(
            prog=self._prog,
            description=f"Launch {PROGRAM_NAME} as a systemd service when your Raspberry Pi is powered on",
        )
        mode_group = parser.add_mutually_exclusive_group(required=True)
        mode_group.add_argument(
            "-client",
            action="store_const",
            dest="mode",
            help=f"Configure this node as a {PROGRAM_NAME} client",
        )
        mode_group.add_argument(
            "-server",
            action="store_const",
            dest="mode",
            help=f"Configure this node as a {PROGRAM_NAME} server",
        )
        server_opts = parser.add_argument_group("Server options")
        server_opts.add_argument(
            "-base",
            nargs="*",
            type=str,
            help="IP address of Lionel Base 3 or LCS Wi-Fi module",
        )
        server_opts.add_argument(
            "-ser2",
            action="store_true",
            help="Send or receive TMCC commands from an LCS Ser2",
        )
        misc_opts = parser.add_argument_group("Miscellaneous options")
        misc_opts.add_argument(
            "-button_file",
            nargs="*",
            type=str,
            help=f"Button definitions file, loaded when {PROGRAM_NAME} starts",
        )
        misc_opts.add_argument(
            "-user",
            action="store",
            default=self._user,
            help=f"Raspberry Pi user to run {PROGRAM_NAME} as (default: {self._user})",
        )
        misc_opts.add_argument(
            "-version",
            action="version",
            version=f"{self.__class__.__name__} {get_version()}",
            help="Show version and exit",
        )
        return parser

    @staticmethod
    def validate_username(user: str) -> bool:
        try:
            pwd.getpwnam(user)
            return True
        except KeyError:
            return False


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        MakeService(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{__file__}: error: {e}\n")
