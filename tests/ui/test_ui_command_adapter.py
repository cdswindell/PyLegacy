from __future__ import annotations

from dataclasses import dataclass

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain_ui.adapters.commands import PyTrainCabCommandAdapter
from pytrain_ui.contracts import EngineViewState


@dataclass
class _State:
    tmcc_id: int = 12
    scope: CommandScope = CommandScope.ENGINE
    is_legacy: bool = True
    is_diesel: bool = True
    is_steam: bool = False
    is_passenger: bool = False
    is_freight: bool = False
    is_acela: bool = False
    is_electric: bool = False
    is_crane: bool = False
    is_transformer: bool = False


class _StateAdapter:
    def __init__(self, state: _State) -> None:
        self.state = state

    def current(self) -> EngineViewState:
        return EngineViewState(scope=self.state.scope.name, tmcc_id=self.state.tmcc_id)


class _SentReq:
    def __init__(self, sends: list[bool]) -> None:
        self._sends = sends

    def send(self) -> None:
        self._sends.append(True)


def _capture_build(monkeypatch):
    built: list[tuple[object, int, int, CommandScope]] = []
    sends: list[bool] = []

    def build(command, address=1, data=0, scope=None):
        built.append((command, address, data, scope))
        return _SentReq(sends)

    monkeypatch.setattr(CommandReq, "build", staticmethod(build))
    return built, sends


def test_legacy_smoke_uses_multibyte_factory(monkeypatch) -> None:
    built, sends = _capture_build(monkeypatch)
    adapter = PyTrainCabCommandAdapter(_StateAdapter(_State()))

    assert adapter.perform("smoke_up") is True
    assert built[0][0].name == "SMOKE_HIGH"
    assert built[0][1:] == (12, 0, CommandScope.ENGINE)
    assert sends == [True]


def test_electric_pantograph_uses_multibyte_factory(monkeypatch) -> None:
    built, sends = _capture_build(monkeypatch)
    state = _State(is_diesel=False, is_electric=True)
    adapter = PyTrainCabCommandAdapter(_StateAdapter(state))

    assert adapter.perform("pantograph_front_up") is True
    assert built[0][0].name == "PANTO_FRONT_UP_CAB2"
    assert sends == [True]


def test_ordinary_engine_action_uses_command_factory(monkeypatch) -> None:
    built, sends = _capture_build(monkeypatch)
    adapter = PyTrainCabCommandAdapter(_StateAdapter(_State()))

    assert adapter.perform("volume_up") is True
    assert built[0][0].name == "VOLUME_UP"
    assert sends == [True]


def test_legacy_momentum_preserves_all_eight_levels(monkeypatch) -> None:
    built, sends = _capture_build(monkeypatch)
    adapter = PyTrainCabCommandAdapter(_StateAdapter(_State()))

    adapter.set_momentum(6)
    assert built[0][0].name == "MOMENTUM"
    assert built[0][2] == 6
    assert sends == [True]


def test_train_brake_uses_zero_to_seven_data(monkeypatch) -> None:
    built, sends = _capture_build(monkeypatch)
    adapter = PyTrainCabCommandAdapter(_StateAdapter(_State()))

    adapter.set_train_brake(99)
    assert built[0][0].name == "TRAIN_BRAKE"
    assert built[0][2] == 7
    assert sends == [True]


def test_quilling_horn_uses_zero_to_fifteen_data(monkeypatch) -> None:
    built, sends = _capture_build(monkeypatch)
    adapter = PyTrainCabCommandAdapter(_StateAdapter(_State()))

    adapter.set_quilling_horn(11)
    assert built[0][0].name == "QUILLING_HORN"
    assert built[0][2] == 11
    assert sends == [True]
