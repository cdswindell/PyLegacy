from __future__ import annotations

from collections import deque
from threading import RLock
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.engine_gui as mod
from src.pytrain.gui.controller.configured_accessory_adapter_provider import ConfiguredAccessoryAdapterProvider
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.utils.unique_deque import UniqueDeque


class DummyAdapter:
    def __init__(self, name: str = "Configured Accessory"):
        self.overlay = None
        self.activations: list[int] = []
        self.name = name

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
    def __init__(self, instance_id: str, *tmcc_ids: int) -> None:
        self.instance_id = instance_id
        self.tmcc_ids = tuple(tmcc_ids)
        self.tmcc_id = tmcc_ids[0] if tmcc_ids else None


class DummyConfiguredSet:
    def __init__(self, *accessories: str | tuple) -> None:
        self.path = "accessory_config.json"
        self._accessories = []
        for acc in accessories:
            if isinstance(acc, tuple):
                instance_id, *tmcc_ids = acc
                self._accessories.append(DummyConfiguredAccessory(instance_id, *tmcc_ids))
            else:
                self._accessories.append(DummyConfiguredAccessory(acc))

    def configured_all(self) -> list[DummyConfiguredAccessory]:
        return list(self._accessories)


class DummyRecentState:
    def __init__(self, tmcc_id: int, road_name: str) -> None:
        self.tmcc_id = tmcc_id
        self.road_name = road_name
        self.road_number = ""


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
        self.reset_calls: list[CommandScope | None] = []

    def reset_configured_accessory_cache(self, *, scope: CommandScope | None = None) -> None:
        self.reset_calls.append(scope)


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
        is_deleted: bool = False,
    ) -> None:
        self.is_sensor_track = is_sensor_track
        self.is_bpc2 = is_bpc2
        self.is_asc2 = is_asc2
        self.is_amc2 = is_amc2
        self.is_deleted = is_deleted


def _new_engine() -> mod.EngineGui:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._cv = RLock()
    gui._caap = DummyProvider({})
    gui._acc_tmcc_to_adapter = {}
    gui._accessory_view = {}
    gui._amc2_ops_panel = None
    # What __init__ would have set, as _amc2_ops_panel above already is. Both are read rather
    # than merely written now: on_new_accessory compares the pair it holds against the id being
    # reported to decide whether the Sequence cursor is this track's or a previous one's.
    gui._sensor_track_selected = None
    gui._sensor_track_undo = None
    return gui


# The __new__ shell is deliberately built out of EngineGui's own private attributes: the methods
# under test read and write them, so a public stand-in would not exercise the same code.
# noinspection PyProtectedMember
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
    gui.title = "Engine GUI"
    gui._separator = "---"
    gui._options_to_state = {}
    gui._recents_queue = {}
    gui._train_linked_queue = UniqueDeque()
    return gui


def test_configured_accessory_providers_are_isolated_per_engine_gui() -> None:
    left_host = object()
    right_host = object()
    left = ConfiguredAccessoryAdapterProvider(DummyConfiguredSet(("station", 12)), left_host)
    right = ConfiguredAccessoryAdapterProvider(DummyConfiguredSet(("station", 12)), right_host)

    left_adapter = left.get("station")
    right_adapter = right.get("station")

    assert left is not right
    assert left_adapter is not right_adapter
    assert left_adapter.host is left_host
    assert right_adapter.host is right_host


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
    gui.update_ac_status = lambda st: seen.append(st)
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
    gui._amc2_ops_panel = SimpleNamespace(update_from_state=lambda st: seen.append(st))
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

    assert catalog_panel.reset_calls == [CommandScope.ACC]


