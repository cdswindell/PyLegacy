from __future__ import annotations

from threading import RLock
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.engine_gui as mod
from src.pytrain.protocol.constants import CommandScope


class DummyAdapter:
    def __init__(self):
        self.overlay = None
        self.activations: list[int] = []

    def activate_tmcc_id(self, tmcc_id: int) -> None:
        self.activations.append(tmcc_id)


class DummyProvider:
    def __init__(self, mapping: dict[int, list[DummyAdapter]]):
        self._mapping = mapping
        self.calls: list[int] = []

    def adapters_for_tmcc_id(self, tmcc_id: int) -> list[DummyAdapter]:
        self.calls.append(tmcc_id)
        return list(self._mapping.get(tmcc_id, ()))


class DummyAccessoryState:
    def __init__(
        self,
        *,
        is_sensor_track: bool = False,
        is_bpc2: bool = False,
        is_asc2: bool = False,
        is_amc2: bool = False,
    ) -> None:
        self.is_sensor_track = is_sensor_track
        self.is_bpc2 = is_bpc2
        self.is_asc2 = is_asc2
        self.is_amc2 = is_amc2


def _new_engine() -> mod.EngineGui:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._cv = RLock()
    gui._caap = DummyProvider({})
    gui._acc_tmcc_to_adapter = {}
    gui._accessory_view = {}
    gui._amc2_ops_panel = None
    return gui


def test_get_configured_accessory_caches_adapter_and_activates_tmcc() -> None:
    gui = _new_engine()
    adapter = DummyAdapter()
    gui._caap = DummyProvider({44: [adapter]})

    first = gui.get_configured_accessory(44)
    second = gui.get_configured_accessory(44)

    assert first is adapter
    assert second is adapter
    assert gui._caap.calls == [44]
    assert adapter.activations == [44]


def test_get_configured_accessory_caches_none_when_no_adapter() -> None:
    gui = _new_engine()
    gui._caap = DummyProvider({})

    first = gui.get_configured_accessory(77)
    second = gui.get_configured_accessory(77)

    assert first is None
    assert second is None
    assert gui._caap.calls == [77]
    assert 77 in gui._acc_tmcc_to_adapter
    assert gui._acc_tmcc_to_adapter[77] is None


def test_get_accessory_view_builds_overlay_once_and_caches() -> None:
    gui = _new_engine()
    adapter = DummyAdapter()
    gui._caap = DummyProvider({12: [adapter]})
    created: list[DummyAdapter] = []

    def fake_create_accessory_view(acc: DummyAdapter):
        created.append(acc)
        acc.overlay = object()
        return acc.overlay

    gui._create_accessory_view = fake_create_accessory_view

    first = gui.get_accessory_view(12)
    second = gui.get_accessory_view(12)

    assert first is second
    assert created == [adapter]
    assert adapter.activations == [12, 12]


def test_set_accessory_view_allows_explicit_none() -> None:
    gui = _new_engine()

    gui.set_accessory_view(9, None)

    assert gui._accessory_view[9] is None


def test_on_new_accessory_calls_update_ac_status_for_asc2(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = _new_engine()
    gui._scope_tmcc_ids = {CommandScope.ACC: 15}
    seen: list[DummyAccessoryState] = []
    gui.update_ac_status = lambda state: seen.append(state)
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)

    state = DummyAccessoryState(is_asc2=True)
    gui.on_new_accessory(state)

    assert seen == [state]


def test_on_new_accessory_updates_sensor_track_value(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = _new_engine()
    gui._scope_tmcc_ids = {CommandScope.ACC: 22}
    gui.sensor_track_buttons = SimpleNamespace(value=None)
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
    monkeypatch.setattr(mod, "IrdaState", type("DummyIrdaState", (), {}), raising=True)
    gui._state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, include: mod.IrdaState() if tmcc_id == 22 else None
    )
    setattr(mod.IrdaState, "sequence", SimpleNamespace(value="SEQUENCE_A"))

    state = DummyAccessoryState(is_sensor_track=True)
    gui.on_new_accessory(state)

    assert gui.sensor_track_buttons.value == "SEQUENCE_A"


def test_on_new_accessory_updates_amc2_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = _new_engine()
    gui._scope_tmcc_ids = {CommandScope.ACC: 35}
    seen: list[DummyAccessoryState] = []
    gui._amc2_ops_panel = SimpleNamespace(update_from_state=lambda state: seen.append(state))
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)

    state = DummyAccessoryState(is_amc2=True)
    gui.on_new_accessory(state)

    assert seen == [state]
