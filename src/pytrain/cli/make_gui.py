#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

from .make_base import _MakeBase
from .pytrain import DEFAULT_BUTTONS_FILE
from ..gui.accessories_gui import AccessoriesGui
from ..gui.component_state_gui import ComponentStateGui
from ..gui.engine_gui import EngineGui
from ..gui.launch_gui import LaunchGui
from ..gui.motors_gui import MotorsGui
from ..gui.power_district_gui import PowerDistrictsGui
from ..gui.routes_gui import RoutesGui
from ..gui.switches_gui import SwitchesGui
from ..gui.systems_gui import SystemsGui
from ..protocol.constants import PROGRAM_NAME, CommandScope
from ..utils.argument_parser import PyTrainArgumentParser, UniqueChoice, IntRange
from ..utils.path_utils import find_file, find_dir

GUI_ARG_TO_CLASS = {
    "ac": AccessoriesGui,
    "accessories": AccessoriesGui,
    "co": ComponentStateGui,
    "component_state": ComponentStateGui,
    "cp": EngineGui,
    "control_panel": EngineGui,
    "la": LaunchGui,
    "launch_pad": LaunchGui,
    "mo": MotorsGui,
    "motors": MotorsGui,
    "pad": LaunchGui,
    "pd": PowerDistrictsGui,
    "po": PowerDistrictsGui,
    "power_districts": PowerDistrictsGui,
    "ro": RoutesGui,
    "routes": RoutesGui,
    "state": ComponentStateGui,
    "sw": SwitchesGui,
    "switches": SwitchesGui,
    "sy": SystemsGui,
    "pa": SystemsGui,
    f"{PROGRAM_NAME}_administration".lower(): SystemsGui,
}

CLASS_TO_TEMPLATE = {
    AccessoriesGui: f"{AccessoriesGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__,"
    " exclude_unnamed=__EXCLUDE_UNNAMED__)",
    ComponentStateGui: f"{ComponentStateGui.name()}(label=__LABEL__, initial=__INITIAL__, scale_by=__SCALE_BY__,"
    " exclude_unnamed=__EXCLUDE_UNNAMED__)",
    LaunchGui: f"{LaunchGui.__name__}(tmcc_id=__TMCC_ID__, track_id=__TRACK_ID__)",
    MotorsGui: f"{MotorsGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__)",
    PowerDistrictsGui: f"{PowerDistrictsGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__,"
    " exclude_unnamed=__EXCLUDE_UNNAMED__)",
    RoutesGui: f"{RoutesGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__)",
    SwitchesGui: f"{SwitchesGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__, exclude_unnamed=__EXCLUDE_UNNAMED__)",
    SystemsGui: f"{SystemsGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__, press_for=__PRESS_FOR__)",
    EngineGui: f"{EngineGui.__name__}(initial_scope=__INITIAL_SCOPE__, initial=__TMCC_ID__,"
    " scale_by=__SCALE_BY__, num_recents=__NUM_RECENTS__)",
}

NEED_FONTS = {
    LaunchGui,
}

CHOICES = [
    "accessories",
    "motors",
    "power districts",
    "routes",
    "switches",
    f"{PROGRAM_NAME} Administration".lower(),
]

CHOICES_HELP = ", ".join([x.title() for x in CHOICES]).replace(PROGRAM_NAME.title(), PROGRAM_NAME)

SCOPES = [
    "accessory",
    "engine",
    "route",
    "switch",
    "train",
]