def test_reload_configured_accessories_removes_only_deleted_configured_accessory_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gui = _new_reload_engine()
    adapter = DummyAdapter("Keep Reloaded")
    gui._caa = DummyConfiguredSet(("keep_old", 12), ("remove_old", 13))
    gui._caap = DummyReloadProvider({12: [adapter]})
    gui._recents_queue[CommandScope.ACC] = UniqueDeque(
        [
            DummyRecentState(12, "Keep Old"),
            DummyRecentState(13, "Remove Old"),
            DummyRecentState(99, "Raw Accessory"),
        ]
    )
    new_config = DummyConfiguredSet(("keep_new", 12))

    monkeypatch.setattr(
        mod.ConfiguredAccessorySet,
        "from_file",
        classmethod(lambda cls, path, verify=True: new_config),
        raising=True,
    )

    assert gui.reload_configured_accessories() is True

    assert [state.tmcc_id for state in gui._recents_queue[CommandScope.ACC]] == [12, 99]
    assert gui.get_options() == [
        "Engine GUI",
        "12: Keep Reloaded",
        "99: Raw Accessory",
        "---",
        mod.ADMIN_TITLE,
    ]
    assert adapter.activations == [12]


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

    # verify keeps its name because from_file is called as from_file(path, verify=True); the stand-in
    # has to accept that keyword even though it raises before reading it.
    # noinspection PyUnusedLocal,unused-parameter
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


def test_accessory_config_signature_tracks_file_changes(tmp_path) -> None:
    config_path = tmp_path / "accessory_config.json"
    missing_signature = mod.EngineGui._accessory_config_signature(config_path)

    config_path.write_text('{"accessories": []}', encoding="utf-8")
    existing_signature = mod.EngineGui._accessory_config_signature(config_path)

    config_path.write_text('{"accessories": [], "changed": true}', encoding="utf-8")
    changed_signature = mod.EngineGui._accessory_config_signature(config_path)

    assert missing_signature[1:] == (False, None, None)
    assert existing_signature[1] is True
    assert changed_signature != existing_signature


