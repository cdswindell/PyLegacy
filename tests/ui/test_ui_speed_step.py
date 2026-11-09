"""Direct speed nudges must use reported speed and respect ramp ownership."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from pytrain_ui.adapters.commands import PyTrainCabCommandAdapter
from pytrain_ui.adapters.state import PyTrainCabStateAdapter


@pytest.fixture
def speed_control(monkeypatch: pytest.MonkeyPatch):
    state = SimpleNamespace(
        tmcc_id=12,
        scope=CommandScope.ENGINE,
        is_legacy=True,
        speed=40,
        target_speed=150,
        speed_max=199,
        is_ramp_active=False,
    )
    state_adapter = Mock(spec=PyTrainCabStateAdapter)
    state_adapter.state = state
    adapter = PyTrainCabCommandAdapter(state_adapter)
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)
    monkeypatch.setattr(
        "pytrain_ui.adapters.commands.RampSpeedReq",
        Mock(side_effect=AssertionError("A speed nudge must not create a ramp")),
    )
    return state, adapter, build


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("legacy,current,delta,expected", [(True, 40, 1, 41), (True, 40, -1, 39), (False, 10, 1, 11)])
def test_speed_step_sends_absolute_speed_from_current_speed(speed_control, scope, legacy, current, delta, expected):
    state, adapter, build = speed_control
    state.scope = scope
    state.is_legacy = legacy
    state.speed = current
    command = TMCC2EngineCommandEnum if legacy else TMCC1EngineCommandEnum

    assert adapter.step_speed(delta)

    build.assert_called_once_with(command.ABSOLUTE_SPEED, 12, data=expected, scope=scope)
    build.return_value.send.assert_called_once_with()


@pytest.mark.parametrize("current,delta,ceiling", [(0, -1, 199), (199, 1, 199), (80, 1, 80)])
def test_speed_step_at_a_limit_sends_nothing(speed_control, current, delta, ceiling):
    state, adapter, build = speed_control
    state.speed = current
    state.speed_max = ceiling

    assert not adapter.step_speed(delta)
    build.assert_not_called()


def test_speed_step_rechecks_live_ramp_activity_on_every_request(speed_control):
    state, adapter, build = speed_control
    assert adapter.step_speed(1)
    build.reset_mock()
    state.is_ramp_active = True

    assert not adapter.step_speed(-1)
    build.assert_not_called()

    state.is_ramp_active = False
    state.speed = 55
    assert adapter.step_speed(-1)
    build.assert_called_once_with(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 12, data=54, scope=CommandScope.ENGINE)


def test_speed_step_with_unknown_current_speed_sends_nothing(speed_control):
    state, adapter, build = speed_control
    state.speed = None

    assert not adapter.step_speed(1)
    build.assert_not_called()
