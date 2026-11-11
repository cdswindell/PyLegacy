"""State editors send the selected engine's protocol and address scope."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CAB1_CONTROL_TYPE, LEGACY_CONTROL_TYPE, TMCC_CONTROL_TYPE, CommandScope
from pytrain.protocol.multibyte.multibyte_constants import TMCC2EffectsControl, TMCC2RailSoundsDialogControl
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, TMCC2RRSpeedsEnum
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
    ("scope", "control_type", "rpm_capable", "labor", "rpm", "expected"),
    [
        (
            CommandScope.TRAIN,
            LEGACY_CONTROL_TYPE,
            True,
            31,
            7,
            [(TMCC2EngineCommandEnum.ENGINE_LABOR, 31), (TMCC2EngineCommandEnum.DIESEL_RPM, 7)],
        ),
        (
            CommandScope.ENGINE,
            TMCC_CONTROL_TYPE,
            True,
            12,
            3,
            [(TMCC2EngineCommandEnum.ENGINE_LABOR, 12), (TMCC2EngineCommandEnum.DIESEL_RPM, 3)],
        ),
        (CommandScope.ENGINE, TMCC_CONTROL_TYPE, False, 0, 4, [(TMCC2EngineCommandEnum.ENGINE_LABOR, 0)]),
        (CommandScope.ENGINE, CAB1_CONTROL_TYPE, True, 12, 3, []),
        (CommandScope.TRAIN, TMCC_CONTROL_TYPE, True, 12, 3, []),
        (CommandScope.ENGINE, LEGACY_CONTROL_TYPE, True, 32, -1, []),
    ],
)
def test_labor_and_rpm_editor_commands(
    monkeypatch, scope: CommandScope, control_type: int, rpm_capable: bool, labor: int, rpm: int, expected: list
) -> None:
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)
    state = SimpleNamespace(
        is_legacy=control_type == LEGACY_CONTROL_TYPE,
        control_type=control_type,
        is_rpm=rpm_capable,
        scope=scope,
        tmcc_id=31,
    )
    adapter = PyTrainCabCommandAdapter(Mock(spec=PyTrainCabStateAdapter, state=state))

    adapter.set_labor(labor)
    adapter.set_rpm(rpm)

    assert build.call_count == len(expected)
    for request, (command, level) in zip(build.call_args_list, expected):
        assert request.args == (command, 31)
        assert request.kwargs == {"data": level, "scope": scope}
    assert build.return_value.send.call_count == len(expected)


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize(
    "command",
    [
        command
        for command in TMCC2RailSoundsDialogControl
        if command.name.startswith(("TOWER_SPEED_", "ENGINEER_SPEED_"))
    ],
)
def test_speed_dialog_sends_only_the_sound_command(
    monkeypatch, scope: CommandScope, command: TMCC2RailSoundsDialogControl
) -> None:
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)
    adapter = PyTrainCabCommandAdapter(
        Mock(spec=PyTrainCabStateAdapter, state=SimpleNamespace(is_legacy=True, scope=scope, tmcc_id=31))
    )

    assert adapter.play_dialog(command.name)
    assert not adapter.play_dialog("ABSOLUTE_SPEED")
    assert not adapter.play_dialog("SPEED_HIGHBALL")
    build.assert_called_once_with(command, 31, scope=scope)
    build.return_value.send.assert_called_once_with()


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_emergency_stop_sends_zero_and_only_the_emergency_dialog(
    monkeypatch, legacy: bool, scope: CommandScope
) -> None:
    build = Mock()
    monkeypatch.setattr(CommandReq, "build", build)
    state = SimpleNamespace(
        is_legacy=legacy,
        scope=scope,
        tmcc_id=31,
        has_throttle=True,
        is_remote_ramping=True,
        cancel_ramps=Mock(),
    )
    adapter = PyTrainCabCommandAdapter(Mock(spec=PyTrainCabStateAdapter, state=state))

    adapter.set_speed_preset("EMERGENCY_STOP")

    state.cancel_ramps.assert_called_once_with(0, reason="Emergency stop", hard_stop=True, yield_speed=0)
    speed_command = TMCC2EngineCommandEnum.ABSOLUTE_SPEED if legacy else TMCC1EngineCommandEnum.ABSOLUTE_SPEED
    assert build.mock_calls == [
        call(speed_command, 31, data=0, scope=scope),
        call().send(),
        call(TMCC2RailSoundsDialogControl.EMERGENCY_CONTEXT_DEPENDENT, 31, scope=scope),
        call().send(delay=0.2),
    ]


@pytest.mark.parametrize("with_dialog", [False, True])
def test_normal_stop_uses_the_zero_speed_ramp(monkeypatch, with_dialog: bool) -> None:
    ramp = Mock()
    dialog_ramp = Mock()
    monkeypatch.setattr("pytrain_ui.adapters.commands.RampSpeedReq", ramp)
    monkeypatch.setattr("pytrain_ui.adapters.commands.RampSpeedDialogReq", dialog_ramp)
    state = SimpleNamespace(
        is_legacy=True, scope=CommandScope.ENGINE, tmcc_id=31, has_throttle=True, is_remote_ramping=False
    )
    adapter = PyTrainCabCommandAdapter(Mock(spec=PyTrainCabStateAdapter, state=state))

    adapter.set_speed_preset("STOP_HOLD", with_dialog)

    if with_dialog:
        assert dialog_ramp.mock_calls == [call(31, TMCC2RRSpeedsEnum.STOP_HOLD, CommandScope.ENGINE), call().send()]
        ramp.assert_not_called()
    else:
        assert ramp.mock_calls == [call(31, 0, CommandScope.ENGINE), call().send()]
        dialog_ramp.assert_not_called()
