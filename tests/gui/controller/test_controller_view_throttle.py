#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""The throttle lever: the pending target speed the Speed slider shows.

Headless: the view is built over stand-in widgets, so what is asserted is the value the
lever asks of the slider and whether a speed command went out -- not what Tk draws. The
engine states are stand-ins too, with mod.EngineState pointed at them so the view's
isinstance guards accept them.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.controller_view as mod


class _FakeState:
    """An engine as far as the throttle path is concerned."""

    def __init__(
        self,
        speed: int = 0,
        target_speed: int | None = None,
        speed_max: int = 195,
        is_cab1: bool = False,
    ) -> None:
        self.speed = speed
        self.target_speed = target_speed
        self.speed_max = speed_max
        self.is_cab1 = is_cab1
        self.is_legacy = not is_cab1
        self.is_forward = True
        self.is_reverse = False
        self.momentum = 0
        self.train_brake = 0


class _FakeSlider:
    """A slider that remembers where it was put, and who is said to hold focus."""

    def __init__(self, value: int = 0) -> None:
        self.value = value
        self.enabled = True
        self.configs: list[dict] = []
        self.focus_holder = object()
        self.tk = SimpleNamespace(
            config=lambda **kwargs: self.configs.append(kwargs),
            focus_displayof=lambda: self.focus_holder,
        )


class _FakeText:
    def __init__(self) -> None:
        self.value = ""
        self.enabled = True


def _view(state: _FakeState | None, monkeypatch: pytest.MonkeyPatch):
    """A ControllerView over stand-ins, with the speed commands it sends recorded."""
    monkeypatch.setattr(mod, "EngineState", _FakeState)

    speed_calls: list[int] = []
    host = SimpleNamespace(
        throttle_state=state,
        throttle=_FakeSlider(),
        speed=_FakeText(),
        momentum=_FakeSlider(),
        momentum_level=_FakeText(),
        brake=_FakeSlider(),
        brake_level=_FakeText(),
        engine_ops_cells=None,
        on_speed_command=speed_calls.append,
    )
    host._rr_speed_panel = None
    host._rr_speed_btn = None
    host._active_bg = "green"
    host._inactive_bg = "white"

    view = mod.ControllerView.__new__(mod.ControllerView)
    view._host = host
    view._updating_from_state = False
    view._throttle_intent = None
    view._gauges = {}
    view._controller_info_box = SimpleNamespace(visible=False, show=lambda: None, hide=lambda: None)
    view._last_state = view._last_throttle_state = state
    view._quill_after_id = None
    return view, host, speed_calls


def test_the_lever_starts_from_the_speed_the_engine_says_it_is_headed_for(monkeypatch: pytest.MonkeyPatch) -> None:
    # target_speed is where the engine is going, so that is where a new lever picks up --
    # not the speed it happens to be passing through on the way there.
    view, host, speed_calls = _view(_FakeState(speed=20, target_speed=60), monkeypatch)

    assert view.throttle_intent_base() == 60
    assert view.nudge_throttle_intent(5) == 65
    assert host.throttle.value == 65
    assert speed_calls == []


def test_the_lever_falls_back_to_the_speed_when_no_target_is_announced(monkeypatch: pytest.MonkeyPatch) -> None:
    view, _host, _speed_calls = _view(_FakeState(speed=42, target_speed=None), monkeypatch)

    assert view.throttle_intent_base() == 42
    assert view.nudge_throttle_intent(0) == 42


def test_holding_the_lever_up_stops_at_the_engines_top_speed(monkeypatch: pytest.MonkeyPatch) -> None:
    view, host, speed_calls = _view(_FakeState(speed=0, target_speed=0, speed_max=100), monkeypatch)

    for _ in range(5):
        value = view.nudge_throttle_intent(40)

    assert value == 100
    assert host.throttle.value == 100
    assert speed_calls == []


def test_holding_the_lever_down_stops_at_a_stand_and_never_goes_below(monkeypatch: pytest.MonkeyPatch) -> None:
    view, host, _speed_calls = _view(_FakeState(speed=30, target_speed=30), monkeypatch)

    for _ in range(4):
        value = view.nudge_throttle_intent(-20)

    assert value == 0
    assert host.throttle.value == 0