def test_accessory_config_change_debounces_and_schedules_apply(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_path = tmp_path / "accessory_config.json"
    config_path.write_text('{"accessories": []}', encoding="utf-8")
    gui = _new_reload_engine()
    gui._accessory_config_last_signature = mod.EngineGui._accessory_config_signature(config_path)
    gui._accessory_config_pending_signature = None
    gui._accessory_config_pending_since = None
    gui._accessory_config_debounce = 0
    new_config = DummyConfiguredSet("new_a")
    new_config.path = config_path

    monkeypatch.setattr(
        mod.ConfiguredAccessorySet,
        "resolve_config_path",
        staticmethod(lambda _path: config_path),
        raising=True,
    )
    gui._load_configured_accessories = lambda: new_config

    config_path.write_text('{"accessories": [], "changed": true}', encoding="utf-8")
    gui._check_accessory_config_change()
    assert gui.app.tk.after_calls == []

    gui._check_accessory_config_change()
    assert len(gui.app.tk.after_calls) == 1

    _, callback = gui.app.tk.after_calls[0]
    callback()

    assert gui._caa is new_config
    assert gui._accessory_config_last_signature == mod.EngineGui._accessory_config_signature(new_config.path)


def test_accessory_config_change_load_failure_keeps_current_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    config_path = tmp_path / "accessory_config.json"
    config_path.write_text('{"accessories": []}', encoding="utf-8")
    gui = _new_reload_engine()
    original_config = gui._caa
    gui._accessory_config_last_signature = mod.EngineGui._accessory_config_signature(config_path)
    gui._accessory_config_pending_signature = None
    gui._accessory_config_pending_since = None
    gui._accessory_config_debounce = 0

    monkeypatch.setattr(
        mod.ConfiguredAccessorySet,
        "resolve_config_path",
        staticmethod(lambda _path: config_path),
        raising=True,
    )
    gui._load_configured_accessories = lambda: None

    config_path.write_text("{bad json", encoding="utf-8")
    gui._check_accessory_config_change()
    gui._check_accessory_config_change()

    assert gui._caa is original_config
    assert gui.app.tk.after_calls == []


def _acc_engine(kind: str | None, *, scope: CommandScope = CommandScope.ACC, tmcc_id: int = 19) -> mod.EngineGui:
    gui = _new_engine()
    gui.scope = scope
    gui._scope_tmcc_ids = {scope: tmcc_id}
    gui._keypad_view = SimpleNamespace(accessory_panel_kind=kind)
    return gui


@pytest.mark.parametrize(
    "kind, expected",
    [
        ("generic", ("acc_generic", "acc")),
        ("bpc2", ("acc_bpc2", "acc")),
        ("asc2", ("acc_asc2", "acc_bpc2", "acc")),
        ("sensor_track", ("acc_sensor_track", "acc")),
    ],
)
def test_input_contexts_follow_the_accessory_panel_displayed(kind: str, expected: tuple[str, ...]) -> None:
    assert _acc_engine(kind).input_contexts == expected


@pytest.mark.parametrize("kind", ["amc2", None])
def test_input_contexts_are_empty_where_no_accessory_context_is_defined(kind: str | None) -> None:
    # AMC2 has no gamepad bindings yet, and a chain of nothing but the base would claim every
    # control and send none of them.
    assert _acc_engine(kind).input_contexts == ()


def test_input_contexts_are_empty_with_nothing_selected() -> None:
    assert _acc_engine("generic", tmcc_id=0).input_contexts == ()


def test_input_contexts_report_bpc2_for_a_train_scope_power_district() -> None:
    # is_accessory_or_bpc2, not scope == ACC: a power district reached under TRAIN scope shows
    # the BPC2 panel, so it is bound like one.
    gui = _acc_engine("bpc2", scope=CommandScope.TRAIN, tmcc_id=4)
    assert gui.input_contexts == ("acc_bpc2", "acc")


def test_input_contexts_do_not_consult_the_panel_when_a_switch_or_route_is_shown() -> None:
    gui = _acc_engine("generic", scope=CommandScope.SWITCH, tmcc_id=7)
    assert gui.input_contexts == ("switch",)

    gui = _acc_engine("generic", scope=CommandScope.ROUTE, tmcc_id=7)
    assert gui.input_contexts == ("route",)


# _popup and _keypad_view are EngineGui's own attributes, so the fakes standing in for them keep
# those names; the two counters follow the same style and are read back to pin what each toggle did.
# noinspection PyProtectedMember
def _toggle_engine() -> mod.EngineGui:
    """An EngineGui shell for the two panel-toggle handlers, whose whole job is to move the
    keypad's override and re-enter ops mode without disturbing the selection."""
    gui = _new_engine()
    gui.scope = CommandScope.ACC
    gui._scope_tmcc_ids = {CommandScope.ACC: 19}
    gui._popup_closed = 0
    gui._popup = SimpleNamespace(close=lambda: setattr(gui, "_popup_closed", gui._popup_closed + 1))
    ops_mode_calls: list[bool] = []
    gui._ops_mode_calls = ops_mode_calls
    gui.ops_mode = lambda update_info=True, state=None: gui._ops_mode_calls.append(update_info)

    keypad = SimpleNamespace(_forced=None)
    keypad.set_panel_kind_override = lambda k: setattr(keypad, "_forced", k)
    gui._keypad_view = keypad
    return gui


def test_show_generic_acc_panel_forces_the_generic_panel_and_re_enters_ops_mode() -> None:
    gui = _toggle_engine()

    gui.on_show_generic_acc_panel()

    assert gui._keypad_view._forced == "generic"
    assert gui._ops_mode_calls == [False], "the selection has not changed, so the info is not rebuilt"
    assert gui._popup_closed == 1


def test_show_native_acc_panel_drops_the_override_and_re_enters_ops_mode() -> None:
    gui = _toggle_engine()
    gui.on_show_generic_acc_panel()

    gui.on_show_native_acc_panel()

    assert gui._keypad_view._forced is None
    assert gui._ops_mode_calls == [False, False]
    assert gui._popup_closed == 2


def _ops_mode_engine(
    monkeypatch: pytest.MonkeyPatch,
    *,
    override: str | None,
    tmcc_id: int = 19,
    configured: bool = True,
) -> tuple[mod.EngineGui, list]:
    """An EngineGui wired to drive the *real* ops_mode non-engine branch.

    The keypad fake reports a non-engine panel and carries a settable panel_kind_override, so
    the guard added to ops_mode is exercised end to end rather than stubbed. Returns the gui
    plus a list that records every on_configured_accessory call, so a test can assert whether
    the operating-accessory overlay was (re)opened.
    """
    gui = _new_engine()
    gui.scope = CommandScope.ACC
    gui._scope_tmcc_ids = {CommandScope.ACC: tmcc_id}

    state = DummyAccessoryState(is_asc2=True)
    state.tmcc_id = tmcc_id
    state.scope = CommandScope.ACC
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
    gui._state_store = SimpleNamespace(get_state=lambda scope, tid, include: state if tid == tmcc_id else None)

    if configured:
        adapter = DummyAdapter()
        gui._accessory_view = {tmcc_id: SimpleNamespace()}
        gui._acc_tmcc_to_adapter = {tmcc_id: adapter}

    keypad = SimpleNamespace(
        is_engine_or_train=False,
        panel_kind_override=override,
    )
    keypad.enter_ops_mode_base = lambda: None
    # The parameter keeps its name because ops_mode calls apply_ops_mode_ui_non_engine(state=state).
    # noinspection PyShadowingNames
    keypad.apply_ops_mode_ui_non_engine = lambda state=None: None
    keypad.set_panel_kind_override = lambda k: setattr(keypad, "panel_kind_override", k)
    gui._keypad_view = keypad

    gui._popup = SimpleNamespace(close=lambda: None)

    opened: list = []
    gui.on_configured_accessory = lambda acc: opened.append(acc)
    return gui, opened


def test_ops_mode_with_generic_override_does_not_reopen_configured_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pressing Acc... forces the generic panel; the operating-accessory overlay must not be
    # rebuilt on top of it.
    gui, opened = _ops_mode_engine(monkeypatch, override=mod.PANEL_GENERIC)

    gui.ops_mode(update_info=False)

    assert opened == [], "the configured operating-accessory overlay must stay closed"


def test_ops_mode_without_override_opens_configured_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression guard: selecting a configured operating accessory fresh (no override in force)
    # still opens its operating-accessory control panel.
    gui, opened = _ops_mode_engine(monkeypatch, override=None)

    gui.ops_mode(update_info=False)

    assert len(opened) == 1, "a configured accessory still opens its operating-accessory panel"


def test_native_return_restores_configured_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # After Acc... suppresses the overlay, the device return button clears the override and the
    # next ops_mode restores the operating-accessory control panel.
    gui, opened = _ops_mode_engine(monkeypatch, override=mod.PANEL_GENERIC)

    gui.ops_mode(update_info=False)
    assert opened == []

    gui.on_show_native_acc_panel()

    assert gui._keypad_view.panel_kind_override is None
    assert len(opened) == 1, "returning to the native panel restores the operating-accessory overlay"


def test_ops_mode_generic_override_on_unconfigured_id_leaves_generic_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A generic (non-configured) accessory under the override has nothing to suppress; the
    # generic panel simply shows and no operating-accessory overlay is opened.
    gui, opened = _ops_mode_engine(monkeypatch, override=mod.PANEL_GENERIC, configured=False)

    gui.ops_mode(update_info=False)

    assert opened == []


def test_the_pad_follows_a_forced_generic_panel() -> None:
    # The invariant the whole design rests on: the override lives inside the one property both
    # the drawn keys and the context chain read, so a forced generic screen is bound as one.
    gui = _acc_engine("generic")
    assert gui.input_contexts == ("acc_generic", "acc")


def test_acc_base_context_claims_what_it_does_not_bind() -> None:
    from src.pytrain.gui.controller import accessory_bindings as ab

    spec = ab.DEFAULT_CONTEXTS[ab.ACC_CONTEXT]
    assert spec.claims_unbound is True
    assert dict(spec.bindings) == {}

    resolution = ab.resolve(("acc_generic", "acc"), "bell")
    assert resolution is not None
    assert resolution.context is spec
    assert resolution.claimed_only is True


@pytest.mark.parametrize(
    "value, expected",
    [
        (
            3,
            [("RELATIVE_SPEED", 3)],
        ),
        (
            -3,
            [("RELATIVE_SPEED", -3)],
        ),
        # Clamped to the range the on-screen slider offers, so the pad cannot ask for a step
        # the slider has no notch for.
        (
            9,
            [("RELATIVE_SPEED", 5)],
        ),
        (
            -9,
            [("RELATIVE_SPEED", -5)],
        ),
        # A step of zero is no request at all.
        (0, []),
        ("fast", []),
    ],
)
def test_on_acc_speed_command_sends_a_clamped_relative_step(value, expected) -> None:
    gui = _new_engine()
    sent: list[tuple[str, int | None]] = []
    gui.on_acc_command = lambda target, data=None: sent.append((target, data))

    gui.on_acc_speed_command(value)

    assert sent == expected


@pytest.mark.parametrize("on", [True, False])
def test_on_lcs_command_sends_the_same_thing_the_on_and_off_keys_do(
    monkeypatch: pytest.MonkeyPatch,
    on: bool,
) -> None:
    sent: list[tuple[str, object]] = []
    monkeypatch.setattr(mod, "send_lcs_on_command", lambda st: sent.append(("on", st)), raising=True)
    monkeypatch.setattr(mod, "send_lcs_off_command", lambda st: sent.append(("off", st)), raising=True)

    gui = _acc_engine("bpc2")
    state = object()
    gui._state_store = SimpleNamespace(get_state=lambda _scope, _tmcc_id, _create: state)

    gui.on_lcs_command(on)

    assert sent == [("on" if on else "off", state)]


def test_on_lcs_command_sends_nothing_with_nothing_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(mod, "send_lcs_on_command", lambda _state: sent.append("on"), raising=True)

    gui = _acc_engine("bpc2", tmcc_id=0)
    gui._state_store = SimpleNamespace(get_state=lambda _scope, _tmcc_id, _create: None)

    gui.on_lcs_command(True)

    assert sent == []

    gui = _acc_engine("bpc2")
    gui._state_store = SimpleNamespace(get_state=lambda _scope, _tmcc_id, _create: None)

    gui.on_lcs_command(True)

    assert sent == [], "and nothing is sent for a port with no state either"


@pytest.mark.parametrize("pressed", [True, False])
def test_on_asc2_momentary_delegates_to_the_keypad(pressed: bool) -> None:
    # Both phases go to the same place the on-screen key sends from, so the pad and the touch
    # screen cannot send different requests.
    gui = _acc_engine("asc2")
    calls: list[bool] = []
    gui._keypad_view = SimpleNamespace(asc2_control=calls.append)

    gui.on_asc2_momentary(pressed)

    assert calls == [pressed]


class _SensorTrackView:
    """The keypad's Sensor Track surface, with the dot and the cursor as two separate things.

    dot is what the track is programmed with -- the radio selection -- and bar is where the pad
    is pointing. Modeling them apart is the whole of A-8: a double that kept one highlight
    would let stepping pass here and still announce a choice on the panel.

    clamped makes every step answer None, as KeypadView.step_sensor_track_sequence does at
    either end of the list.
    """

    def __init__(self, dot: int | None, *, clamped: bool = False) -> None:
        self.accessory_panel_kind = "sensor_track"
        self.dot = dot
        self.bar: int | None = None
        self.clamped = clamped
        self.sent: list[tuple[int, int]] = []
        self.steps: list[int] = []

    @property
    def sensor_track_sequence(self) -> int | None:
        return self.dot

    @property
    def sensor_track_cursor(self) -> int | None:
        # Falls back to the dot, as the pane's own reader does: a panel nobody has stepped yet
        # points at the option the track holds.
        return self.bar if self.bar is not None else self.dot

    def set_sensor_track_cursor(self, sequence: int | None) -> bool:
        self.bar = sequence
        return True

    def set_sensor_track_sequence(self, sequence: int) -> bool:
        # The dot brings the cursor with it: after a select or a revert the pad is pointing at
        # exactly what the track now holds.
        self.dot = sequence
        self.bar = sequence
        return True

    def step_sensor_track_sequence(self, delta: int) -> int | None:
        self.steps.append(delta)
        if self.clamped:
            return None
        current = self.sensor_track_cursor
        self.bar = 0 if current is None else current + delta
        return self.bar

    def send_sensor_track_sequence(self, tmcc_id: int, sequence: int) -> None:
        self.sent.append((tmcc_id, sequence))


def _sensor_track_engine(highlight: int | None = None, *, tmcc_id: int = 19, clamped: bool = False) -> mod.EngineGui:
    """A Sensor Track pane over the view double above.

    highlight is the Sequence option the radio dot starts on -- None for a fresh track with no
    IrdaState yet, which is nothing selected and nothing pointed at.
    """
    gui = _acc_engine("sensor_track", tmcc_id=tmcc_id)
    view = _SensorTrackView(highlight, clamped=clamped)
    gui._keypad_view = view
    gui.sensor_track_view = view
    gui.sensor_track_sent = view.sent
    gui.sensor_track_steps = view.steps
    return gui


@pytest.mark.parametrize("delta", [-1, 1])
def test_on_sensor_track_step_moves_the_cursor_and_writes_nothing(delta: int) -> None:
    # A-7: the two acts are separate. Stepping is the pad moving its eye down the list, and
    # nothing the track is told about, so crossing the ten options costs no commands at all.
    # A-8: and nothing the *panel* is told about either -- the dot stays on what the track holds.
    gui = _sensor_track_engine(5)

    moved = gui.on_sensor_track_step(delta)

    assert moved is True
    assert gui.sensor_track_steps == [delta]
    assert gui.sensor_track_view.bar == 5 + delta
    assert gui.sensor_track_view.dot == 5, "the radio dot did not move"
    assert gui.sensor_track_sent == [], "the step itself writes nothing"


def test_on_sensor_track_step_answers_false_where_the_highlight_did_not_move() -> None:
    # A press clamped at either end, which a caller may want to tell from one that moved.
    gui = _sensor_track_engine(0, clamped=True)

    assert gui.on_sensor_track_step(-1) is False
    assert gui.sensor_track_sent == []


def test_on_sensor_track_select_writes_the_highlighted_option_at_this_pane_s_id() -> None:
    gui = _sensor_track_engine(3, tmcc_id=23)

    gui.on_sensor_track_select()

    assert gui.sensor_track_sent == [(23, 3)]
    assert gui._sensor_track_selected == (23, 3)
    assert gui._sensor_track_undo is None, "there was nothing selected before to go back to"


def test_a_select_writes_the_option_under_the_cursor_and_moves_the_dot_onto_it() -> None:
    # A-8's other half. The pad stepped away from what the track holds, so the option written is
    # the one under the cursor -- and afterwards the two coincide, which is what "done" looks
    # like on the panel.
    gui = _sensor_track_engine(1, tmcc_id=23)
    gui.on_sensor_track_step(5)

    assert gui.sensor_track_view.dot == 1, "still showing what the track holds"

    gui.on_sensor_track_select()

    assert gui.sensor_track_sent == [(23, 6)]
    assert gui.sensor_track_view.dot == 6
    assert gui.sensor_track_view.bar == 6, "and nothing is left pending"


def test_on_sensor_track_select_with_nothing_highlighted_writes_nothing() -> None:
    # A fresh track with no IrdaState shows nothing selected, and "the option showing" is then
    # not a thing there is one of. Writing index 0 for it would be the pad choosing.
    gui = _sensor_track_engine(None)

    gui.on_sensor_track_select()

    assert gui.sensor_track_sent == []
    assert gui._sensor_track_selected is None


def test_a_second_select_records_the_option_it_displaced() -> None:
    # The undo point, which is the whole of what revert works from: the option that was
    # selected *before* this write, so a select the operator regrets can be taken back.
    gui = _sensor_track_engine(2, tmcc_id=23)
    gui.on_sensor_track_select()
    gui.on_sensor_track_step(4)

    gui.on_sensor_track_select()

    assert gui.sensor_track_sent == [(23, 2), (23, 6)]
    assert gui._sensor_track_undo == (23, 2)


def test_selecting_the_option_already_showing_keeps_the_undo_point() -> None:
    # Re-selecting what is already selected is a confirmation rather than a change, and taking
    # it as one would spend the undo point on nothing -- leaving the operator's real previous
    # choice unreachable after a stray press of the select key.
    gui = _sensor_track_engine(2, tmcc_id=23)
    gui.on_sensor_track_select()
    gui.on_sensor_track_step(4)
    gui.on_sensor_track_select()

    gui.on_sensor_track_select()

    assert gui.sensor_track_sent == [(23, 2), (23, 6), (23, 6)], "the write is still made"
    assert gui._sensor_track_undo == (23, 2), "and the option to go back to is still the old one"


def test_on_sensor_track_revert_puts_back_the_option_the_last_select_replaced() -> None:
    gui = _sensor_track_engine(2, tmcc_id=23)
    gui.on_sensor_track_select()
    gui.on_sensor_track_step(4)
    gui.on_sensor_track_select()

    gui.on_sensor_track_revert()

    assert gui.sensor_track_sent == [(23, 2), (23, 6), (23, 2)], "the displaced option went back"
    assert gui.sensor_track_view.dot == 2, "and the dot followed it"
    assert gui.sensor_track_view.bar == 2, "and so did the cursor, leaving nothing pending"
    assert gui._sensor_track_selected == (23, 2)


def test_a_revert_is_one_shot_rather_than_a_way_of_flipping_between_two_options() -> None:
    # An undo, not a toggle: spent by the revert that uses it. Otherwise a second press would
    # re-apply the very write the first one was asked to take back.
    gui = _sensor_track_engine(2, tmcc_id=23)
    gui.on_sensor_track_select()
    gui.on_sensor_track_step(4)
    gui.on_sensor_track_select()
    gui.on_sensor_track_revert()

    gui.on_sensor_track_revert()

    assert gui.sensor_track_sent == [(23, 2), (23, 6), (23, 2)], "the second revert wrote nothing"
    assert gui._sensor_track_undo is None


def test_a_revert_with_nothing_selected_yet_abandons_the_stepping_and_sends_nothing() -> None:
    # What makes revert useful before the first select: it takes the highlight back to the
    # option the track actually holds. No write, the track already being there -- one would be
    # a command asked for by nobody.
    gui = _sensor_track_engine(4, tmcc_id=23)
    gui._sensor_track_selected = (23, 4)
    gui.on_sensor_track_step(3)

    assert gui.sensor_track_view.bar == 7

    gui.on_sensor_track_revert()

    assert gui.sensor_track_view.bar == 4, "back where the track is set"
    assert gui.sensor_track_view.dot == 4, "which the dot never left"
    assert gui.sensor_track_sent == []


def test_a_revert_on_a_pane_re_scoped_to_another_sensor_track_writes_nothing() -> None:
    # The reason both records carry the id as well as the value. The catalog can re-point the
    # pane between the select and the revert, and an id-blind undo would then write the option
    # chosen for one Sensor Track to a different one.
    gui = _sensor_track_engine(2, tmcc_id=19)
    gui.on_sensor_track_select()
    gui.on_sensor_track_step(4)
    gui.on_sensor_track_select()

    gui._scope_tmcc_ids[CommandScope.ACC] = 42

    gui.on_sensor_track_revert()

    assert gui.sensor_track_sent == [(19, 2), (19, 6)], "nothing was written at the new id"


def test_on_new_accessory_seeds_what_a_revert_falls_back_to() -> None:
    # The one place the panel learns what the track actually holds, so the one place the pad's
    # notion of "currently selected" can start out right rather than being guessed.
    gui = _sensor_track_engine(None, tmcc_id=22)
    gui._scope_tmcc_ids = {CommandScope.ACC: 22}
    gui.sensor_track_buttons = SimpleNamespace(value=None)
    gui._sensor_track_undo = (22, 1)
    monkey = SimpleNamespace(sequence=SimpleNamespace(value=3))
    gui._state_store = SimpleNamespace(get_state=lambda scope, tmcc_id, include: monkey)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
        patch.setattr(mod, "IrdaState", type(monkey), raising=True)
        gui.on_new_accessory(DummyAccessoryState(is_sensor_track=True))

    assert gui._sensor_track_selected == (22, 3)
    assert gui._sensor_track_undo is None, "and an undo point from before the report is stale"
    assert gui.sensor_track_view.bar == 3, "and the cursor starts on the option the track holds"


def _report_sensor_track(gui: mod.EngineGui, tmcc_id: int, sequence: int) -> None:
    """Deliver an IrdaState for tmcc_id, as an incoming status report does."""
    gui._scope_tmcc_ids = {CommandScope.ACC: tmcc_id}
    gui.sensor_track_buttons = SimpleNamespace(value=None)
    report = SimpleNamespace(sequence=SimpleNamespace(value=sequence))
    gui._state_store = SimpleNamespace(get_state=lambda _scope, _tmcc_id, _create: report)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
        patch.setattr(mod, "IrdaState", type(report), raising=True)
        gui.on_new_accessory(DummyAccessoryState(is_sensor_track=True))


def test_a_report_for_the_same_track_moves_the_dot_and_leaves_a_step_in_progress_alone() -> None:
    # KD-15, and the bug a naive re-seed would ship: on_new_accessory runs on every accessory
    # state update, so re-seeding unconditionally would snap the cursor back the moment the
    # track reported itself -- under the operator's thumb, mid-step.
    gui = _sensor_track_engine(2, tmcc_id=22)
    gui._sensor_track_selected = (22, 2)
    gui.on_sensor_track_step(5)

    _report_sensor_track(gui, 22, 2)

    assert gui.sensor_track_view.bar == 7, "the cursor is where the operator left it"
    assert gui.sensor_track_buttons.value == 2, "and the dot is what the track reported"


def test_a_report_for_a_different_track_re_seeds_the_cursor() -> None:
    # A cursor left somewhere by one Sensor Track must never be presented as another's position.
    gui = _sensor_track_engine(2, tmcc_id=22)
    gui._sensor_track_selected = (22, 2)
    gui.on_sensor_track_step(5)

    _report_sensor_track(gui, 41, 8)

    assert gui._sensor_track_selected == (41, 8)
    assert gui.sensor_track_view.bar == 8


def test_a_track_with_no_report_leaves_nothing_to_point_at() -> None:
    # Nothing is known about the track, so no row is the pad's position either -- and the first
    # press then lands on "No Action" rather than one option away from a stale cursor.
    gui = _sensor_track_engine(3, tmcc_id=22)
    gui._sensor_track_selected = (22, 3)
    gui.on_sensor_track_step(4)
    gui._scope_tmcc_ids = {CommandScope.ACC: 22}
    gui.sensor_track_buttons = SimpleNamespace(value=1)
    gui._state_store = SimpleNamespace(get_state=lambda _scope, _tmcc_id, _create: None)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
        patch.setattr(mod, "IrdaState", SimpleNamespace, raising=True)
        gui.on_new_accessory(DummyAccessoryState(is_sensor_track=True))

    assert gui._sensor_track_selected is None
    assert gui.sensor_track_view.bar is None
    assert gui.sensor_track_buttons.value is None
