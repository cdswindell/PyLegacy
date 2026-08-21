#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from argparse import ArgumentTypeError
import builtins
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

import src.pytrain.cli.make_gui as mod
from src.pytrain.cli.make_gui import MakeGui
from src.pytrain.gui.component_state_gui import ComponentStateGui
from src.pytrain.gui.controller.engine_gui import EngineGui
from src.pytrain.gui.controller.steam_deck_gui import SteamDeckGui
from src.pytrain.utils.path_utils import find_file


def test_parse_wide_screen_set_normalizes_aliases_and_dedupes() -> None:
    parsed = MakeGui._parse_wide_screen_set("routes,power_districts,pd,RO")
    assert parsed == ["Routes", "Power Districts"]


def test_parse_wide_screen_set_accepts_alternate_delimiters() -> None:
    parsed = MakeGui._parse_wide_screen_set("systems|switches")
    assert parsed == ["PyTrain Administration", "Switches"]


def test_parse_wide_screen_set_accepts_operating_accessories_aliases() -> None:
    parsed = MakeGui._parse_wide_screen_set("operating,lcs,oa,accessories")
    assert parsed == ["Operating Accessories", "Accessories"]


def test_parse_wide_screen_set_rejects_unknown_component() -> None:
    with pytest.raises(ArgumentTypeError):
        _ = MakeGui._parse_wide_screen_set("routes,not_real")


def test_harvest_gui_config_includes_screen_components() -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._gui_config = {}
    mg._args = SimpleNamespace(
        initial="power districts",
        label="My Layout",
        scale_by=1.0,
        screens=2,
        screen_components=[["Routes", "Power Districts"], ["Switches"]],
    )

    mg.harvest_gui_config()

    assert mg._gui_config["__SCREENS__"] == "2"
    assert mg._gui_config["__SCREEN_COMPONENTS__"] == "[['Routes', 'Power Districts'], ['Switches']]"


def test_make_gui_parser_accepts_no_cache_sync() -> None:
    with mock.patch.object(builtins, "input", return_value="n"):
        assert MakeGui("-client -no_cache_sync component_state".split()) is not None


def test_make_gui_command_line_defaults_to_cache_sync_enabled() -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._exe = "pytrain"
    mg._args = SimpleNamespace(mode="client", ser2=False)
    mg._base_ip = None
    mg._echo = False
    mg._buttons_file = None
    mg._no_cache_sync = False

    assert mg.command_line == "pytrain -headless -client"


def test_make_gui_command_line_can_disable_cache_sync() -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._exe = "pytrain"
    mg._args = SimpleNamespace(mode="client", ser2=False)
    mg._base_ip = None
    mg._echo = False
    mg._buttons_file = None
    mg._no_cache_sync = True

    assert mg.command_line == "pytrain -headless -client -no_cache_sync"


def test_make_gui_shell_script_includes_cache_sync_switch_only_when_disabled(tmp_path) -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._gui_class = None  # no GUI class selected -> the default launch template
    mg._launch_path = tmp_path / "launch_pytrain.bash"
    mg._config = {
        "___ACTIVATE___": "/venv/bin/activate",
        "___BUTTONS___": "",
        "___CACHE_SYNC___": " -no_cache_sync",
        "___CLIENT___": " -client",
        "___ECHO___": "",
        "___LCSSER2___": "",
        "___LIONELBASE___": "",
        "___PYTRAIN___": "pytrain",
        "___PYTRAINHOME___": "/opt/pytrain",
    }

    path = mg.make_shell_script()

    assert path is not None
    assert "-no_cache_sync" in path.read_text(encoding="utf-8")

    mg._config["___CACHE_SYNC___"] = ""
    path = mg.make_shell_script()

    assert path is not None
    assert "-no_cache_sync" not in path.read_text(encoding="utf-8")


def test_landscape_aliases_template_and_font_selection() -> None:
    assert mod.GUI_ARG_TO_CLASS["landscape"] is mod.SteamDeckGui
    assert mod.GUI_ARG_TO_CLASS["steam_deck"] is mod.SteamDeckGui
    assert mod.GUI_ARG_TO_CLASS["deck"] is mod.SteamDeckGui
    template = mod.CLASS_TO_TEMPLATE[mod.SteamDeckGui]
    assert "width=__WIDTH__" in template
    assert "height=__HEIGHT__" in template
    assert "controller_profile=__CONTROLLER_PROFILE__" in template
    assert {mod.EngineGui, mod.SteamDeckGui}.issubset(mod.NEED_FONTS)


