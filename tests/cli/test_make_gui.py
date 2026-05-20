#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from argparse import ArgumentTypeError
import builtins
from types import SimpleNamespace
from unittest import mock

import pytest

from src.pytrain.cli.make_gui import MakeGui


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
