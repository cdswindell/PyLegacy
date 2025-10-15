#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import os
import shutil
import sys
from argparse import ArgumentParser
from pathlib import Path

from .make_base import _MakeBase
from .pytrain import DEFAULT_BUTTONS_FILE
from ..utils.argument_parser import PyTrainArgumentParser
from ..utils.path_utils import find_file


class MakeGui(_MakeBase):
    def __init__(self, cmd_line: list[str] = None) -> None:
        self._start_gui = False
        self._launch_path = self._desktop_path = None
        super().__init__(cmd_line)

    def program(self) -> str:
        return "make_gui"

    def function(self) -> str:
        return "GUI"

    def postprocess_args(self) -> None:
        if self._args.start is True:
            self._start_gui = True
        self._buttons_file = DEFAULT_BUTTONS_FILE
        self._launch_path = Path(self._home, "launch_pytrain.bash")
        self._desktop_path = Path(self._home, ".config", "autostart", "pytrain.desktop")

    def config_header(self) -> list[str]:
        from .. import PROGRAM_NAME

        lines = list()
        lines.append(f"\nInstalling the {PROGRAM_NAME} GUI with these settings:")
        lines.append(f"  Start GUI now: {'Yes' if self._start_gui is True else 'No'}")
        return lines

    def install(self) -> None:
        from .. import PROGRAM_NAME

        path = self.make_shell_script()
        if path:
            self._config["___SHELL_SCRIPT___"] = str(path)
            desktop = self.make_python_desktop_file()
            if desktop:
                self._config["___DESKTOP___"] = str(desktop)
                if self._start_gui:
                    self.spawn_detached(path)
                    print(f"\n{PROGRAM_NAME} GUI started...")

    def remove(self) -> None:
        from .. import PROGRAM_NAME

        if not self.is_gui_present:
            print(f"\nNo {PROGRAM_NAME} GUI detected. Exiting")
            return
        if self.confirm(f"Are you sure you want to remove the {PROGRAM_NAME} GUI?"):
            for path in (self._desktop_path, self._launch_path):
                if path.exists():
                    print(f"\nRemoving {path}...")
                    path.unlink(missing_ok=True)

    def command_line_parser(self) -> ArgumentParser:
        from .. import PROGRAM_NAME

        parser = ArgumentParser(add_help=False)
        misc_opts = parser.add_argument_group("Service options")
        misc_opts.add_argument(
            "-start",
            action="store_true",
            help=f"Start {PROGRAM_NAME} GUI now (otherwise, it starts on reboot)",
        )
        return PyTrainArgumentParser(
            prog=self._prog,
            description=f"Launch {PROGRAM_NAME} GUI when your Raspberry Pi is powered on",
            parents=[self._command_line_parser(), parser],
        )

    def make_shell_script(self) -> Path | None:
        template = find_file("launch_pytrain.bash.template", (".", "../", "src"))
        if template is None:
            print("\nUnable to locate shell script template. Exiting")
            return None
        template_data = ""
        with open(template, "r") as f:
            template_data = f.read()
        for key, value in self.config.items():
            template_data = template_data.replace(key, value)
        path = self._launch_path
        # write the shell script file
        if path.exists():
            shutil.copy2(path, path.with_suffix(".bak"))
        with open(path, "w") as f:
            f.write(template_data)
        os.chmod(path, 0o755)
        print(f"\n{path} created")
        return path

    def make_python_desktop_file(self) -> Path | None:
        template = find_file("pytrain_desktop.template", (".", "../", "src"))
        if template is None:
            print("\nUnable to locate desktop template. Exiting")
            return None
        template_data = ""
        with open(template, "r") as f:
            template_data = f.read()
        for key, value in self.config.items():
            template_data = template_data.replace(key, value)
        # make sure directory exists
        path = self._desktop_path
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(path.parent, 0o755)
        # write the shell script file
        if path.exists():
            shutil.copy2(path, path.with_suffix(".bak"))
        with open(path, "w") as f:
            f.write(template_data)

        print(f"\n{path} created")
        return path

    @property
    def is_gui_present(self) -> bool:
        launch_path = Path(self._home, "launch_pytrain.bash")
        desktop_path = Path(self._home, ".config", "autostart", "pytrain.desktop")
        return launch_path.exists() and desktop_path.exists()


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        MakeGui(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{__file__}: error: {e}\n")
