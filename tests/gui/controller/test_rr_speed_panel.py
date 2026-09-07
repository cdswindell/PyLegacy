#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The official railroad speed pad, and how it shows the speed in force.

Headless: the panel is built over stand-in widgets, so what is asserted is what it asks of a
button rather than what Tk draws. That the border actually follows the color asked for is
HoldButton's own business, covered in tests/gui/test_hold_button.py.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.rr_speed_panel as mod
from src.pytrain.gui.controller.engine_gui_conf import RR_SPEED_LAYOUT

# What the host would answer for border_size; the panel only passes it along.
BORDER = 3
EMERGENCY = "Emergency\nStop"


class _Box:
    def __init__(self, _parent=None, **kwargs) -> None:
        self.kwargs = kwargs
        self.tk_configs: list[dict] = []
        self.tk = SimpleNamespace(config=lambda **config: self.tk_configs.append(config))


class _Button(_Box):
    """A keypad button: what the panel sets on one is all this has to remember."""

    def __init__(self) -> None:
        super().__init__()
        self.hold_threshold = None
        self.text_color = None
        self.bg = None
        self.border_thickness = 0
        self.on_hold = None


def _build(monkeypatch: pytest.MonkeyPatch, paints_face: bool = True):
    """Build the panel, answering it and its buttons keyed by the label each carries."""
    buttons: dict[str, _Button] = {}

    def make_keypad_button(_keypad_box, label, _row, _col, **_kwargs):
        button = _Button()
        buttons[label] = button
        return _Box(), button

    monkeypatch.setattr(mod, "Box", _Box)
    monkeypatch.setattr(mod, "paints_button_background", lambda _widget: paints_face)
    host = SimpleNamespace(
        button_size=90,
        s_18=18,
        border_size=BORDER,
        on_speed_command=lambda *_args: None,
    )
    host.make_keypad_button = make_keypad_button

    panel = mod.RrSpeedPanel.__new__(mod.RrSpeedPanel)
    panel._gui = host
    panel._rr_speed_btns = set()
    panel.build(_Box())
    return panel, buttons


def _state(speed: str | None) -> SimpleNamespace | None:
    """An engine reporting the railroad speed it is running at, or nothing selected."""
    return None if speed is None else SimpleNamespace(rr_speed=SimpleNamespace(name=speed))


def test_every_cell_is_given_a_border_to_carry_its_color(monkeypatch: pytest.MonkeyPatch) -> None:
    # A color on a button's face is not something macOS paints, so the border is what
    # shows there -- and the cell is a fixed size the button is already clipped to, so
    # asking for one costs this layout nothing.
    _panel, buttons = _build(monkeypatch)

    assert len(buttons) == sum(len(row) for row in RR_SPEED_LAYOUT)
    for label, button in buttons.items():
        assert button.border_thickness == BORDER, label


def test_the_speed_in_force_is_the_only_one_wearing_the_selection_color(monkeypatch: pytest.MonkeyPatch) -> None:
    panel, buttons = _build(monkeypatch)

    panel.configure(_state("SLOW"))

    assert buttons["Slow\nSpeed"].bg == "green"
    others = {label: button.bg for label, button in buttons.items() if label not in {"Slow\nSpeed", EMERGENCY}}
    assert set(others.values()) == {"white"}, others


def test_no_speed_is_marked_while_nothing_is_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    panel, buttons = _build(monkeypatch)

    panel.configure(_state(None))

    marked = [label for label, button in buttons.items() if button.bg == "green"]
    assert marked == []


def test_the_emergency_cell_keeps_white_text_where_its_red_face_is_painted(monkeypatch: pytest.MonkeyPatch) -> None:
    # The Pi, where Tk fills the face in itself and white is what reads against red.
    _panel, buttons = _build(monkeypatch, paints_face=True)

    assert buttons[EMERGENCY].bg == "red"
    assert buttons[EMERGENCY].text_color == "white"


def test_the_emergency_cell_takes_the_red_for_its_label_where_the_face_is_not_painted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # macOS, where the red never reaches the face: white on the face Aqua draws instead
    # left the label all but invisible, so the label is what carries the red.
    _panel, buttons = _build(monkeypatch, paints_face=False)

    assert buttons[EMERGENCY].bg == "red"
    assert buttons[EMERGENCY].text_color == "red"


def test_the_emergency_cell_is_not_one_of_the_speeds_to_choose_between(monkeypatch: pytest.MonkeyPatch) -> None:
    # It stays red through every selection: it is an action, not the speed in force.
    panel, buttons = _build(monkeypatch)

    panel.configure(_state("HIGHBALL"))

    assert buttons[EMERGENCY].bg == "red"
    assert buttons[EMERGENCY] not in panel._rr_speed_btns
