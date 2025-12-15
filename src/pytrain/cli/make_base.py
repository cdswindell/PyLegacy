#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import getpass
import ipaddress
import os
import platform
import pwd
import subprocess
import sys
from abc import ABC, ABCMeta, abstractmethod
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict

import psutil

from .. import find_dir, find_file
from ..utils.argument_parser import PyTrainArgumentParser


class _MakeBase(ABC):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, cmd_line: list[str] = None) -> None:
        from .. import is_package

        self._user = cur_user = getpass.getuser()
        self._home = Path.home()
        self._cwd = Path.cwd()
        self._buttons_file = None
        self._prog = f"{self.program()}" if is_package() else f"{self.program()}.py"
        self._parser = parser = self.command_line_parser()
        self._misc_options = None
        if cmd_line:
            args = parser.parse_args(cmd_line)
        else:
            args = parser.parse_args()
        self._args = args
        self._do_confirm = True if bool(args.yes) is False else False

        # handle subclass arguments
        self.postprocess_args()

        # verify username
        self._user = args.user
        if self._user is None:
            print("\nA valid Raspberry Pi username is required")
            return
        elif not self.validate_username(self._user):
            print(f"\nUser '{self._user}' does not exist on this system. Exiting.")
            return
        elif self._user != cur_user:
            self._home = Path(os.path.expanduser(f"~{self._user}"))

        # only allow running on a Raspberry Pi
        if platform.system().lower() != "linux":
            print(f"\nPlease run {self._prog} from a Raspberry Pi. Exiting")
            return

        # process remove request, if specified
        if args.remove is True:
            self.remove()
            return

        # verify the template directory exists
        self._template_dir = find_dir("installation", (".", "../", "src"))
        if self._template_dir is None:
            print("\nUnable to locate directory with installation templates. Exiting")
            return

        # verify we can activate the virtual environment
        self._activate_cmd = find_file("activate", (".", "../"))
        if self._activate_cmd is None:
            print("\nUnable to locate virtual environment 'activate' command. Exiting")
            return

        # if server, verify base 3 and/or ser2 is specified
        self._ser2 = args.ser2 is True
        if args.base is None:
            self._base_ip = None
        else:
            self._base_ip = args.base if args.base and args.base != "search" else "search"
            if self._base_ip != "search":
                if not self.is_valid_ip(self._base_ip):
                    print(f"\nInvalid IP address '{self._base_ip}'. Exiting")
                    return
            else:
                self._base_ip = ""  # an empty value causes PyTrain to search for the base
        if args.mode == "server" and args.base is None and args.ser2 is False:
            print("\nA Lionel Base IP address or Ser2 is required when configuring as a server. Exiting")
            return

        # verify client args
        if args.mode == "client":
            if self._base_ip is not None:
                print("\nA Lionel Base IP address is not required when configuring as a client. Continuing")
                self._base_ip = None
            if args.ser2:
                print("\nA Ser2 is not required when configuring as a client. Continuing")
                self._ser2 = args.ser2 = False

        # verify buttons file exists
        if self._buttons_file:
            if not os.path.isfile(self._buttons_file):
                print(f"\nButton definitions file '{self._buttons_file}' not found. Continuing")

        self._exe = "pytrain" if is_package() else "cli/pytrain.py"
        self._echo = args.echo is True
        self._cmd_line = self.command_line
        self._config = {
            "___ACTIVATE___": str(self._activate_cmd),
            "___BUTTONS___": self._buttons_file if self._buttons_file else "",
            "___CLIENT___": " -client" if self.is_client else "",
            "___ECHO___": " -echo" if self._echo is True else "",
            "___HOME___": str(self._home),
            "___LCSSER2___": " -ser2" if self._ser2 is True else "",
            "___LIONELBASE___": f" -base {self._base_ip}" if self._base_ip is not None else "",
            "___MODE___": "Server" if self.is_server else "Client",
            "___PYTRAINHOME___": str(self._cwd),
            "___PYTRAIN___": str(self._exe),
            "___USERHOME___": str(self._home),
            "___USER___": self._user,
        }

        # handle subclass config
        self.postprocess_config()

        if self.confirm_environment():
            self.install()
        else:
            print("\nRe-run this script with the -h option for help")

    @property
    def is_client(self) -> bool:
        return self._args.mode == "client"

    @property
    def is_server(self) -> bool:
        return self._args.mode == "server"

    @property
    def config(self) -> Dict[str, str]:
        return self._config

    @property
    def pytrain_path(self) -> str:
        return f"{self._cwd}/{self._exe}"

    @property
    def command_line(self) -> str | None:
        cmd_line = f"{self._exe} -headless"
        if self._args.mode == "client":
            cmd_line += " -client"
        else:
            if self._base_ip:
                ip = self._base_ip
                ip = f" {ip}" if ip != "search" else ""
                cmd_line += f" -base{ip}"
            if self._args.ser2 is True:
                cmd_line += " -ser2"
        if self._echo is True:
            cmd_line += " -echo"
        if self._buttons_file:
            cmd_line += f" -buttons {self._buttons_file}"
        return cmd_line

    def confirm_environment(self) -> bool:
        from .. import PROGRAM_NAME

        for line in self.config_header():
            print(line)
        print(f"  Mode: {'Client' if self._args.mode == 'client' else 'Server'}")
        if self._args.mode == "server":
            print(f"  Lionel Base IP addresses: {self._base_ip}")
            print(f"  Use Ser2: {'Yes' if self._args.ser2 is True else 'No'}")
        print(f"  Button definitions file: {self._buttons_file if self._buttons_file else 'None'}")
        print(f"  Run as user: {self._user}")
        print(f"  User '{self._user} Home: {self._home}")
        print(f"  Echo TMCC/Legacy/Pdi commands to log file: {'Yes' if self._echo is True else 'No'}")
        print(f"  System type: {platform.system()}")
        print(f"  Virtual environment activation command: {self._activate_cmd}")
        print(f"  {PROGRAM_NAME} Exe: {self._exe}")
        print(f"  {PROGRAM_NAME} Home: {self._cwd}")
        print(f"  {PROGRAM_NAME} Command Line: {self._cmd_line}")

        return self.confirm("\nConfirm? [y/n] ") if self._do_confirm else True

    @staticmethod
    def find_and_kill_process(process_name: str = None, cmdline: str | set[str] = None) -> None:
        """Finds and kills all processes with the given name."""
        process = None
        if cmdline and isinstance(cmdline, str):
            cmdline = set(cmdline.split())
        for p in psutil.process_iter():
            try:
                if process_name and p.name() == process_name:
                    process = p
                elif cmdline and cmdline.intersection(set(p.cmdline())):
                    process = p

                if process:
                    print(f"Attempting to kill process {p.pid} ({' '.join(p.cmdline())})...")
                    p.kill()
                    print(f"Process {p.pid} killed.")
                    return
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                print(f"Could not access or kill process with name '{process_name}'.")

    @staticmethod
    def spawn_detached(path: str | Path, *args: str) -> None:
        path = str(path) if isinstance(path, Path) else path
        # Ensure executable; if it’s a script without exec bit, call its interpreter
        cmd = [path, *args]
        if path.endswith(".py"):
            cmd = [sys.executable, path, *args]
        elif path.endswith(".sh") or path.endswith(".bash"):
            cmd = ["/bin/bash", path, *args]

        # Detach: new session, no stdio, independent cwd and env if desired
        with (
            open(os.devnull, "rb") as devnull_in,
            open(os.devnull, "wb") as devnull_out,
            open(os.devnull, "wb") as devnull_err,
        ):
            subprocess.Popen(
                cmd,
                stdin=devnull_in,
                stdout=devnull_out,
                stderr=devnull_err,
                close_fds=True,
                start_new_session=True,  # posix: setsid()
                cwd="/",  # optional: avoid holding current directory
                env=os.environ.copy(),  # optional: prune/adjust as needed
            )

    @staticmethod
    def confirm(msg: str = None) -> bool:
        msg = msg if msg else "Continue? [y/n] "
        answer = input(msg)
        return True if answer.lower() in ["y", "yes"] else False

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_service_present(service: str) -> bool:
        cmd = f"sudo systemctl status {service}.service"
        result = subprocess.run(cmd.split(), capture_output=True)
        if result.returncode == 4 or os.path.exists(f"/etc/systemd/system/{service}.service") is False:
            return False
        else:
            return True

    @staticmethod
    def deactivate_service(service: str) -> None:
        subprocess.run(f"sudo systemctl stop {service}.service".split())
        subprocess.run(f"sudo systemctl disable {service}.service".split())
        subprocess.run(f"sudo rm -fr /etc/systemd/system/{service}.service".split())
        subprocess.run("sudo systemctl daemon-reload".split())
        subprocess.run("sudo systemctl reset-failed".split())

    def _command_line_parser(self) -> PyTrainArgumentParser:
        from .. import PROGRAM_NAME, get_version

        parser = PyTrainArgumentParser(add_help=False)
        mode_group = parser.add_mutually_exclusive_group(required=True)
        mode_group.add_argument(
            "-client",
            action="store_const",
            const="client",
            dest="mode",
            help=f"Configure this node as a {PROGRAM_NAME} client",
        )
        mode_group.add_argument(
            "-server",
            action="store_const",
            const="server",
            dest="mode",
            help=f"Configure this node as a {PROGRAM_NAME} server",
        )
        mode_group.add_argument(
            "-remove",
            action="store_true",
            help=f"Deactivate and remove any existing {PROGRAM_NAME} {self.function()}",
        )
        server_opts = parser.add_argument_group("Server options")
        server_opts.add_argument(
            "-base",
            nargs="?",
            default=None,
            const="search",
            help="IP address of Lionel Base 3 or LCS Wi-Fi module",
        )
        server_opts.add_argument(
            "-ser2",
            action="store_true",
            help="Send or receive TMCC commands from an LCS Ser2",
        )
        self._misc_options = misc_opts = parser.add_argument_group("Miscellaneous options")
        misc_opts.add_argument(
            "-echo",
            action="store_true",
            help="Echo received TMCC/Legacy/Pdi commands to log file",
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
        misc_opts.add_argument(
            "-yes",
            action="store_true",
            help="Skip confirmation prompt and proceed with installation/removal",
        )
        return parser

    @staticmethod
    def validate_username(user: str) -> bool:
        try:
            pwd.getpwnam(user)
            return True
        except KeyError:
            return False

    def postprocess_args(self) -> None: ...

    def postprocess_config(self) -> None: ...

    @abstractmethod
    def program(self) -> str: ...

    @abstractmethod
    def function(self) -> str: ...

    @abstractmethod
    def config_header(self) -> list[str]: ...

    @abstractmethod
    def install(self) -> str: ...

    @abstractmethod
    def remove(self) -> str: ...

    @abstractmethod
    def command_line_parser(self) -> ArgumentParser: ...
