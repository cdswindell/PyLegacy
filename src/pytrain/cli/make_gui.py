#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from argparse import ArgumentParser, ArgumentTypeError
from pathlib import Path

from .make_base import _MakeBase
from .pytrain import DEFAULT_BUTTONS_FILE
from ..gui.accessories_gui import AccessoriesGui
from ..gui.component_state_gui import ComponentStateGui
from ..gui.controller.engine_gui import EngineGui
from ..gui.controller.steam_deck_gui import SteamDeckGui
from ..gui.guizero_base import resolve_font_family
from ..gui.launch_gui import LaunchGui
from ..gui.motors_gui import MotorsGui
from ..gui.power_district_gui import PowerDistrictsGui
from ..gui.routes_gui import RoutesGui
from ..gui.switches_gui import SwitchesGui
from ..gui.systems_gui import SystemsGui
from ..gui.wide_component_state_gui import WideComponentStateGui
from ..protocol.constants import CommandScope, PROGRAM_BASE, PROGRAM_NAME
from ..utils.argument_parser import IntRange, PyTrainArgumentParser, UniqueChoice
from ..utils.host_info import STEAM_DECK_PLATFORM
from ..utils.path_utils import find_dir, find_file

GUI_ARG_TO_CLASS = {
    "ac": AccessoriesGui,
    "accessories": AccessoriesGui,
    "co": ComponentStateGui,
    "component_state": ComponentStateGui,
    "cp": EngineGui,
    "control_panel": EngineGui,
    "deck": SteamDeckGui,
    "landscape": SteamDeckGui,
    "steam_deck": SteamDeckGui,
    "sd": SteamDeckGui,
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
    "wide": WideComponentStateGui,
    "wco": WideComponentStateGui,
    "wide_component_state": WideComponentStateGui,
    "wide_state": WideComponentStateGui,
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
    " exclude_unnamed=__EXCLUDE_UNNAMED__, screens=__SCREENS__)",
    WideComponentStateGui: f"{WideComponentStateGui.name()}(label=__LABEL__, initial=__INITIAL__,"
    " scale_by=__SCALE_BY__, exclude_unnamed=__EXCLUDE_UNNAMED__, screens=__SCREENS__,"
    " screen_components=__SCREEN_COMPONENTS__, launch_tmcc_id=__TMCC_ID__, launch_track_id=__TRACK_ID__)",
    LaunchGui: f"{LaunchGui.__name__}(tmcc_id=__TMCC_ID__, track_id=__TRACK_ID__)",
    MotorsGui: f"{MotorsGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__)",
    PowerDistrictsGui: f"{PowerDistrictsGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__,"
    " exclude_unnamed=__EXCLUDE_UNNAMED__)",
    RoutesGui: f"{RoutesGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__)",
    SwitchesGui: f"{SwitchesGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__, exclude_unnamed=__EXCLUDE_UNNAMED__)",
    SystemsGui: f"{SystemsGui.name()}(label=__LABEL__, scale_by=__SCALE_BY__, press_for=__PRESS_FOR__)",
    EngineGui: f"{EngineGui.__name__}(scope=__SCOPE__, tmcc_id=__TMCC_ID__,"
    " scale_by=__SCALE_BY__, num_recents=__NUM_RECENTS__)",
    SteamDeckGui: f"{SteamDeckGui.__name__}(width=__WIDTH__, height=__HEIGHT__,"
    " controller_profile=__CONTROLLER_PROFILE__)",
}

NEED_FONTS = {
    EngineGui,
    SteamDeckGui,
    LaunchGui,
}

LAUNCH_TEMPLATE = "launch_pytrain.bash.template"
# Platform a GUI implies, exported by the generated launcher as PYTRAIN_PLATFORM and
# read back through HostInfo. One launcher template serves every platform: the value
# selects which platform-specific setup it applies, and lets application code branch
# without re-detecting the hardware. Empty for GUIs that imply no particular platform.
CLASS_TO_PLATFORM = {
    SteamDeckGui: STEAM_DECK_PLATFORM,
}

CHOICES = [
    "accessories",
    "motors",
    "power districts",
    "routes",
    "switches",
    f"{PROGRAM_NAME} Administration".lower(),
]
WIDE_CHOICES = CHOICES + ["operating accessories", "launch pad"]