def test_project_packages_digital_dream_fonts() -> None:
    project = Path(__file__).parents[2] / "pyproject.toml"

    assert '"pytrain.gui" = ["fonts/**/*.ttf"]' in project.read_text(encoding="utf-8")


def test_harvest_landscape_config_includes_native_size_and_profile() -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._gui_config = {}
    mg._args = SimpleNamespace(
        width=1280,
        height=800,
        controller_profile="~/deck-controls.json",
    )

    mg.harvest_gui_config()

    assert mg._gui_config["__WIDTH__"] == "1280"
    assert mg._gui_config["__HEIGHT__"] == "800"
    assert mg._gui_config["__CONTROLLER_PROFILE__"] == "'~/deck-controls.json'"


def test_make_gui_parser_constructs_landscape_controller() -> None:
    with mock.patch.object(builtins, "input", return_value="n"):
        mg = MakeGui("-client landscape -controller_profile ~/deck-controls.json".split())

    assert mg._gui_class is mod.SteamDeckGui
    assert mg._args.width == 1280
    assert mg._args.height == 800
    assert mg.construct_gui_stmt() == (
        "SteamDeckGui(width=1280, height=800, controller_profile='~/deck-controls.json')"
    )


def test_font_install_uses_xdg_directory_refreshes_and_verifies(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "digital.ttf").write_bytes(b"font")
    installed = tmp_path / ".local" / "share" / "fonts" / "pytrain"
    runs: list[list[str]] = []
    monkeypatch.setattr(mod, "find_dir", lambda *_args: source)
    monkeypatch.setattr(mod.subprocess, "run", lambda command, **_kwargs: runs.append(command))
    mg = MakeGui.__new__(MakeGui)
    mg._fonts_path = installed
    mg.verify_tk_font = lambda: True

    result = mg.install_fonts()

    assert result == installed
    assert (installed / "digital.ttf").exists()
    assert runs == [["fc-cache", "-f", str(installed)]]


def test_steam_deck_gui_reports_its_platform() -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._gui_class = SteamDeckGui

    assert mg.platform == "steamdeck"


@pytest.mark.parametrize("gui_class", [EngineGui, ComponentStateGui, None])
def test_other_guis_imply_no_platform(gui_class) -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._gui_class = gui_class

    assert mg.platform == ""


def test_launch_template_exposes_the_platform_placeholder() -> None:
    # make_shell_script() substitutes one config dict into the template, so a missing
    # placeholder would silently emit a launcher with no platform set.
    template = find_file("launch_pytrain.bash.template", (".", "../", "src"))
    assert template is not None

    body = Path(template).read_text(encoding="utf-8")
    assert 'export PYTRAIN_PLATFORM="___PLATFORM___"' in body


@pytest.mark.parametrize(
    "gui_class, expected",
    [(SteamDeckGui, "steamdeck"), (EngineGui, "")],
)
def test_shell_script_exports_the_platform_it_was_generated_for(tmp_path, gui_class, expected) -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._gui_class = gui_class
    mg._launch_path = tmp_path / "launch_pytrain.bash"
    mg._config = {
        "___ACTIVATE___": "/venv/bin/activate",
        "___BUTTONS___": "",
        "___CACHE_SYNC___": "",
        "___CLIENT___": " -client",
        "___ECHO___": "",
        "___LCSSER2___": "",
        "___LIONELBASE___": "",
        "___PLATFORM___": mg.platform,
        "___PYTRAIN___": "pytrain",
        "___PYTRAINHOME___": "/opt/pytrain",
    }

    path = mg.make_shell_script()

    assert path is not None
    written = path.read_text(encoding="utf-8")
    assert f'export PYTRAIN_PLATFORM="{expected}"' in written
    assert "___" not in written  # every placeholder resolved


def test_postprocess_config_records_the_platform() -> None:
    mg = MakeGui.__new__(MakeGui)
    mg._gui_class = SteamDeckGui
    mg._imports = "from pytrain import *"
    mg._gui_config = {"__WIDTH__": "1280", "__HEIGHT__": "800", "__CONTROLLER_PROFILE__": "None"}
    mg._config = {}

    mg.postprocess_config()

    assert mg._config["___PLATFORM___"] == "steamdeck"
