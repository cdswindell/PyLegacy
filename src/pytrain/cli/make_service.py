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
import shutil
import subprocess
import sys
import tempfile
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict

from .pytrain import DEFAULT_BUTTONS_FILE
from .. import is_linux
from ..utils.path_utils import find_dir, find_file


class MakeService:
    def __init__(self, cmd_line: list[str] = None) -> None:
        from .. import is_package

        self._user = getpass.getuser()
        self._home = Path.home()
        self._cwd = Path.cwd()
        self._prog = "make_service" if is_package() else "make_service.py"
        if cmd_line:
            args = self.command_line_parser().parse_args(cmd_line)
        else:
            args = self.command_line_parser().parse_args()
        self._args = args

        self._template_dir = find_dir("installation", (".", "../", "src"))
        if self._template_dir is None:
            print("\nUnable to locate directory with installation templates. Exiting")
            return

        self._activate_cmd = find_file("activate", (".", "../"))
        if self._activate_cmd is None:
            print("\nUnable to locate virtual environment 'activate' command. Exiting")
            return

        # verify username
        self._user = args.user
        if self._user is None:
            print("\nA valid Raspberry Pi username is required")
            return
        elif self.validate_username(self._user) is False:
            print(f"\nUser '{self._user}' does not exist on this system. Exiting.")
            return

        # if server, verify a base 3 and/or ser2 is specified
        self._ser2 = args.ser2 is True
        if args.base is None:
            self._base_ip = None
        else:
            self._base_ip = args.base if args.base and args.base != "search" else "search"
            if self._base_ip != "search":
                if self.is_valid_ip(self._base_ip) is False:
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
            if args.ser2 is True:
                print("\nA Ser2 is not required when configuring as a client. Continuing")

        # verify buttons file exists
        if args.buttons_file:
            if os.path.isfile(args.buttons_file) is False:
                print(f"\nButton definitions file '{args.buttons_file}' not found. Continuing")

        self._exe = "pytrain" if is_package() else "cli/pytrain.py"
        self._echo = args.echo is True
        self._cmd_line = self.command_line
        self._config = {
            "___ACTIVATE___": str(self._activate_cmd),
            "___BUTTONS___": self._args.buttons_file if self._args.buttons_file else "",
            "___CLIENT___": "-client" if self.is_client else "",
            "___ECHO___": " -echo" if self._echo is True else "",
            "___HOME___": str(self._home),
            "___LCSSER2___": " -ser2" if self._ser2 is True else "",
            "___LIONELBASE___": f"-base {self._base_ip}" if self._base_ip is not None else "",
            "___MODE___": "Server" if self.is_server else "Client",
            "___PYTRAINHOME___": str(self._cwd),
            "___PYTRAIN___": str(self._exe),
            "___USER___": self._user,
        }
        self._start_service = args.start is True
        if self.confirm_environment():
            path = self.make_shell_script()
            if path:
                self._config["___SHELL_SCRIPT___"] = str(path)
                self.install_service()
        else:
            print("\nRe-run this script with the -h option for help")

    def make_shell_script(self) -> Path | None:
        template = find_file("pytrain.bash.template", (".", "../", "src"))
        if template is None:
            print("\nUnable to locate shell script template. Exiting")
            return None
        with open(template, "r") as f:
            template_data = f.read()
        for key, value in self.config.items():
            template_data = template_data.replace(key, value)
        path = Path(self._home, "pytrain_server.bash" if self.is_server else "pytrain_client.bash")
        # write the shell script file
        if path.exists():
            shutil.copy2(path, path.with_suffix(".bak"))
        with open(path, "w") as f:
            f.write(template_data)
        os.chmod(path, 0o755)
        print(f"\n{path} created")
        return path

    def install_service(self) -> str | None:
        from .. import PROGRAM_NAME

        if is_linux() is False:
            print(f"\nPlease run {self._prog} from a Raspberry Pi. Exiting")
            return None
        template = find_file("pytrain.service.template", (".", "../", "src"))
        if template is None:
            print("\nUnable to locate service definition template. Exiting")
            return None
        with open(template, "r") as f:
            template_data = f.read()
        for key, value in self.config.items():
            template_data = template_data.replace(key, value)
        tmp = tempfile.NamedTemporaryFile()
        with open(tmp.name, "w") as f:
            f.write(template_data)
        service = "pytrain_server.service" if self.is_server else "pytrain_client.service"
        result = subprocess.run(
            f"sudo cp -f {tmp.name} /etc/systemd/system/{service}".split(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error creating /etc/systemd/system/{service}: {result.stderr} Exiting")
            return None
        result = subprocess.run(
            f"sudo chmod 644 /etc/systemd/system/{service}".split(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error changing mode of /etc/systemd/system/{service}: {result.stderr} Exiting")
            return None
        result = subprocess.run(
            "sudo systemctl daemon-reload".split(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error reloading system daemons: {result.stderr} Exiting")
            return None
        result = subprocess.run(
            f"sudo systemctl enable {service}".split(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error enabling {PROGRAM_NAME} service: {result.stderr} Exiting")
            return None
        if self._start_service:
            subprocess.run(
                f"sudo systemctl restart {service}".split(),
            )
            print(f"\n{PROGRAM_NAME} service started...")
        return service

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
        if self._args.buttons_file:
            cmd_line += f" -buttons {self._args.buttons_file}"
        return cmd_line

    def confirm_environment(self) -> bool:
        from .. import PROGRAM_NAME

        print(f"\nInstalling {PROGRAM_NAME} as a systemd service with these settings:")
        print(f"  Mode: {'Client' if self._args.mode == 'client' else 'Server'}")
        if self._args.mode == "server":
            print(f"  Lionel Base IP addresses: {self._base_ip}")
            print(f"  Use Ser2: {'Yes' if self._args.ser2 is True else 'No'}")
        print(f"  Button definitions file: {self._args.buttons_file if self._args.buttons_file else 'None'}")
        print(f"  Run as user: {self._user}")
        print(f"  User '{self._user} Home: {self._home}")
        print(f"  Echo TMCC/Legacy/Pdi commands to log file: {'Yes' if self._echo is True else 'No'}")
        print(f"  System type: {platform.system()}")
        print(f"  Virtual environment activation command: {self._activate_cmd}")
        print(f"  {PROGRAM_NAME} Exe: {self._exe}")
        print(f"  {PROGRAM_NAME} Home: {self._cwd}")
        print(f"  {PROGRAM_NAME} Command Line: {self._cmd_line}")
        return self.confirm("\nConfirm? [y/n] ")

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

    def command_line_parser(self) -> ArgumentParser:
        from .. import PROGRAM_NAME, get_version

        parser = ArgumentParser(
            prog=self._prog,
            description=f"Launch {PROGRAM_NAME} as a systemd service when your Raspberry Pi is powered on",
        )
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
        misc_opts = parser.add_argument_group("Miscellaneous options")
        misc_opts.add_argument(
            "-buttons_file",
            nargs="?",
            default=None,
            const=DEFAULT_BUTTONS_FILE,
            help=f"Button definitions file, loaded when {PROGRAM_NAME} starts",
        )
        misc_opts.add_argument(
            "-echo",
            action="store_true",
            help="Echo received TMCC/Legacy/Pdi commands to log file",
        )
        misc_opts.add_argument(
            "-start",
            action="store_true",
            help=f"Start {PROGRAM_NAME} Client/Server now (otherwise, it starts on reboot)",
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