CHOICES_HELP = ", ".join([x.title() for x in CHOICES]).replace(PROGRAM_NAME.title(), PROGRAM_NAME)
WIDE_CHOICES_HELP = ", ".join([x.title() for x in WIDE_CHOICES]).replace(PROGRAM_NAME.title(), PROGRAM_NAME)

WIDE_COMPONENT_ALIASES = {
    "accessories": "Accessories",
    "accessory": "Accessories",
    "ac": "Accessories",
    "operating accessories": "Operating Accessories",
    "operating accessory": "Operating Accessories",
    "operating_accessories": "Operating Accessories",
    "operating_accessory": "Operating Accessories",
    "configured": "Operating Accessories",
    "configured accessories": "Operating Accessories",
    "configured accessory": "Operating Accessories",
    "op accessories": "Operating Accessories",
    "op accessory": "Operating Accessories",
    "operating": "Operating Accessories",
    "lcs": "Operating Accessories",
    "oa": "Operating Accessories",
    "launch pad": "Launch Pad",
    "launch pads": "Launch Pad",
    "launch": "Launch Pad",
    "launchpad": "Launch Pad",
    "pad": "Launch Pad",
    "la": "Launch Pad",
    "lp": "Launch Pad",
    "motors": "Motors",
    "motor": "Motors",
    "mo": "Motors",
    "power districts": "Power Districts",
    "power district": "Power Districts",
    "power_districts": "Power Districts",
    "power_district": "Power Districts",
    "pd": "Power Districts",
    "po": "Power Districts",
    "routes": "Routes",
    "route": "Routes",
    "ro": "Routes",
    "switches": "Switches",
    "switch": "Switches",
    "sw": "Switches",
    f"{PROGRAM_NAME} administration".lower(): f"{PROGRAM_NAME} Administration",
    "administration": f"{PROGRAM_NAME} Administration",
    "admin": f"{PROGRAM_NAME} Administration",
    "systems": f"{PROGRAM_NAME} Administration",
    "system": f"{PROGRAM_NAME} Administration",
    "sy": f"{PROGRAM_NAME} Administration",
    "pa": f"{PROGRAM_NAME} Administration",
}

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
        self._desktop_autostart = True
        super().__init__(cmd_line)

    def program(self) -> str:
        return "make_gui"

    def function(self) -> str:
        return "GUI"

    def postprocess_args(self) -> None:
        from .. import is_package

        if not self._args.remove and not self._args.gui:
            self._parser.error("the following arguments are required: gui")
        if self._args.start is True:
            self._start_gui = True
        if self._args.exclude_unnamed:
            self._exclude_unnamed = True
        # Only the Steam Deck subparser defines -desktop_autostart, and only there is the
        # autostart entry opt-in: the Deck launches PyTrain from Steam, so an entry that
        # also starts it with the desktop session is redundant. Every other GUI keeps the
        # entry unconditionally, hence the getattr default of True.
        self._desktop_autostart = getattr(self._args, "desktop_autostart", True)
        self._buttons_file = DEFAULT_BUTTONS_FILE
        self._launch_path = Path(self._home, "launch_pytrain.bash")
        self._desktop_path = Path(self._home, ".config", "autostart", "pytrain.desktop")
        self._buttons_path = Path(self._cwd, self._buttons_file)
        self._fonts_path = Path(self._home, ".local", "share", "fonts", "pytrain")
        self._imports = f"from {PROGRAM_BASE if is_package() else 'src.' + PROGRAM_BASE} import *"
        self._gui_class = GUI_ARG_TO_CLASS.get(self._args.gui)
        if self._gui_class is WideComponentStateGui and self._args.screen_components:
            screen_sets = len(self._args.screen_components)
            if screen_sets > 3:
                self._parser.error("wide supports at most 3 -show entries")
            if self._args.screens is not None and self._args.screens != screen_sets:
                self._parser.error(
                    f"-screens ({self._args.screens}) must match number of -show entries ({screen_sets})"
                )
            if self._args.screens is None:
                self._args.screens = screen_sets
        self.harvest_gui_config()

    @staticmethod
    def _normalize_wide_component_name(value: str) -> str:
        key = value.strip().lower().replace("-", " ").replace("_", " ")
        key = " ".join(key.split())
        if key in WIDE_COMPONENT_ALIASES:
            return WIDE_COMPONENT_ALIASES[key]
        raise ArgumentTypeError(f"Invalid screen component '{value}'")

    @classmethod
    def _parse_wide_screen_set(cls, value: str) -> list[str]:
        tokens = [token.strip() for token in re.split(r"[,+|/]", value) if token.strip()]
        if not tokens:
            raise ArgumentTypeError("Each -show must include at least one GUI name")
        gui_names = []
        for token in tokens:
            canonical = cls._normalize_wide_component_name(token)
            if canonical not in gui_names:
                gui_names.append(canonical)
        return gui_names

    def postprocess_config(self) -> None:
        self._config["___IMPORTS___"] = self._imports
        self._config["___GUI___"] = self._gui_stmt = self.construct_gui_stmt()
        self._config["___PLATFORM___"] = self.platform

    @property
    def platform(self) -> str:
        """Platform the configured GUI implies, or "" when it implies none.

        Baked into the generated launcher as PYTRAIN_PLATFORM so both the launcher and
        PyTrain itself can apply platform-specific handling.
        """
        return CLASS_TO_PLATFORM.get(self._gui_class, "")

    def config_header(self) -> list[str]:
        lines = list()
        lines.append(f"\nInstalling the {PROGRAM_NAME} {self._gui_class.__name__} GUI with these settings:")
        lines.append(f"  Start GUI now: {'Yes' if self._start_gui is True else 'No'}")
        if hasattr(self._args, "desktop_autostart"):
            # Shown only where it is a choice, so every other GUI's prompt is unchanged.
            lines.append(f"  Autostart with desktop session: {'Yes' if self._desktop_autostart else 'No'}")
        lines.append(f"  Imports: {self._imports}")
        lines.append(f"  GUI: {self._gui_stmt}")
        return lines

    def install(self) -> str:
        path = self.make_shell_script()
        if path:
            self._config["___SHELL_SCRIPT___"] = str(path)
        else:
            return

        if self._desktop_autostart:
            # No config entry for the result: nothing substitutes a desktop path into a
            # template, unlike ___SHELL_SCRIPT___ and ___BUTTONS___ below.
            if not self.make_python_desktop_file():
                return
        else:
            self.remove_desktop_autostart()

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

    def remove_desktop_autostart(self) -> None:
        """Clear an autostart entry left by an earlier install.

        Installing without -desktop_autostart has to be authoritative: leaving a stale
        entry in place would keep starting PyTrain with the desktop session while the
        command that just ran said it should not.
        """
        if self._desktop_path.exists():
            print(f"\nRemoving autostart entry {self._desktop_path}...")
            self._desktop_path.unlink(missing_ok=True)

    def remove(self) -> str:
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

        # Steam Deck landscape controller
        deck = sp.add_parser(
            "landscape",
            aliases=["deck", "steam_deck", "sd", "landscape"],
            allow_abbrev=True,
            help="Steam Deck Landscape Controller",
        )
        deck.add_argument(
            "-width",
            type=IntRange(640, 3840),
            default=1280,
            help="Window width (default: 1280)",
        )
        deck.add_argument(
            "-height",
            type=IntRange(480, 2160),
            default=800,
            help="Window height (default: 800)",
        )
        deck.add_argument(
            "-controller_profile",
            type=str,
            default=None,
            help="Steam Deck JSON controller profile (default: bundled profile)",
        )
        deck.add_argument(
            "-desktop_autostart",
            action="store_true",
            help="Also start PyTrain when a desktop session starts (default: no, launch it from Steam instead)",
        )

        # Launch Pad GUI
        pad = sp.add_parser(
            "launch_pad",
            aliases=["la", "lp", "pad"],
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
        comp.add_argument(
            "-screens",
            type=IntRange(1, 3),
            default=None,
            metavar="",
            help="Virtual 800x480 screens to render side-by-side (1-3, default: auto by width)",
        )

        # Wide Component State GUI
        wcomp = sp.add_parser(
            "wide",
            aliases=["wco", "wide_state", "wide_component_state"],
            allow_abbrev=True,
            help="Wide Component State GUI (2-3 screens side-by-side)",
        )
        wcomp.add_argument(
            "-initial",
            type=UniqueChoice(WIDE_CHOICES),
            nargs="?",
            const="power districts",
            default="power districts",
            help=f"Initial Display (default: Power Districts, choices: {WIDE_CHOICES_HELP})",
        )
        wcomp.add_argument(
            "-label",
            type=str,
            help="Layout Name",
        )
        wcomp.add_argument(
            "-scale_by",
            type=float,
            default=1.0,
            help="Text Scale Factor (default: 1.0)",
        )
        wcomp.add_argument(
            "-screens",
            type=IntRange(1, 3),
            default=None,
            metavar="",
            help="Virtual screens (1-3). Default: 2 when -show omitted, else count of -show entries",
        )
        wcomp.add_argument(
            "-show",
            "-screen_set",
            dest="screen_components",
            action="append",
            type=self._parse_wide_screen_set,
            metavar="",
            help="One screen's GUI set (repeat once per screen), comma-separated names; e.g. 'routes,power_districts'",
        )
        wcomp.add_argument(
            "-tmcc_id",
            type=IntRange(1, 98),
            default=39,
            const=39,
            nargs="?",
            help="Launch Pad TMCC ID when Launch Pad is included (default: 39)",
        )
        wcomp.add_argument(
            "-track_id",
            type=IntRange(1, 98),
            help="Launch Pad Track Power District TMCC ID when Launch Pad is included",
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
            aliases=["pa", "sy", "admin", "ad", "py"],
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
        template = find_file(LAUNCH_TEMPLATE, (".", "../", "src"))
        if template is None:
            print(f"\nUnable to locate shell script template {LAUNCH_TEMPLATE}. Exiting")
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
            subprocess.run(["fc-cache", "-f", str(path)], check=False)
            if not self.verify_tk_font():
                print("Digital dream is not visible to Tk; using TkDefaultFont fallback")
            print(f"Installed fonts to: {path}")
        except shutil.Error as e:
            print(f"Error copying directory: {e}")
            path = None
        except OSError as e:
            print(f"Error: {e}")
            path = None
        return path

    @staticmethod
    def verify_tk_font() -> bool:
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            return resolve_font_family(root, "DigitalDream") != "TkDefaultFont"
        except (RuntimeError, tk.TclError):
            return False
        finally:
            if root is not None:
                root.destroy()

    def harvest_gui_config(self):
        if hasattr(self._args, "initial"):
            initial = f"'{self._args.initial.title()}'" if self._args.initial else "None"
            initial = initial.replace(PROGRAM_NAME.title(), PROGRAM_NAME)
            self._gui_config["__INITIAL__"] = initial
        if hasattr(self._args, "label"):
            self._gui_config["__LABEL__"] = f"'{self._args.label}'" if self._args.label else "None"
        if hasattr(self._args, "scale_by"):
            self._gui_config["__SCALE_BY__"] = str(self._args.scale_by)
        if hasattr(self._args, "screens"):
            self._gui_config["__SCREENS__"] = str(self._args.screens)
        if hasattr(self._args, "screen_components"):
            self._gui_config["__SCREEN_COMPONENTS__"] = (
                repr(self._args.screen_components) if self._args.screen_components else "None"
            )
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
            self._gui_config["__SCOPE__"] = f"CommandScope.{scope.name}"
        else:
            self._gui_config["__SCOPE__"] = "None"
        if hasattr(self._args, "tmcc_id"):
            self._gui_config["__TMCC_ID__"] = str(self._args.tmcc_id)
        else:
            self._gui_config["__TMCC_ID__"] = "None"
        if hasattr(self._args, "width"):
            self._gui_config["__WIDTH__"] = str(self._args.width)
        if hasattr(self._args, "height"):
            self._gui_config["__HEIGHT__"] = str(self._args.height)
        if hasattr(self._args, "controller_profile"):
            profile = self._args.controller_profile
            self._gui_config["__CONTROLLER_PROFILE__"] = repr(profile) if profile else "None"

    def construct_gui_stmt(self):
        stmt = CLASS_TO_TEMPLATE.get(self._gui_class)
        for key, value in self._gui_config.items():
            stmt = stmt.replace(key, value)
        return stmt

    @property
    def is_gui_present(self) -> bool:
        """Whether any GUI install exists here, so -remove has something to clean up.

        The launcher is written by every install; the autostart entry is opt-in on the
        Steam Deck (-desktop_autostart). Requiring both would make -remove report "no GUI
        detected" for a Steam-launched Deck install and refuse to remove its launcher.
        """
        launch_path = Path(self._home, "launch_pytrain.bash")
        desktop_path = Path(self._home, ".config", "autostart", "pytrain.desktop")
        return launch_path.exists() or desktop_path.exists()


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        MakeGui(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{__file__}: error: {e}\n")
