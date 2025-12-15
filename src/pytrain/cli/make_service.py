#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from argparse import ArgumentParser
from pathlib import Path

from .make_base import _MakeBase
from .pytrain import DEFAULT_BUTTONS_FILE
from ..utils.argument_parser import PyTrainArgumentParser
from ..utils.path_utils import find_file


class MakeService(_MakeBase):
    def __init__(self, cmd_line: list[str] = None) -> None:
        self._start_service = False
        super().__init__(cmd_line)

    def program(self) -> str:
        return "make_service"

    def function(self) -> str:
        return "service"

    def postprocess_args(self) -> None:
        if self._args.start is True:
            self._start_service = True
        self._buttons_file = self._args.buttons_file

    def config_header(self) -> list[str]:
        from .. import PROGRAM_NAME

        lines = list()
        lines.append(f"\nInstalling {PROGRAM_NAME} as a systemd service with these settings:")
        lines.append(f"  Start service now: {'Yes' if self._start_service is True else 'No'}")
        return lines

    def install(self) -> None:
        path = self.make_shell_script()
        if path:
            self._config["___SHELL_SCRIPT___"] = str(path)
            self.install_service()

    def remove(self) -> None:
        from .. import PROGRAM_NAME

        if self.is_server_present:
            mode = "Server"
        elif self.is_client_present:
            mode = "Client"
        else:
            print(f"\nNo {PROGRAM_NAME} server or client is currently running. Exiting")
            return
        if not self._do_confirm or self.confirm(
            f"Are you sure you want to deactivate and remove {PROGRAM_NAME} {mode}?"
        ):
            path = Path(self._home, "pytrain_server.bash" if mode == "Server" else "pytrain_client.bash")
            if path.exists():
                print(f"\nRemoving {path}...")
                path.unlink(missing_ok=True)
            print(f"\nDeactivating {PROGRAM_NAME} {mode} service...")
            self.deactivate_service("pytrain_server" if mode == "Server" else "pytrain_client")

    def command_line_parser(self) -> ArgumentParser:
        from .. import PROGRAM_NAME

        parser = ArgumentParser(add_help=False)
        misc_opts = parser.add_argument_group("Service options")
        misc_opts.add_argument(
            "-buttons_file",
            nargs="?",
            default=None,
            const=DEFAULT_BUTTONS_FILE,
            help=f"Button definitions file, loaded when {PROGRAM_NAME} service starts",
        )
        misc_opts.add_argument(
            "-start",
            action="store_true",
            help=f"Start {PROGRAM_NAME} Client/Server now (otherwise, it starts on reboot)",
        )
        return PyTrainArgumentParser(
            prog=self._prog,
            description=f"Launch {PROGRAM_NAME} as a systemd service when your Raspberry Pi is powered on",
            parents=[self._command_line_parser(), parser],
        )

    def make_shell_script(self) -> Path | None:
        template = find_file("pytrain.bash.template", (".", "../", "src"))
        if template is None:
            print("\nUnable to locate shell script template. Exiting")
            return None
        template_data = ""
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

        if platform.system().lower() != "linux":
            print(f"\nPlease run {self._prog} from a Raspberry Pi. Exiting")
            return None
        template = find_file("pytrain.service.template", (".", "../", "src"))
        if template is None:
            print("\nUnable to locate service definition template. Exiting")
            return None
        template_data = ""
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
    def is_server_present(self) -> bool:
        return self.is_service_present("pytrain_server")

    @property
    def is_client_present(self) -> bool:
        return self.is_service_present("pytrain_client")


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        MakeService(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{__file__}: error: {e}\n")
