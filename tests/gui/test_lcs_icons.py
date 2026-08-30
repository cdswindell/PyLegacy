#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

"""The purpose-drawn generic-panel return icons exist, load, and are wired to the button logic."""

from __future__ import annotations

import pytest

from src.pytrain.gui.controller import engine_gui_conf as conf
from src.pytrain.gui.controller import keypad_view as kv
from src.pytrain.utils.path_utils import find_file

Image = pytest.importorskip("PIL.Image")

ICON_NAMES = [conf.BPC2_OP_IMAGE, conf.ASC2_OP_IMAGE, conf.OP_SCREEN_IMAGE]


@pytest.mark.parametrize("name", ICON_NAMES)
def test_the_icon_asset_is_present_and_loadable(name: str) -> None:
    path = find_file(name)
    assert path is not None, f"{name} was not found on the image search path"

    with Image.open(path) as img:
        img.load()
        assert img.width > 0 and img.height > 0


def test_the_return_key_icon_map_covers_both_lcs_panels() -> None:
    # The device icons drive the native-return direction of the shared key; a kind with no
    # entry falls back to the LCS text label rather than a blank key.
    assert kv.NATIVE_PANEL_RETURN_ICON[kv.PANEL_BPC2] == conf.BPC2_OP_IMAGE
    assert kv.NATIVE_PANEL_RETURN_ICON[kv.PANEL_ASC2] == conf.ASC2_OP_IMAGE
    assert kv.PANEL_SENSOR_TRACK not in kv.NATIVE_PANEL_RETURN_ICON


def test_the_navigation_key_labels_carry_their_ellipses() -> None:
    assert conf.ACC_PANEL_KEY == "Acc..."
    assert conf.LCS_NOOP_KEY == "LCS..."