class MakeGui(_MakeBase):
    """
    Handles the creation, configuration, and management of a graphical user interface (GUI) for PyTrain.

    This class facilitates the configuration and installation of various GUI components as specified by command-line
    arguments. It is designed to be extensible to support multiple GUI types, offering flexibility for user interaction
    and program operations. The functionality includes argument preprocessing, GUI setup, installation, and removal,
    as well as command-line parser configuration tailored to specific GUI requirements.
    """

    def __init__(self, cmd_line: list[str] = None) -> None:
        self._start_gui = False
        self._launch_path = self._desktop_path = self._buttons_path = self._fonts_path = None
        self._imports = self._gui_class = self._gui_stmt = None
        self._gui_config = dict()
        self._exclude_unnamed = False
        super().__init__(cmd_line)

    def program(self) -> str:
        return "make_gui"

    def function(self) -> str:
        return "GUI"

    def postprocess_args(self) -> None:
        from .. import PROGRAM_BASE, is_package

        if not self._args.remove and not self._args.gui:
            self._parser.error("the following arguments are required: gui")
        if self._args.start is True:
            self._start_gui = True
        if self._args.exclude_unnamed:
            self._exclude_unnamed = True
        self._buttons_file = DEFAULT_BUTTONS_FILE
        self._launch_path = Path(self._home, "launch_pytrain.bash")
        self._desktop_path = Path(self._home, ".config", "autostart", "pytrain.desktop")
        self._buttons_path = Path(self._cwd, self._buttons_file)
        self._fonts_path = Path(self._home, ".fonts")
        self._imports = f"from {PROGRAM_BASE if is_package() else 'src.' + PROGRAM_BASE} import *"
        self._gui_class = GUI_ARG_TO_CLASS.get(self._args.gui)
        self.harvest_gui_config()

    def postprocess_config(self) -> None:
        self._config["___IMPORTS___"] = self._imports
        self._config["___GUI___"] = self._gui_stmt = self.construct_gui_stmt()

    def config_header(self) -> list[str]:
        lines = list()
        lines.append(f"\nInstalling the {PROGRAM_NAME} {self._gui_class.__name__} GUI with these settings:")
        lines.append(f"  Start GUI now: {'Yes' if self._start_gui is True else 'No'}")
        lines.append(f"  Imports: {self._imports}")
        lines.append(f"  GUI: {self._gui_stmt}")
        return lines

    def install(self) -> None:
        path = self.make_shell_script()
        if path:
            self._config["___SHELL_SCRIPT___"] = str(path)
        else:
            return

        desktop = self.make_python_desktop_file()
        if desktop:
            self._config["___DESKTOP___"] = str(desktop)
        else:
            return

        buttons = self.make_buttons_file()
        if buttons:
            self._config["___BUTTONS___"] = str(buttons)
        else:
            return

        if self._gui_class in NEED_FONTS:
            self.install_fonts()

        if self._start_gui:
            self.spawn_detached(path)
            print(f"\nStarting {PROGRAM_NAME} {self._gui_class.__name__} GUI...")

    def remove(self) -> None:
        if not self.is_gui_present:
            print(f"\nNo {PROGRAM_NAME} GUI detected. Exiting")
            return
        if not self._do_confirm or self.confirm(f"Are you sure you want to remove the {PROGRAM_NAME} GUI?"):
            self.find_and_kill_process(cmdline="python3 headless -buttons")
            for path in (self._desktop_path, self._launch_path, self._buttons_path):
                if path.exists():
                    print(f"\nRemoving {path}...")
                    path.unlink(missing_ok=True)

    # noinspection PyTypeChecker
    def command_line_parser(self) -> ArgumentParser:
        parent = self._command_line_parser()
        parser = ArgumentParser(add_help=False)
        sp = parser.add_subparsers(dest="gui", help="Available GUIs")

        # Launch Pad GUI
        hhcp = sp.add_parser(
            "control_panel",
            aliases=["cp"],
            allow_abbrev=True,
            help="Control Panel GUI",
        )
        hhcp.add_argument(
            "-scale_by",
            type=float,
            default=1.5,
            metavar="",
            help="Text Scale Factor (default: 1.5)",
        )
        hhcp.add_argument(
            "-history",
            type=IntRange(1, 15),
            default=5,
            metavar="",
            help="History Depth (default: 5)",
        )
        hhcp.add_argument(
            "-tmcc_id",
            type=IntRange(1, 9999),
            metavar="",
            help="Initial Engine/Train/Switch/Accessory/Route to display",
        )
        hhcp.add_argument(
            "-scope",
            type=UniqueChoice(SCOPES),
            metavar="",
            default="engine",
            help="Initial Component Type to display (default: engine)",
        )

        # Launch Pad GUI
        pad = sp.add_parser(
            "launch_pad",
            aliases=["la", "pad"],
            allow_abbrev=True,
            help="Launch Pad GUI",
        )
        pad.add_argument(
            "-tmcc_id",
            type=IntRange(1, 98),
            default=39,
            const=39,
            nargs="?",
            help="Launch Pad TMCC ID (default: 39)",
        )
        pad.add_argument(
            "-track_id",
            type=IntRange(1, 98),
            help="Launch Pad Track Power District TMCC ID",
        )

        # Component State GUI
        comp = sp.add_parser(
            "component_state",
            aliases=["co", "state"],
            allow_abbrev=True,
            help="Component State GUI",
        )

        comp.add_argument(
            "-initial",
            type=UniqueChoice(CHOICES),
            nargs="?",
            const="power districts",
            default="power districts",
            help=f"Initial Display (default: Power Districts, choices: {CHOICES_HELP})",
        )
        comp.add_argument(
            "-label",
            type=str,
            help="Layout Name",
        )
        comp.add_argument(
            "-scale_by",
            type=float,
            default=1.0,
            help="Text Scale Factor (default: 1.0)",
        )

        # Accessories GUI
        acc = sp.add_parser(
            "accessories",
            aliases=["ac"],
            allow_abbrev=True,
            help="Accessories GUI",
        )

        acc.add_argument(
            "-label",
            type=str,
            help="Layout Name",
        )
        acc.add_argument(
            "-scale_by",
            type=float,
            default=1.0,
            help="Text Scale Factor (default: 1.0)",
        )

        # Motors GUI
        mo = sp.add_parser(
            "motors",
            aliases=["mo"],
            allow_abbrev=True,
            help="Motors GUI",
        )
        mo.add_argument(
            "-label",
            type=str,
            help="Layout Name",
        )
        mo.add_argument(
            "-scale_by",
            type=float,
            default=1.0,
            help="Text Scale Factor (default: 1.0)",
        )

        # Power Districts GUI
        pd = sp.add_parser(
            "power_districts",
            aliases=["po", "pd"],
            allow_abbrev=True,
            help="Power Districts GUI",
        )
        pd.add_argument(
            "-label",
            type=str,
            help="Layout Name",
        )
        pd.add_argument(
            "-scale_by",
            type=float,
            default=1.0,
            help="Text Scale Factor (default: 1.0)",
        )

        # Routes GUI
        ro = sp.add_parser(
            "routes",
            aliases=["ro"],
            allow_abbrev=True,
            help="Routes GUI",
        )
        ro.add_argument(
            "-label",
            type=str,
            help="Layout Name",
        )
        ro.add_argument(
            "-scale_by",
            type=float,
            default=1.0,
            help="Text Scale Factor (default: 1.0)",
        )

        # Switches GUI
        sw = sp.add_parser(
            "switches",
            aliases=["sw"],
            allow_abbrev=True,
            help="Switches GUI",
        )
        sw.add_argument(
            "-label",
            type=str,
            help="Layout Name",
        )
        sw.add_argument(
            "-scale_by",
            type=float,
            default=1.0,
            help="Text Scale Factor (default: 1.0)",
        )

        # Systems GUI
        sy = sp.add_parser(
            f"{PROGRAM_NAME}_administration".lower(),
            aliases=["pa", "sy"],
            allow_abbrev=True,
            help=f"{PROGRAM_NAME} System Administration GUI",
        )
        sy.add_argument(
            "-label",
            type=str,
            help="Layout Name",
        )
        sy.add_argument(
            "-scale_by",
            type=float,
            default=1.0,
            help="Text Scale Factor (default: 1.0)",
        )
        sy.add_argument(
            "-press_for",
            type=IntRange(1, 10),
            default=5,
            const=5,
            nargs="?",
            help="Time button must be pressed before performing action (default: 5 seconds)",
        )

        # add one more item to parent miscellaneous group
        # make sure parent parser is created first
        self._misc_options.add_argument(
            "-exclude_unnamed",
            action="store_true",
            help="Exclude unnamed components from the GUI display",
        )

        misc_opts = parser.add_argument_group("Service options")
        misc_opts.add_argument(
            "-start",
            action="store_true",
            help=f"Start {PROGRAM_NAME} GUI now (otherwise, it starts on reboot)",
        )
        return PyTrainArgumentParser(
            prog=self._prog,
            description=f"Launch {PROGRAM_NAME} GUI when your Raspberry Pi is powered on",
            parents=[parent, parser],
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
        # write the desktop file
        with open(path, "w") as f:
            f.write(template_data)

        print(f"\n{path} created")
        return path

    def make_buttons_file(self) -> Path | None:
        template = find_file("buttons_gui.py.template", (".", "../", "src"))
        if template is None:
            print("\nUnable to locate buttons template. Exiting")
            return None
        template_data = ""
        with open(template, "r") as f:
            template_data = f.read()
        for key, value in self.config.items():
            template_data = template_data.replace(key, value)
        # make sure directory exists
        path = self._buttons_path
        # write the buttons file
        if path.exists():
            shutil.copy2(path, path.with_suffix(".bak"))
        with open(path, "w") as f:
            f.write(template_data)

        print(f"\n{path} created")
        return path

    def install_fonts(self) -> Path | None:
        template = find_dir("fonts", (".", "../", "src"))
        if template is None:
            print("\nUnable to locate fonts directory. Exiting")
            return None
        path = self._fonts_path
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        # copy the fonts directory
        try:
            shutil.copytree(template, path, dirs_exist_ok=True)
            subprocess.run(["fc-cache", "-f", "-v"])
            print(f"Installed fonts to: {path}")
        except shutil.Error as e:
            print(f"Error copying directory: {e}")
            path = None
        except OSError as e:
            print(f"Error: {e}")
            path = None
        return path

    def harvest_gui_config(self):
        if hasattr(self._args, "initial"):
            initial = f"'{self._args.initial.title()}'" if self._args.initial else "None"
            initial = initial.replace(PROGRAM_NAME.title(), PROGRAM_NAME)
            self._gui_config["__INITIAL__"] = initial
        if hasattr(self._args, "label"):
            self._gui_config["__LABEL__"] = f"'{self._args.label}'" if self._args.label else "None"
        if hasattr(self._args, "scale_by"):
            self._gui_config["__SCALE_BY__"] = str(self._args.scale_by)
        if hasattr(self._args, "press_for"):
            self._gui_config["__PRESS_FOR__"] = str(self._args.press_for)
        if hasattr(self._args, "track_id"):
            self._gui_config["__TRACK_ID__"] = str(self._args.track_id)
        if hasattr(self._args, "exclude_unnamed"):
            self._gui_config["__EXCLUDE_UNNAMED__"] = str(self._args.exclude_unnamed)
        if hasattr(self._args, "history"):
            self._gui_config["__NUM_RECENTS__"] = str(self._args.history)
        if hasattr(self._args, "scope"):
            scope = CommandScope.by_name(self._args.scope)
            if scope is None and self._args.scope.lower() == "accessory":
                scope = CommandScope.ACC
            self._gui_config["__INITIAL_SCOPE__"] = f"CommandScope.{scope.name}"
        else:
            self._gui_config["__INITIAL_SCOPE__"] = "None"
        if hasattr(self._args, "tmcc_id"):
            self._gui_config["__TMCC_ID__"] = str(self._args.tmcc_id)
        else:
            self._gui_config["__TMCC_ID__"] = "None"

    def construct_gui_stmt(self):
        stmt = CLASS_TO_TEMPLATE.get(self._gui_class)
        for key, value in self._gui_config.items():
            stmt = stmt.replace(key, value)
        return stmt

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
