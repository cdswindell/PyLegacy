"""State editors send the selected engine's protocol and address scope."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from pytrain_ui.adapters.commands import PyTrainCabCommandAdapter
from pytrain_ui.adapters.state import PyTrainCabStateAdapter


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("level", range(8))
def test_momentum_editor_protocol_and_levels(monkeypatch, legacy: bool, scope: CommandScope, level: int) -> None:
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)
    adapter = PyTrainCabCommandAdapter(
        Mock(spec=PyTrainCabStateAdapter, state=SimpleNamespace(is_legacy=legacy, scope=scope, tmcc_id=31))
    )
    adapter.set_momentum(level)
    if legacy:
        build.assert_called_once_with(TMCC2EngineCommandEnum.MOMENTUM, 31, data=level, scope=scope)
    else:
        command = (
            TMCC1EngineCommandEnum.MOMENTUM_LOW
            if level == 0
            else TMCC1EngineCommandEnum.MOMENTUM_HIGH
            if level == 7
            else TMCC1EngineCommandEnum.MOMENTUM_MEDIUM
        )
        assert build.call_args.args[:2] == (command, 31)
        assert build.call_args.kwargs["scope"] == scope
    build.return_value.send.assert_called_once_with()


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("level", range(4))
def test_smoke_editor_absolute_level(monkeypatch, legacy: bool, scope: CommandScope, level: int) -> None:
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)
    adapter = PyTrainCabCommandAdapter(
        Mock(spec=PyTrainCabStateAdapter, state=SimpleNamespace(is_legacy=legacy, scope=scope, tmcc_id=31))
    )
    adapter.set_smoke(level)
    command = (
        (
            TMCC2EffectsControl.SMOKE_OFF,
            TMCC2EffectsControl.SMOKE_LOW,
            TMCC2EffectsControl.SMOKE_MEDIUM,
            TMCC2EffectsControl.SMOKE_HIGH,
        )[level]
        if legacy
        else TMCC1EngineCommandEnum.SMOKE_ON
        if level
        else TMCC1EngineCommandEnum.SMOKE_OFF
    )
    assert build.call_args.args[:2] == (command, 31)
    assert build.call_args.kwargs["scope"] == scope
    build.return_value.send.assert_called_once_with()


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("level", range(8))
def test_train_brake_editor_requires_legacy(monkeypatch, legacy: bool, level: int) -> None:
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)
    adapter = PyTrainCabCommandAdapter(
        Mock(spec=PyTrainCabStateAdapter, state=SimpleNamespace(is_legacy=legacy, scope=CommandScope.TRAIN, tmcc_id=31))
    )
    adapter.set_train_brake(level)
    if legacy:
        build.assert_called_once_with(TMCC2EngineCommandEnum.TRAIN_BRAKE, 31, data=level, scope=CommandScope.TRAIN)
        build.return_value.send.assert_called_once_with()
    else:
        build.assert_not_called()


@pytest.mark.parametrize(
    ("legacy", "rpm_capable", "labor", "rpm", "expected"),
    [
        (True, True, 31, 7, [(TMCC2EngineCommandEnum.ENGINE_LABOR, 31), (TMCC2EngineCommandEnum.DIESEL_RPM, 7)]),
        (True, False, 0, 4, [(TMCC2EngineCommandEnum.ENGINE_LABOR, 0)]),
        (False, True, 12, 3, []),
        (True, True, 32, -1, []),
    ],
)
def test_labor_and_rpm_editor_commands(
    monkeypatch, legacy: bool, rpm_capable: bool, labor: int, rpm: int, expected: list
) -> None:
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)
    state = SimpleNamespace(is_legacy=legacy, is_rpm=rpm_capable, scope=CommandScope.TRAIN, tmcc_id=31)
    adapter = PyTrainCabCommandAdapter(Mock(spec=PyTrainCabStateAdapter, state=state))

    adapter.set_labor(labor)
    adapter.set_rpm(rpm)

    assert build.call_count == len(expected)
    for request, (command, level) in zip(build.call_args_list, expected):
        assert request.args == (command, 31)
        assert request.kwargs == {"data": level, "scope": CommandScope.TRAIN}
    assert build.return_value.send.call_count == len(expected)
