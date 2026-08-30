#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Creation of Accessory and Switch records from the Enter key.

Headless throughout: ``EngineGui`` is exercised through an ``__new__`` shell carrying only the
attributes the creation path touches, and ``KeypadView`` against a ``SimpleNamespace`` host, in
the style of ``tests/gui/test_engine_gui_transitions.py``.
"""

import threading
from types import SimpleNamespace

import pytest

from pytrain.gui.controller import engine_gui as gui_mod
from pytrain.gui.controller import keypad_view as mod
from pytrain.gui.controller.engine_gui_conf import CREATABLE_SCOPES, ENTER_KEY
from pytrain.protocol.constants import CommandScope

NON_CREATABLE = [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ROUTE]


class DummyState:
    """Just enough of a ComponentState for the provisional bookkeeping."""

    def __init__(
        self,
        scope: CommandScope = CommandScope.ACC,
        tmcc_id: int = 42,
        is_comp_data_empty: bool = True,
    ) -> None:
        self.scope = scope
        self.tmcc_id = tmcc_id
        self.is_deleted = False
        # True until the Base 3 answers: the marker that says a record is still provisional.
        self.is_comp_data_empty = is_comp_data_empty
        self.initialized: list[tuple] = []

    def initialize(self, scope: CommandScope = None, tmcc_id: int = None) -> None:
        self.scope = scope
        self.tmcc_id = tmcc_id
        self.initialized.append((scope, tmcc_id))


class DummyStore:
    def __init__(self, states: dict[tuple[CommandScope, int], DummyState] = None) -> None:
        self.states = dict(states or {})
        self.lookups: list[tuple] = []

    def get_state(self, scope: CommandScope, tmcc_id: int, create: bool = True):
        self.lookups.append((scope, tmcc_id, create))
        return self.states.get((scope, tmcc_id), None)


def _gui(scope: CommandScope = CommandScope.ACC, store: DummyStore = None) -> gui_mod.EngineGui:
    gui = gui_mod.EngineGui.__new__(gui_mod.EngineGui)
    gui.scope = scope
    gui._cv = threading.RLock()
    gui._scope_tmcc_ids = {s: 0 for s in CommandScope}
    gui._provisional = set()
    gui._state_store = store if store is not None else DummyStore()
    return gui


# ---------------------------------------------------------------------------
# EngineGui.create_provisional_component / is_provisional
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scope", sorted(CREATABLE_SCOPES, key=lambda s: s.name))
def test_creating_a_component_initializes_it_and_selects_it(scope, monkeypatch) -> None:
    created = DummyState(scope, 0)
    monkeypatch.setattr(
        gui_mod.ComponentStateStore,
        "get_state",
        classmethod(lambda _cls, _scope, _tmcc_id, create=True: created),
    )
    gui = _gui(scope)

    state = gui.create_provisional_component(scope, 42)

    assert state is created
    assert created.initialized == [(scope, 42)], "comp_data is initialized, exactly as the Set key does"
    assert gui.is_provisional(scope, 42) is True
    assert gui._scope_tmcc_ids[scope] == 42


def test_creating_over_an_existing_state_reuses_it_without_reinitializing(monkeypatch) -> None:
    existing = DummyState(CommandScope.ACC, 42)
    monkeypatch.setattr(
        gui_mod.ComponentStateStore,
        "get_state",
        classmethod(lambda *_a, **_k: pytest.fail("the store must not be asked to create an existing state")),
    )
    gui = _gui(CommandScope.ACC, DummyStore({(CommandScope.ACC, 42): existing}))

    state = gui.create_provisional_component(CommandScope.ACC, 42)

    assert state is existing
    assert existing.initialized == []
    assert gui.is_provisional(CommandScope.ACC, 42) is True


def test_a_component_is_not_provisional_until_it_is_created() -> None:
    gui = _gui()

    assert gui.is_provisional(CommandScope.ACC, 42) is False
    assert gui.is_provisional(CommandScope.SWITCH, 42) is False


def test_the_provisional_flag_is_per_scope_and_per_id(monkeypatch) -> None:
    monkeypatch.setattr(
        gui_mod.ComponentStateStore,
        "get_state",
        classmethod(lambda _cls, scope, tmcc_id, create=True: DummyState(scope, 0)),
    )
    gui = _gui(CommandScope.ACC)

    gui.create_provisional_component(CommandScope.ACC, 42)

    assert gui.is_provisional(CommandScope.ACC, 42) is True
    assert gui.is_provisional(CommandScope.SWITCH, 42) is False
    assert gui.is_provisional(CommandScope.ACC, 43) is False


# ---------------------------------------------------------------------------
# Deferred promotion: nothing reaches recents while provisional
# ---------------------------------------------------------------------------


def test_a_provisional_selection_stays_out_of_recents() -> None:
    gui = _gui(CommandScope.ACC)
    gui._provisional.add((CommandScope.ACC, 42))
    recents: list[tuple] = []
    gui.make_recent = lambda *args, **kwargs: recents.append(args)
    gui.ops_mode = lambda **_kwargs: None

    gui._update_recent_selection(42, DummyState(CommandScope.ACC, 42), True, True)

    assert recents == [], "a mistyped or unnamed id leaves no trace in recents"
    assert gui._scope_tmcc_ids[CommandScope.ACC] == 42, "but it is still the current selection"


def test_a_defined_selection_still_reaches_recents() -> None:
    gui = _gui(CommandScope.ACC)
    recents: list[tuple] = []
    gui.make_recent = lambda *args, **kwargs: recents.append(args)
    gui.ops_mode = lambda **_kwargs: None

    gui._update_recent_selection(42, DummyState(CommandScope.ACC, 42), True, True)

    assert len(recents) == 1
    assert recents[0][:2] == (CommandScope.ACC, 42)


def test_a_provisional_selection_still_enters_ops_mode_when_it_is_not_there_yet() -> None:
    gui = _gui(CommandScope.SWITCH)
    gui._provisional.add((CommandScope.SWITCH, 7))
    gui.make_recent = lambda *_a, **_k: pytest.fail("provisional states must not be made recent")
    calls: list[dict] = []
    gui.ops_mode = lambda **kwargs: calls.append(kwargs)

    gui._update_recent_selection(7, DummyState(CommandScope.SWITCH, 7), False, True)

    assert calls == [{"update_info": False}]


def test_deleting_a_state_drops_its_provisional_entry() -> None:
    gui = _gui(CommandScope.ACC)
    gui._provisional.add((CommandScope.ACC, 42))
    state = DummyState(CommandScope.ACC, 42)
    gui._scope_watchers = {}
    gui._recents_queue = {}
    gui._train_linked_queue = []
    gui._active_engine_state = None
    gui._active_train_state = None
    gui._catalog_panel = None
    gui._request_options_rebuild = lambda: None
    gui.display_most_recent = lambda _scope: None
    gui.update_component_info = lambda *_a, **_k: None
    gui.tmcc_id_text = SimpleNamespace(value="42")
    gui._keypad_view = SimpleNamespace(scope_keypad=lambda *_a, **_k: None)

    gui._rebuild_state_caches(state)

    assert gui.is_provisional(CommandScope.ACC, 42) is False


# ---------------------------------------------------------------------------
# KeypadView._can_create
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scope", sorted(CREATABLE_SCOPES, key=lambda s: s.name))
@pytest.mark.parametrize("tmcc_id", [2, 3, 50, 97, 98])
def test_ids_in_range_are_creatable(scope, tmcc_id) -> None:
    assert mod.KeypadView._can_create(scope, tmcc_id) is True


@pytest.mark.parametrize("scope", sorted(CREATABLE_SCOPES, key=lambda s: s.name))
@pytest.mark.parametrize("tmcc_id", [0, 1, 99, 100, 4321])
def test_ids_out_of_range_are_not_creatable(scope, tmcc_id) -> None:
    assert mod.KeypadView._can_create(scope, tmcc_id) is False


@pytest.mark.parametrize("scope", NON_CREATABLE)
def test_non_creatable_scopes_are_rejected_at_every_id(scope) -> None:
    assert all(mod.KeypadView._can_create(scope, tmcc_id) is False for tmcc_id in (2, 42, 98))


def test_engines_are_deliberately_out_of_scope_for_now() -> None:
    assert CommandScope.ENGINE not in CREATABLE_SCOPES
    assert CREATABLE_SCOPES == frozenset({CommandScope.ACC, CommandScope.SWITCH})


# ---------------------------------------------------------------------------
# The Enter key
# ---------------------------------------------------------------------------


def _host(scope: CommandScope, tmcc_id: str) -> SimpleNamespace:
    host = SimpleNamespace()
    host.scope = scope
    host.calls: list[tuple] = []
    host.tmcc_id_text = SimpleNamespace(value=tmcc_id)
    host.make_recent = lambda s, t, state=None: host.calls.append(("make_recent", s, t)) or False
    host.ops_mode = lambda update_info=False, state=None: host.calls.append(("ops_mode", update_info, state))
    host.create_provisional_component = lambda s, t: host.calls.append(("create", s, t)) or DummyState(s, t)
    host.update_component_info = lambda *_a, **_k: None
    host.on_info = lambda **_k: host.calls.append(("on_info",))
    host.do_command = lambda key: host.calls.append(("do_command", key))
    return host


def _view(host: SimpleNamespace) -> mod.KeypadView:
    view = mod.KeypadView(host)
    entered: list[dict] = []
    view.entry_mode = lambda **kwargs: entered.append(kwargs)
    view.entered = entered
    return view


@pytest.mark.parametrize("scope", sorted(CREATABLE_SCOPES, key=lambda s: s.name))
def test_enter_on_an_undefined_creatable_id_creates_and_operates(scope) -> None:
    host = _host(scope, "42")
    view = _view(host)

    view.on_keypress(ENTER_KEY)

    assert ("create", scope, 42) in host.calls
    ops = [call for call in host.calls if call[0] == "ops_mode"]
    assert len(ops) == 1
    assert ops[0][1] is True, "ops mode paints the new component's info"
    assert isinstance(ops[0][2], DummyState)
    assert view.entered == [], "and it does not fall back to the entry keypad"
    assert view.reset_on_keystroke is False


@pytest.mark.parametrize("scope", NON_CREATABLE)
def test_enter_on_an_undefined_non_creatable_id_still_returns_to_entry_mode(scope) -> None:
    host = _host(scope, "0042")
    view = _view(host)

    view.on_keypress(ENTER_KEY)

    assert not any(call[0] == "create" for call in host.calls)
    assert not any(call[0] == "ops_mode" for call in host.calls)
    assert view.entered == [{"clear_info": False}]


@pytest.mark.parametrize("scope", sorted(CREATABLE_SCOPES, key=lambda s: s.name))
@pytest.mark.parametrize("tmcc_id", ["00", "01", "99"])
def test_enter_on_an_out_of_range_id_still_returns_to_entry_mode(scope, tmcc_id) -> None:
    host = _host(scope, tmcc_id)
    view = _view(host)

    view.on_keypress(ENTER_KEY)

    assert not any(call[0] == "create" for call in host.calls)
    assert view.entered == [{"clear_info": False}]


@pytest.mark.parametrize("scope", sorted(CREATABLE_SCOPES, key=lambda s: s.name))
def test_enter_on_a_defined_id_takes_the_unchanged_fast_path(scope) -> None:
    host = _host(scope, "42")
    host.make_recent = lambda s, t, state=None: host.calls.append(("make_recent", s, t)) or True
    view = _view(host)

    view.on_keypress(ENTER_KEY)

    assert host.calls == [("make_recent", scope, 42), ("ops_mode", False, None)]
    assert view.entered == []


def test_the_set_key_create_path_is_unchanged(monkeypatch) -> None:
    created = DummyState(CommandScope.ACC, 0)
    calls: list[tuple] = []

    def get_state(_cls, scope, tmcc_id, create=True):
        calls.append((scope, tmcc_id, create))
        return created if create else None

    monkeypatch.setattr(mod.ComponentStateStore, "get_state", classmethod(get_state))
    host = _host(CommandScope.ACC, "42")
    host.on_set_key = lambda s, t: host.calls.append(("set_key", s, t))
    view = _view(host)

    view.on_keypress("Set")

    assert ("set_key", CommandScope.ACC, 42) in host.calls
    assert created.initialized == [(CommandScope.ACC, 42)]
    assert ("ops_mode", True, created) in host.calls
    assert ("on_info",) in host.calls


# ---------------------------------------------------------------------------
# Promotion: a provisional record earns its place once it is named
# ---------------------------------------------------------------------------


def _promotable(scope: CommandScope = CommandScope.ACC, store: DummyStore = None) -> gui_mod.EngineGui:
    gui = _gui(scope, store)
    gui.promoted: list[tuple] = []
    gui.make_recent = lambda s, t, state=None: gui.promoted.append(("make_recent", s, t)) or True
    gui._request_options_rebuild = lambda: gui.promoted.append(("rebuild",))
    gui._reset_catalog_configured_accessories = lambda: gui.promoted.append(("catalog",))
    return gui


@pytest.mark.parametrize("scope", sorted(CREATABLE_SCOPES, key=lambda s: s.name))
def test_promoting_a_provisional_record_adds_it_to_recents_options_and_catalog(scope) -> None:
    gui = _promotable(scope)
    gui._provisional.add((scope, 42))

    assert gui.promote_component(DummyState(scope, 42)) is True
    assert gui.is_provisional(scope, 42) is False
    assert gui.promoted == [("make_recent", scope, 42), ("rebuild",), ("catalog",)]


def test_promoting_something_that_was_never_provisional_does_nothing() -> None:
    gui = _promotable()

    assert gui.promote_component(DummyState(CommandScope.ACC, 42)) is False
    assert gui.promoted == []


def test_promoting_the_same_record_twice_only_counts_once() -> None:
    gui = _promotable()
    gui._provisional.add((CommandScope.ACC, 42))
    state = DummyState(CommandScope.ACC, 42)

    assert gui.promote_component(state) is True
    assert gui.promote_component(state) is False
    assert gui.promoted.count(("make_recent", CommandScope.ACC, 42)) == 1


def test_promoting_without_a_state_falls_back_to_the_active_one() -> None:
    gui = _promotable(store=DummyStore({(CommandScope.ACC, 42): DummyState(CommandScope.ACC, 42)}))
    gui._scope_tmcc_ids[CommandScope.ACC] = 42
    gui._provisional.add((CommandScope.ACC, 42))

    assert gui.promote_component() is True
    assert gui.promoted[0] == ("make_recent", CommandScope.ACC, 42)


def test_promoting_with_nothing_selected_is_a_no_op() -> None:
    gui = _promotable()

    assert gui.promote_component() is False
    assert gui.promoted == []


def test_an_empty_record_is_not_promoted_while_the_base_is_still_silent() -> None:
    gui = _promotable()
    gui._provisional.add((CommandScope.ACC, 42))

    gui._promote_if_populated(DummyState(CommandScope.ACC, 42, is_comp_data_empty=True))

    assert gui.promoted == []
    assert gui.is_provisional(CommandScope.ACC, 42) is True


def test_a_record_the_base_has_answered_for_is_promoted_without_an_edit() -> None:
    gui = _promotable()
    gui._provisional.add((CommandScope.ACC, 42))

    gui._promote_if_populated(DummyState(CommandScope.ACC, 42, is_comp_data_empty=False))

    assert gui.is_provisional(CommandScope.ACC, 42) is False
    assert gui.promoted == [("make_recent", CommandScope.ACC, 42), ("rebuild",), ("catalog",)]


def test_promote_if_populated_tolerates_nothing_selected() -> None:
    gui = _promotable()

    gui._promote_if_populated(None)

    assert gui.promoted == []


def test_an_incoming_switch_report_promotes_a_provisional_switch() -> None:
    gui = _promotable(CommandScope.SWITCH)
    gui._scope_tmcc_ids[CommandScope.SWITCH] = 7
    gui._provisional.add((CommandScope.SWITCH, 7))
    gui.add_hover_action = lambda *_a, **_k: None
    gui._active_bg = gui._inactive_bg = "white"
    gui.switch_thru_btn = gui.switch_out_btn = SimpleNamespace()
    state = DummyState(CommandScope.SWITCH, 7, is_comp_data_empty=False)
    state.is_thru, state.is_out = True, False

    gui.on_new_switch(state)

    assert gui.is_provisional(CommandScope.SWITCH, 7) is False


def test_an_incoming_accessory_report_promotes_a_provisional_accessory() -> None:
    gui = _promotable(CommandScope.ACC)
    gui._scope_tmcc_ids[CommandScope.ACC] = 42
    gui._provisional.add((CommandScope.ACC, 42))
    state = DummyState(CommandScope.ACC, 42, is_comp_data_empty=False)

    # Not an AccessoryState, so the panel-specific work below is skipped; promotion is not.
    gui.on_new_accessory(state)

    assert gui.is_provisional(CommandScope.ACC, 42) is False
