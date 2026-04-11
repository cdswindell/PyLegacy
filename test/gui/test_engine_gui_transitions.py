from __future__ import annotations

from threading import RLock
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.engine_gui as mod
from src.pytrain.protocol.constants import CommandScope


class DummyState:
    def __init__(self, tmcc_id: int, name: str = "State Name", scope: CommandScope = CommandScope.ENGINE) -> None:
        self.tmcc_id = tmcc_id
        self.name = name
        self.scope = scope


class DummyAccessoryState:
    def __init__(self, tmcc_id: int, name: str = "Accessory State") -> None:
        self.tmcc_id = tmcc_id
        self.name = name
        self.scope = CommandScope.ACC


class DummyAdapter:
    def __init__(self, name: str = "Configured Accessory") -> None:
        self.name = name
        self.activations: list[int] = []

    def activate_tmcc_id(self, tmcc_id: int) -> None:
        self.activations.append(tmcc_id)


class DummyWatcher:
    def __init__(self, state, action) -> None:
        self.state = state
        self.action = action
        self.tmcc_id = state.tmcc_id
        self.shutdown_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def _new_engine(scope: CommandScope = CommandScope.ENGINE) -> mod.EngineGui:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._cv = RLock()
    gui.scope = scope
    gui._scope_tmcc_ids = {scope: 0}
    gui._scope_watchers = {}
    gui._shutdown_flag = SimpleNamespace(is_set=lambda: False)
    gui._popup_closed = 0
    gui._popup = SimpleNamespace(close=lambda: setattr(gui, "_popup_closed", gui._popup_closed + 1))
    gui.tmcc_id_text = SimpleNamespace(value="0000")
    gui.name_text = SimpleNamespace(value="")
    gui.image_box = SimpleNamespace(hide=lambda: None)
    gui._keypad_view = SimpleNamespace(reset_on_keystroke=False)
    gui._controller_view = SimpleNamespace()
    gui._train_linked_queue = []
    gui._acc_tmcc_to_adapter = {}
    gui._accessory_view = {}
    gui._active_train_state = None
    gui._active_engine_state = None
    gui._state_store = SimpleNamespace(get_state=lambda *_args, **_kwargs: None)
    gui._image_updates: list[int] = []
    gui._image_clears = 0
    gui._image_presenter = SimpleNamespace(
        update=lambda tmcc_id: gui._image_updates.append(tmcc_id),
        clear=lambda: setattr(gui, "_image_clears", gui._image_clears + 1),
    )
    gui._recent_calls: list[tuple[CommandScope, int, object]] = []
    gui.make_recent = lambda scope, tmcc_id, state=None: gui._recent_calls.append((scope, tmcc_id, state)) or True
    gui._ops_mode_calls: list[bool] = []
    gui.ops_mode = lambda update_info=False: gui._ops_mode_calls.append(update_info)
    gui._scoped_callback_calls: list[object] = []
    gui._scoped_callbacks = {scope: lambda state: gui._scoped_callback_calls.append(state)}
    return gui


def test_update_component_info_with_state_updates_ui_and_ops_mode() -> None:
    gui = _new_engine()
    state = DummyState(tmcc_id=34, name="Hudson")
    gui._scope_tmcc_ids[CommandScope.ENGINE] = 12
    gui.tmcc_id_text.value = "0012"
    gui._state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, include=False: state if (scope, tmcc_id) == (CommandScope.ENGINE, 12) else None
    )

    gui.update_component_info(12)

    assert gui._popup_closed == 1
    assert gui._scope_tmcc_ids[CommandScope.ENGINE] == 34
    assert gui.tmcc_id_text.value == "0034"
    assert gui.name_text.value == "Hudson"
    assert gui._recent_calls == [(CommandScope.ENGINE, 34, state)]
    assert gui._ops_mode_calls == [False]
    assert gui._scoped_callback_calls == []
    assert gui._image_updates == [34]


def test_update_component_info_without_state_uses_not_found_and_scoped_callback() -> None:
    gui = _new_engine()
    gui._scope_tmcc_ids[CommandScope.ENGINE] = 88
    gui.tmcc_id_text.value = "0088"

    gui.update_component_info(88, not_found_value="Missing")

    assert gui._popup_closed == 1
    assert gui._recent_calls == []
    assert gui._ops_mode_calls == []
    assert gui.name_text.value == "Missing"
    assert gui._scoped_callback_calls == [None]
    assert gui._image_updates == [88]


def test_update_component_info_zero_clears_image_and_resets_keystroke_flag() -> None:
    gui = _new_engine()
    gui._keypad_view.reset_on_keystroke = True

    gui.update_component_info(0)

    assert gui._popup_closed == 1
    assert gui._scope_tmcc_ids[CommandScope.ENGINE] == 0
    assert gui.tmcc_id_text.value == "0000"
    assert gui.name_text.value == ""
    assert gui._image_clears == 1
    assert gui._image_updates == [0]
    assert gui._keypad_view.reset_on_keystroke is False


def test_update_component_info_accessory_uses_configured_accessory_name(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = _new_engine(CommandScope.ACC)
    state = DummyAccessoryState(tmcc_id=21, name="Base Accessory")
    adapter = DummyAdapter(name="Panel Light")
    view = SimpleNamespace(caa=adapter)
    gui._scope_tmcc_ids[CommandScope.ACC] = 21
    gui.tmcc_id_text.value = "21"
    gui._state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, include=False: state if (scope, tmcc_id) == (CommandScope.ACC, 21) else None
    )
    gui.get_accessory_view = lambda tmcc_id: view if tmcc_id == 21 else None
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
    monkeypatch.setattr(mod, "StateWatcher", DummyWatcher, raising=True)

    gui.update_component_info(21)

    assert gui.name_text.value == "Panel Light"
    assert adapter.activations == [21]
    assert gui._recent_calls == [(CommandScope.ACC, 21, state)]
    assert gui._scoped_callback_calls == []
    assert gui._image_updates == [21]


def test_monitor_state_reuses_existing_watcher_and_replaces_on_tmcc_change(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = _new_engine()
    state_12 = DummyState(tmcc_id=12)
    state_44 = DummyState(tmcc_id=44)
    state_map = {12: state_12, 44: state_44}
    gui._state_store = SimpleNamespace(get_state=lambda scope, tmcc_id, include=False: state_map.get(tmcc_id))
    monkeypatch.setattr(mod, "StateWatcher", DummyWatcher, raising=True)

    gui._scope_tmcc_ids[CommandScope.ENGINE] = 12
    gui.monitor_state()
    first = gui._scope_watchers[CommandScope.ENGINE]

    gui.monitor_state()
    assert gui._scope_watchers[CommandScope.ENGINE] is first
    assert first.shutdown_calls == 0

    gui._scope_tmcc_ids[CommandScope.ENGINE] = 44
    gui.monitor_state()
    second = gui._scope_watchers[CommandScope.ENGINE]

    assert second is not first
    assert first.shutdown_calls == 1
    assert second.tmcc_id == 44
