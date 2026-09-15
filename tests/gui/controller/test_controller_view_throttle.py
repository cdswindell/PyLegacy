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
        ramp: SimpleNamespace | None = None,
    ) -> None:
        self.speed = speed
        self.target_speed = target_speed
        self.ramp = ramp
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


class _FakeClock:
    """The module's monotonic, under the test's control.

    The commit latch expires on a deadline measured in seconds; crossing it by sleeping
    would put THROTTLE_COMMIT_GRACE of real time into the suite for no added coverage.
    """

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    clock = _FakeClock()
    monkeypatch.setattr(mod, "monotonic", clock)
    return clock


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
    view._throttle_committed = None
    view._throttle_committed_at = None
    view._gauges = {}
    view._controller_info_box = SimpleNamespace(visible=False, show=lambda: None, hide=lambda: None)
    view._last_state = view._last_throttle_state = state
    view._quill_after_id = None
    return view, host, speed_calls


def test_the_lever_starts_from_the_speed_the_engine_says_it_is_headed_for(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only the locally owned ramp supplies a destination, not a database target.
    ramp = SimpleNamespace(is_active=True, requested_speed=60)
    view, host, speed_calls = _view(_FakeState(speed=20, target_speed=90, ramp=ramp), monkeypatch)

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
    view, host, speed_calls = _view(_FakeState(speed=0, target_speed=0), monkeypatch)

    view.nudge_throttle_intent(10)
    view.commit_throttle_intent(80)

    assert speed_calls == [80]
    assert view.throttle_intent == 10
    # And the handle stays with it. A lead is a projection rather than a selection: painting
    # it on the slider threw the handle 70 steps up the dial for the one tick before the next
    # nudge dragged it back, which is the swing the operator sees as the lever lurching.
    assert host.throttle.value == 10


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
    state.speed = 55
    view.update(state, state)

    assert host.throttle.value == 55


def _committed(monkeypatch: pytest.MonkeyPatch, *, speed: int = 5, lever: int = 68):
    """A finished direct gesture awaiting the reported speed, with no local ramp."""
    state = _FakeState(speed=speed, target_speed=0)
    view, host, speed_calls = _view(state, monkeypatch)
    clock = _clock(monkeypatch)

    view.nudge_throttle_intent(lever - speed)
    view.commit_throttle_intent()
    view.clear_throttle_intent()
    return view, host, state, speed_calls, clock


def test_the_handle_stays_on_the_committed_speed_while_the_engine_is_still_catching_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The thumb comes off at 68 and the state is still advertising 106. Without the latch the
    # refresh drops the handle to 106 for as long as it takes the echo to arrive.
    view, host, state, speed_calls, _clk = _committed(monkeypatch)
    assert speed_calls == [68]

    state.target_speed = 106
    view.update(state, state)

    assert host.throttle.value == 68


def test_the_handle_follows_the_engine_again_once_it_announces_the_committed_speed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view, host, state, _speed_calls, _clk = _committed(monkeypatch)

    state.speed = 68
    view.update(state, state)
    assert host.throttle.value == 68

    # Agreed, so a later reported speed moves the handle, even with a stale target.
    state.speed = 40
    view.update(state, state)

    assert host.throttle.value == 40


def test_the_handle_stops_waiting_for_a_command_that_never_lands(monkeypatch: pytest.MonkeyPatch) -> None:
    # A HALT, or another controller taking the throttle, means the committed speed is never
    # announced. The grace is what keeps that from pinning the handle for good.
    view, host, state, _speed_calls, clock = _committed(monkeypatch)
    state.speed = 106

    view.update(state, state)
    assert host.throttle.value == 68, "still inside the grace"

    clock.advance(mod.THROTTLE_COMMIT_GRACE)
    view.update(state, state)

    assert host.throttle.value == 106


def test_a_new_lever_starts_from_the_speed_last_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    # Seeded from the state instead, a gesture begun in that window picks up the target the
    # engine is about to stop announcing, and the handle jumps on the very first nudge.
    view, host, state, _speed_calls, _clk = _committed(monkeypatch)
    state.target_speed = 106

    assert view.throttle_intent_base() == 68
    assert view.nudge_throttle_intent(5) == 73
    assert host.throttle.value == 73


def test_clearing_the_throttle_drops_the_latch_as_well_as_the_lever(monkeypatch: pytest.MonkeyPatch) -> None:
    # What EngineGui.clear_throttle() calls: a HALT, a reset, or a different engine selected
    # leaves nothing worth standing on, so the handle is free to follow the engine down.
    view, host, state, _speed_calls, _clk = _committed(monkeypatch)
    state.speed = 106

    view.clear_throttle_intent()
    view.clear_throttle_commit()
    view.update(state, state)

    assert host.throttle.value == 106


def test_a_commit_the_engine_is_already_obeying_still_holds_the_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    # Nothing goes on the wire when the engine is already at the speed asked for, but it is
    # still what the operator asked for and the handle is to stay on it.
    view, host, state, speed_calls, _clk = _committed(monkeypatch, speed=68)

    assert speed_calls == [], "the engine is already there"
    state.target_speed = 106
    view.update(state, state)

    assert host.throttle.value == 68


def test_a_cab_1_commit_takes_no_latch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Its stick asks for relative steps, so there is no absolute speed to wait on.
    view, _host, speed_calls = _view(_FakeState(speed=0, target_speed=0, is_cab1=True), monkeypatch)
    _clock(monkeypatch)

    view._send_throttle_value(30)

    assert speed_calls == [0]
    assert view._throttle_committed is None


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


@pytest.mark.parametrize("ramp_status", ["missing", "absent", "inactive", "active"])
@pytest.mark.parametrize("requested_speed", [0, 20, 60])
def test_only_an_active_local_ramp_sets_the_display_and_gesture_baseline(
    monkeypatch: pytest.MonkeyPatch, ramp_status: str, requested_speed: int
) -> None:
    state = _FakeState(speed=20, target_speed=90)
    if ramp_status == "missing":
        del state.ramp
    elif ramp_status != "absent":
        state.ramp = SimpleNamespace(is_active=ramp_status == "active", requested_speed=requested_speed)
    view, host, speed_calls = _view(state, monkeypatch)

    view.update(state, state)

    expected = requested_speed if ramp_status == "active" else 20
    assert host.throttle.value == expected
    assert host.speed.value == "020"
    assert host.throttle.configs[-1]["troughcolor"] == ("#4C96C5" if expected != 20 else mod.LIONEL_BLUE)
    assert view.throttle_intent_base() == expected
    assert view.nudge_throttle_intent(5) == expected + 5
    assert speed_calls == []


@pytest.mark.parametrize("owns_ramp", [False, True])
def test_ramp_ownership_comes_from_the_throttle_state_not_the_selected_engine(
    monkeypatch: pytest.MonkeyPatch, owns_ramp: bool
) -> None:
    ramp = SimpleNamespace(is_active=True, requested_speed=60)
    state = _FakeState(speed=20, target_speed=90, ramp=None if owns_ramp else ramp)
    throttle_state = _FakeState(speed=20, target_speed=90, ramp=ramp if owns_ramp else None)
    view, host, speed_calls = _view(throttle_state, monkeypatch)

    view.update(state, throttle_state)

    assert host.throttle.value == (60 if owns_ramp else 20)
    assert host.speed.value == "020"
    assert view.throttle_intent_base() == (60 if owns_ramp else 20)
    assert speed_calls == []


@pytest.mark.parametrize("held", ["touch", "lever"])
def test_a_local_ramp_refresh_does_not_move_a_held_gesture(monkeypatch: pytest.MonkeyPatch, held: str) -> None:
    state = _FakeState(speed=20, target_speed=90, ramp=SimpleNamespace(is_active=True, requested_speed=60))
    view, host, speed_calls = _view(state, monkeypatch)
    if held == "touch":
        host.throttle.focus_holder = host.throttle.tk
        host.throttle.value = 75
    else:
        view.nudge_throttle_intent(15)

    view.update(state, state)

    assert host.throttle.value == 75
    assert host.speed.value == "020"
    assert speed_calls == []

    state.ramp.is_active = False
    state.ramp = None
    state.speed = 30
    view.update(state, state)

    assert host.throttle.value == 75
    assert host.speed.value == "030"
    assert host.throttle.configs[-1]["troughcolor"] == mod.LIONEL_BLUE


def test_a_ramp_accepted_while_the_lever_is_held_does_not_leave_a_pending_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _FakeState(speed=20, target_speed=90, ramp=SimpleNamespace(is_active=True, requested_speed=60))
    view, host, speed_calls = _view(state, monkeypatch)
    _clock(monkeypatch)
    view.nudge_throttle_intent(15)
    view.commit_throttle_intent(100)

    # The old ramp must not acknowledge the new command while it is still pending.
    view.update(state, state)
    assert view._throttle_committed == 100
    assert view.throttle_intent_base() == 100
    assert host.throttle.value == 75

    state.ramp.requested_speed = 100
    view.update(state, state)
    assert view._throttle_committed is None
    assert host.throttle.value == 75

    state.ramp = None
    state.speed = 40
    view.clear_throttle_intent()
    view.update(state, state)

    assert host.throttle.value == 40
    assert view.throttle_intent_base() == 40
    assert speed_calls == [100]


def test_a_database_target_cannot_acknowledge_a_pending_direct_gesture(monkeypatch: pytest.MonkeyPatch) -> None:
    view, host, state, _speed_calls, _clock = _committed(monkeypatch)
    state.target_speed = 68
    view.update(state, state)
    state.target_speed = 90
    view.update(state, state)

    assert host.throttle.value == 68
    assert host.speed.value == "005"
    assert view.throttle_intent_base() == 68
    assert host.throttle.configs[-1]["troughcolor"] == mod.LIONEL_BLUE


def test_a_new_gesture_does_not_revive_an_expired_direct_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    view, host, state, _speed_calls, clock = _committed(monkeypatch)
    clock.advance(mod.THROTTLE_COMMIT_GRACE)
    state.speed = 40

    assert view.throttle_intent_base() == 40
    assert view.nudge_throttle_intent(5) == 45
    assert host.throttle.value == 45


def _ramping(monkeypatch: pytest.MonkeyPatch):
    state = _FakeState(speed=5, target_speed=106)
    view, host, speed_calls = _view(state, monkeypatch)
    clock = _clock(monkeypatch)

    def start_ramp(speed: int) -> None:
        speed_calls.append(speed)
        state.ramp = SimpleNamespace(is_active=True, requested_speed=speed)

    host.on_speed_command = start_ramp
    view.nudge_throttle_intent(63)
    view.commit_throttle_intent()
    view.clear_throttle_intent()
    return view, host, state, speed_calls, clock


def test_an_active_local_ramp_outlives_the_direct_commit_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    view, host, state, speed_calls, clock = _ramping(monkeypatch)
    clock.advance(mod.THROTTLE_COMMIT_GRACE * 2)
    state.speed = state.target_speed = 40

    view.update(state, state)

    assert speed_calls == [68]
    assert host.throttle.value == 68
    assert host.speed.value == "040"
    assert host.throttle.configs[-1]["troughcolor"] == "#4C96C5"
    assert view.throttle_intent_base() == 68


@pytest.mark.parametrize("refresh_before_release", [False, True])
@pytest.mark.parametrize("release", ["completed", "canceled", "takeover", "inactive"])
def test_releasing_a_local_ramp_immediately_releases_commit_protection(
    monkeypatch: pytest.MonkeyPatch, refresh_before_release: bool, release: str
) -> None:
    view, host, state, speed_calls, _clock = _ramping(monkeypatch)
    if refresh_before_release:
        view.update(state, state)
    state.ramp.is_active = False
    if release != "inactive":
        state.ramp = None
    state.speed = 68 if release == "completed" else 40

    assert view.throttle_intent_base() == state.speed
    view.update(state, state)

    assert host.throttle.value == state.speed
    assert host.speed.value == f"{state.speed:03d}"
    assert host.throttle.configs[-1]["troughcolor"] == mod.LIONEL_BLUE
    assert view._throttle_committed is None
    assert speed_calls == [68]


def test_a_commit_at_actual_speed_still_redirects_an_active_ramp(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _FakeState(speed=20, target_speed=90, ramp=SimpleNamespace(is_active=True, requested_speed=60))
    view, _host, speed_calls = _view(state, monkeypatch)

    view.commit_throttle_intent(20)

    assert speed_calls == [20]