def test_a_speed_limit_arriving_mid_gesture_pulls_the_lever_back_down(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _FakeState(speed=0, target_speed=0, speed_max=195)
    view, _host, _speed_calls = _view(state, monkeypatch)

    assert view.nudge_throttle_intent(120) == 120
    state.speed_max = 60

    assert view.nudge_throttle_intent(1) == 60


def test_a_cab_1_engine_has_no_lever_to_move(monkeypatch: pytest.MonkeyPatch) -> None:
    # Its stick sends relative steps and never builds a ramp, so there is nothing pending.
    view, _host, speed_calls = _view(_FakeState(is_cab1=True), monkeypatch)

    assert view.nudge_throttle_intent(10) is None
    assert view.throttle_intent_active is False
    assert speed_calls == []


def test_no_engine_selected_leaves_the_lever_unseeded(monkeypatch: pytest.MonkeyPatch) -> None:
    view, _host, speed_calls = _view(None, monkeypatch)

    assert view.nudge_throttle_intent(10) is None
    assert view.throttle_intent_active is False
    assert speed_calls == []


def test_committing_sends_one_command_for_where_the_lever_rests(monkeypatch: pytest.MonkeyPatch) -> None:
    view, _host, speed_calls = _view(_FakeState(speed=0, target_speed=0), monkeypatch)

    view.nudge_throttle_intent(37.4)
    view.commit_throttle_intent()

    assert speed_calls == [37]


def test_committing_an_explicit_speed_leaves_the_lever_where_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    # The lead command asks for a speed ahead of the lever; the lever keeps its own position
    # so the settle that follows can still send where the operator actually stopped.
    view, _host, speed_calls = _view(_FakeState(speed=0, target_speed=0), monkeypatch)

    view.nudge_throttle_intent(10)
    view.commit_throttle_intent(80)

    assert speed_calls == [80]
    assert view.throttle_intent == 10


def test_committing_clamps_to_the_engines_top_speed(monkeypatch: pytest.MonkeyPatch) -> None:
    view, host, speed_calls = _view(_FakeState(speed=0, target_speed=0, speed_max=75), monkeypatch)

    view.commit_throttle_intent(400)

    assert speed_calls == [75]
    assert host.throttle.value == 75


def test_committing_with_no_lever_held_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    view, _host, speed_calls = _view(_FakeState(speed=10, target_speed=10), monkeypatch)

    view.commit_throttle_intent()

    assert speed_calls == []


def test_clearing_the_lever_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    view, _host, speed_calls = _view(_FakeState(speed=0, target_speed=0), monkeypatch)

    view.nudge_throttle_intent(25)
    view.clear_throttle_intent()

    assert view.throttle_intent_active is False
    assert view.throttle_intent is None
    assert speed_calls == []


def test_a_state_refresh_leaves_the_slider_on_the_lever(monkeypatch: pytest.MonkeyPatch) -> None:
    # The engine is still reporting the old target while the lever is held; letting the
    # refresh win would drag the handle out from under the operator's thumb.
    state = _FakeState(speed=10, target_speed=10)
    view, host, _speed_calls = _view(state, monkeypatch)

    assert view.nudge_throttle_intent(70) == 80
    view.update(state, state)

    assert host.throttle.value == 80


def test_a_state_refresh_moves_the_slider_once_the_lever_is_let_go(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _FakeState(speed=10, target_speed=10)
    view, host, _speed_calls = _view(state, monkeypatch)

    view.nudge_throttle_intent(70)
    view.clear_throttle_intent()
    state.target_speed = 55
    view.update(state, state)

    assert host.throttle.value == 55


def test_a_touch_drag_takes_the_lever_back_from_the_stick(monkeypatch: pytest.MonkeyPatch) -> None:
    # Releasing the slider is authoritative: it sends where the handle was dropped and
    # drops the lever, so a later commit cannot resurrect the stick's stale target.
    state = _FakeState(speed=0, target_speed=0)
    view, host, speed_calls = _view(state, monkeypatch)
    idle_calls: list = []
    host.app = SimpleNamespace(tk=SimpleNamespace(after_idle=idle_calls.append))
    view._cancel_cab_1_throttle_repeat = lambda: None

    view.nudge_throttle_intent(90)
    host.throttle.value = 30
    view._on_throttle_release_event()

    assert speed_calls == [30]
    assert view.throttle_intent_active is False

    view.commit_throttle_intent()

    assert speed_calls == [30]
