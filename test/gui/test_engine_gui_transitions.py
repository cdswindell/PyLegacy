from __future__ import annotations

from threading import RLock
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.engine_gui as mod
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.utils.unique_deque import UniqueDeque


class DummyState:
    def __init__(self, tmcc_id: int, name: str = "State Name", scope: CommandScope = CommandScope.ENGINE) -> None:
        self.tmcc_id = tmcc_id
        self.address = tmcc_id
        self.name = name
        self.scope = scope

    def __repr__(self) -> str:
        return f"{self.scope.name}:{self.tmcc_id}"


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


class DummyTrainState(DummyState):
    def __init__(self, tmcc_id: int, linked_ids: list[int] | None = None, name: str = "Train") -> None:
        super().__init__(tmcc_id=tmcc_id, name=name, scope=CommandScope.TRAIN)
        self.link_tmcc_ids = list(linked_ids or [])
        self.num_train_linked = len(self.link_tmcc_ids)
        self.has_throttle = True

    def __contains__(self, item: object) -> bool:
        return isinstance(item, DummyState) and item.scope == CommandScope.ENGINE and item.tmcc_id in self.link_tmcc_ids


def _new_engine(scope: CommandScope = CommandScope.ENGINE) -> mod.EngineGui:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._cv = RLock()
    gui.scope = scope
    gui._scope_tmcc_ids = {CommandScope.ENGINE: 0, CommandScope.TRAIN: 0, scope: 0}
    gui._scope_watchers = {}
    gui._shutdown_flag = SimpleNamespace(is_set=lambda: False)
    gui._popup_closed = 0
    gui._popup = SimpleNamespace(close=lambda: setattr(gui, "_popup_closed", gui._popup_closed + 1))
    gui.tmcc_id_text = SimpleNamespace(value="0000")
    gui.tmcc_id_box = SimpleNamespace(text=f"{scope.title} ID")
    gui.name_text = SimpleNamespace(value="")
    gui.image_box = SimpleNamespace(hide=lambda: None)
    gui._keypad_view = SimpleNamespace(
        reset_on_keystroke=False,
        is_entry_mode=True,
        scope_keypad=lambda force_entry_mode, clear_info: setattr(
            gui, "_scope_keypad_args", (force_entry_mode, clear_info)
        ),
    )
    gui._controller_view = SimpleNamespace(update=lambda **_kwargs: None)
    gui._train_linked_queue = UniqueDeque()
    gui._acc_tmcc_to_adapter = {}
    gui._accessory_view = {}
    gui._active_train_state = None
    gui._active_engine_state = None
    gui._state_info = None
    gui._transition_depth = 0
    gui._options_rebuild_pending = False
    gui._last_displayed_scope = None
    gui._last_displayed_tmcc_id = None
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
    gui._scoped_callbacks = {
        CommandScope.ENGINE: lambda state: gui._scoped_callback_calls.append(("engine", state)),
        CommandScope.TRAIN: lambda state: gui._scoped_callback_calls.append(("train", state)),
        scope: lambda state: gui._scoped_callback_calls.append((scope.label, state)),
    }
    gui._scope_buttons = {
        CommandScope.ENGINE: SimpleNamespace(bg="white", text_color="black"),
        CommandScope.TRAIN: SimpleNamespace(bg="white", text_color="black"),
    }
    gui.scope_box = SimpleNamespace(
        hide=lambda: setattr(gui, "_scope_box_hidden", True),
        show=lambda: setattr(gui, "_scope_box_shown", True),
    )
    gui.header = SimpleNamespace(clear=lambda: None, append=lambda _value: None, select_default=lambda: None)
    gui._recents_queue = {}
    gui._separator = "---"
    gui._options_to_state = {}
    gui.rebuild_options = lambda: setattr(gui, "_rebuild_options_calls", getattr(gui, "_rebuild_options_calls", 0) + 1)
    gui.display_most_recent = mod.EngineGui.display_most_recent.__get__(gui, mod.EngineGui)
    gui._acc_overlay = None
    gui._enabled_bg = "green"
    gui._enabled_text = "black"
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
    assert gui._scoped_callback_calls == [("Engine", None)]
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


def test_on_new_train_builds_train_link_queue_and_sets_engine_scope_tmcc() -> None:
    gui = _new_engine(CommandScope.TRAIN)
    train_state = DummyTrainState(tmcc_id=77, linked_ids=[11, 12], name="Empire")
    linked_1 = DummyState(tmcc_id=11, name="Car 1")
    linked_2 = DummyState(tmcc_id=12, name="Car 2")
    gui._state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, include=False: {
            (CommandScope.ENGINE, 11): linked_1,
            (CommandScope.ENGINE, 12): linked_2,
        }.get((scope, tmcc_id))
    )
    gui._scope_buttons[CommandScope.ENGINE] = SimpleNamespace(bg="white", text_color="black")
    gui._scope_buttons[CommandScope.TRAIN] = SimpleNamespace(bg="white", text_color="black")

    gui.on_new_train(train_state)

    assert list(gui._train_linked_queue) == [linked_1, linked_2]
    assert gui._scope_tmcc_ids[CommandScope.ENGINE] == 11
    assert gui._active_train_state is train_state
    assert gui._scope_buttons[CommandScope.ENGINE].bg == "lightgreen"
    assert gui._rebuild_options_calls == 1


