from __future__ import annotations

from collections import deque
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


class DummyConfiguredAccessory:
    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id


class DummyConfiguredSet:
    def __init__(self, *instance_ids: str) -> None:
        self.path = "accessory_config.json"
        self._accessories = [DummyConfiguredAccessory(instance_id) for instance_id in instance_ids]

    def configured_all(self) -> list[DummyConfiguredAccessory]:
        return list(self._accessories)


class DummyReloadProvider(DummyProvider):
    def __init__(self, mapping: dict[int, list[DummyAdapter]] | None = None) -> None:
        super().__init__(mapping or {})
        self.set_calls: list[tuple[DummyConfiguredSet, bool]] = []

    def set_configured_set(self, configured_set: DummyConfiguredSet, *, drop_adapters: bool = True) -> None:
        self.set_calls.append((configured_set, drop_adapters))


class DummyPopup:
    def __init__(self) -> None:
        self.close_calls = 0
        self.discard_calls = 0
        self.forgot: list[set[str]] = []

    def close(self) -> None:
        self.close_calls += 1

    def discard_acc_overlay_restore(self) -> None:
        self.discard_calls += 1

    def forget(self, keys: set[str]) -> None:
        self.forgot.append(set(keys))


class DummyOverlay:
    def __init__(self, overlay_key: str, *, visible: bool = True) -> None:
        self.overlay_key = overlay_key
        self.visible = visible
        self.hide_calls = 0

    def hide(self) -> None:
        self.hide_calls += 1
        self.visible = False


class DummyKeypadView:
    def __init__(self) -> None:
        self.scope_keypad_calls: list[tuple[bool, bool]] = []

    def scope_keypad(self, force_entry_mode: bool = False, clear_info: bool = True) -> None:
        self.scope_keypad_calls.append((force_entry_mode, clear_info))


class DummyCatalogPanel:
    def __init__(self) -> None:
        self.reset_calls = 0

    def reset_configured_accessory_cache(self) -> None:
        self.reset_calls += 1


class DummyTk:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, object]] = []

    def after(self, delay: int, callback) -> str:
        self.after_calls.append((delay, callback))
        return f"after-{len(self.after_calls)}"


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


def _new_reload_engine() -> mod.EngineGui:
    gui = _new_engine()
    gui._accessory_config_file = "accessory_config.json"
    gui._caa = DummyConfiguredSet("old_a")
    gui._caap = DummyReloadProvider()
    gui._acc_tmcc_to_adapter = {12: object()}
    gui._accessory_view = {12: object()}
    gui._acc_overlay = None
    gui._popup = DummyPopup()
    gui._keypad_view = DummyKeypadView()
    gui._scope_tmcc_ids = {CommandScope.ACC: 12}
    gui.scope = CommandScope.ACC
    gui.tmcc_id_box = SimpleNamespace(text="Accessory ID")
    gui.scope_box = SimpleNamespace(visible=False, show=lambda: setattr(gui.scope_box, "visible", True))
    gui._accessory_overlay_prewarm_queue = deque([object()])
    gui._accessory_overlay_prewarm_active = True
    gui._accessory_overlay_prewarm_generation = 1
    gui._shutdown_flag = SimpleNamespace(is_set=lambda: False)
    gui._app = SimpleNamespace(tk=DummyTk())
    gui._catalog_panel = None
    gui._transition_depth = 0
    gui._options_rebuild_pending = False
    gui._rebuild_options_calls = 0
    gui.rebuild_options = lambda: setattr(gui, "_rebuild_options_calls", gui._rebuild_options_calls + 1)
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


def test_reload_configured_accessories_reindexes_and_restarts_prewarm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gui = _new_reload_engine()
    new_config = DummyConfiguredSet("new_a")

    monkeypatch.setattr(
        mod.ConfiguredAccessorySet,
        "from_file",
        classmethod(lambda cls, path, verify=True: new_config),
        raising=True,
    )

    assert gui.reload_configured_accessories() is True

    assert gui._caa is new_config
    assert gui._caap.set_calls == [(new_config, True)]
    assert gui._acc_tmcc_to_adapter == {}
    assert gui._accessory_view == {}
    assert gui._popup.forgot == [{"old_a"}]
    assert gui._popup.discard_calls == 1
    assert gui._popup.close_calls == 0
    assert gui._keypad_view.scope_keypad_calls == []
    assert gui._accessory_overlay_prewarm_generation == 2
    assert gui._accessory_overlay_prewarm_active is False
    assert list(gui._accessory_overlay_prewarm_queue) == []
    assert gui.app.tk.after_calls and gui.app.tk.after_calls[-1][0] == 25
    assert gui._rebuild_options_calls == 1


def test_reload_configured_accessories_resets_catalog_panel_when_it_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gui = _new_reload_engine()
    catalog_panel = DummyCatalogPanel()
    gui._catalog_panel = catalog_panel
    new_config = DummyConfiguredSet("new_a")

    monkeypatch.setattr(
        mod.ConfiguredAccessorySet,
        "from_file",
        classmethod(lambda cls, path, verify=True: new_config),
        raising=True,
    )

    assert gui.reload_configured_accessories() is True

    assert catalog_panel.reset_calls == 1


def test_reload_configured_accessories_resets_active_overlay_to_acc_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gui = _new_reload_engine()
    overlay = DummyOverlay("active_overlay", visible=True)
    gui._acc_overlay = overlay
    gui._scope_tmcc_ids[CommandScope.ACC] = 44
    new_config = DummyConfiguredSet("new_a")

    monkeypatch.setattr(
        mod.ConfiguredAccessorySet,
        "from_file",
        classmethod(lambda cls, path, verify=True: new_config),
        raising=True,
    )

    assert gui.reload_configured_accessories() is True

    assert gui._acc_overlay is None
    assert overlay.hide_calls == 1
    assert gui._popup.forgot == [{"old_a", "active_overlay"}]
    assert gui._popup.discard_calls == 1
    assert gui._popup.close_calls == 1
    assert gui.scope == CommandScope.ACC
    assert gui._scope_tmcc_ids[CommandScope.ACC] == 0
    assert gui.tmcc_id_box.text == f"{CommandScope.ACC.title} ID"
    assert gui._keypad_view.scope_keypad_calls == [(True, True)]
    assert gui.scope_box.visible is True


def test_reload_configured_accessories_failure_leaves_existing_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gui = _new_reload_engine()
    original_config = gui._caa
    original_tmcc_cache = dict(gui._acc_tmcc_to_adapter)
    original_view_cache = dict(gui._accessory_view)

    def raise_reload(_cls, _path, verify=True):
        raise ValueError("bad config")

    monkeypatch.setattr(mod.ConfiguredAccessorySet, "from_file", classmethod(raise_reload), raising=True)

    assert gui.reload_configured_accessories() is False

    assert gui._caa is original_config
    assert gui._caap.set_calls == []
    assert gui._acc_tmcc_to_adapter == original_tmcc_cache
    assert gui._accessory_view == original_view_cache
    assert gui._popup.forgot == []
    assert gui._popup.discard_calls == 0
    assert gui.app.tk.after_calls == []
