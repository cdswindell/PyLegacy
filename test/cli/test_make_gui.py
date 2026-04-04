#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from argparse import ArgumentTypeError
from types import SimpleNamespace

import pytest

from src.pytrain.cli.make_gui import MakeGui


def test_parse_wide_screen_set_normalizes_aliases_and_dedupes() -> None:
    parsed = MakeGui._parse_wide_screen_set("routes,power_districts,pd,RO")
    assert parsed == ["Routes", "Power Districts"]


def test_parse_wide_screen_set_accepts_alternate_delimiters() -> None:
    parsed = MakeGui._parse_wide_screen_set("systems|switches")
    assert parsed == ["PyTrain Administration", "Switches"]


def test_parse_wide_screen_set_accepts_operating_accessories_aliases() -> None:
    parsed = MakeGui._parse_wide_screen_set("oa,accessories")
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