def test_on_scope_switches_between_engine_and_train_without_forcing_entry_mode() -> None:
    gui = _new_engine(CommandScope.ENGINE)
    engine_state = DummyState(tmcc_id=5, name="Hudson", scope=CommandScope.ENGINE)
    train_state = DummyTrainState(tmcc_id=9, linked_ids=[5], name="Empire")
    gui._recents_queue[CommandScope.ENGINE] = UniqueDeque([engine_state])
    gui._recents_queue[CommandScope.TRAIN] = UniqueDeque([train_state])
    gui._state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, include=False: {
            (CommandScope.ENGINE, 5): engine_state,
            (CommandScope.TRAIN, 9): train_state,
        }.get((scope, tmcc_id))
    )
    gui._scope_tmcc_ids[CommandScope.ENGINE] = 5
    gui._scope_tmcc_ids[CommandScope.TRAIN] = 0
    gui.monitor_state = lambda: None

    gui.on_scope(CommandScope.TRAIN)

    assert gui.scope == CommandScope.TRAIN
    assert gui._scope_tmcc_ids[CommandScope.TRAIN] == 9
    assert gui.tmcc_id_box.text == "Train ID"
    assert gui.tmcc_id_text.value == "0009"
    assert gui._scope_keypad_args == (False, True)
    assert gui._popup_closed == 2
    assert gui._rebuild_options_calls >= 1

    gui.on_scope(CommandScope.ENGINE)

    assert gui.scope == CommandScope.ENGINE
    assert gui.tmcc_id_box.text == "Engine ID"
    assert gui.tmcc_id_text.value == "0005"
    assert gui._scope_keypad_args == (False, True)


def test_on_new_engine_marks_train_scope_when_train_linked_engine_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gui = _new_engine(CommandScope.ENGINE)
    linked_engine = DummyState(tmcc_id=5, name="Car 1", scope=CommandScope.ENGINE)
    train_state = DummyTrainState(tmcc_id=9, linked_ids=[5], name="Empire")
    gui._active_train_state = train_state
    gui._train_linked_queue.append(linked_engine)
    gui._scope_buttons[CommandScope.TRAIN] = SimpleNamespace(bg="white", text_color="black")
    monkeypatch.setattr(mod, "EngineState", DummyState, raising=True)

    gui.on_new_engine(linked_engine, is_engine=True)

    assert gui._scope_buttons[CommandScope.TRAIN].bg == "lightgreen"


def test_update_component_info_same_selection_skips_redundant_ops_mode_and_image_refresh() -> None:
    gui = _new_engine()
    state = DummyState(tmcc_id=34, name="Hudson")
    gui._scope_tmcc_ids[CommandScope.ENGINE] = 34
    gui.tmcc_id_text.value = "0034"
    gui.name_text.value = "Hudson"
    gui._active_engine_state = state
    gui._last_displayed_scope = CommandScope.ENGINE
    gui._last_displayed_tmcc_id = 34
    gui._keypad_view.is_entry_mode = False
    gui._state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, include=False: state if (scope, tmcc_id) == (CommandScope.ENGINE, 34) else None
    )

    gui.update_component_info(34)

    assert gui._recent_calls == []
    assert gui._ops_mode_calls == []
    assert gui._image_updates == []


def test_on_scope_rebuilds_options_once_for_scope_transition() -> None:
    gui = _new_engine(CommandScope.ENGINE)
    engine_state = DummyState(tmcc_id=5, name="Hudson", scope=CommandScope.ENGINE)
    train_state = DummyTrainState(tmcc_id=9, linked_ids=[5], name="Empire")
    gui._recents_queue[CommandScope.ENGINE] = UniqueDeque([engine_state])
    gui._recents_queue[CommandScope.TRAIN] = UniqueDeque([train_state])
    gui._state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, include=False: {
            (CommandScope.ENGINE, 5): engine_state,
            (CommandScope.TRAIN, 9): train_state,
        }.get((scope, tmcc_id))
    )
    gui._scope_tmcc_ids[CommandScope.ENGINE] = 5
    gui._scope_tmcc_ids[CommandScope.TRAIN] = 0
    gui.monitor_state = lambda: None

    gui.on_scope(CommandScope.TRAIN)

    assert gui._rebuild_options_calls == 1
