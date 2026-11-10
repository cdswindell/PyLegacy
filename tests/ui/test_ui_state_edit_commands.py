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
