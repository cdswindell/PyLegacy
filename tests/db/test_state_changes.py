"""Scope-wide notifications preserve legacy state signaling without entity threads."""

import gc
from threading import Event, Thread
from weakref import ref

import pytest

from src.pytrain.db import component_state as state_module
from src.pytrain.db import state_changes as changes_module
from src.pytrain.db.comp_data import RouteData
from src.pytrain.db.component_state import ComponentState, SystemStateDict
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.components import RouteComponent
from src.pytrain.db.state_changes import StateChange, StateChangeHub
from src.pytrain.db.state_watcher import StateWatcher
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import PdiCommand
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum, TMCC1SwitchCommandEnum


@pytest.fixture
def state_environment(monkeypatch):
    states = SystemStateDict()
    hub = StateChangeHub()
    # PyCharm does not resolve this imported singleton on the patched module.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(state_module, "state_changes", hub)
    monkeypatch.setattr(changes_module, "state_changes", hub)
    monkeypatch.setattr(ComponentStateStore, "get", lambda: ComponentStateStore)
    monkeypatch.setattr(
        ComponentStateStore,
        "get_state",
        lambda scope, address, create=True: states[scope][address] if create else states[scope].get(address),
    )
    monkeypatch.setattr(ComponentState, "request_config", lambda *_: None)
    return states, hub


def test_no_backlog_without_subscribers_and_abandoned_mailboxes_are_collectible():
    hub = StateChangeHub()
    for address in range(1, 99):
        hub.publish(CommandScope.SWITCH, address)
    subscription = hub.subscribe({CommandScope.SWITCH})
    assert subscription.pending_count == 0
    assert not subscription.wait(0)
    hub.publish(CommandScope.SWITCH, 1)
    assert subscription.pending_count == 1
    reference = ref(subscription)
    del subscription
    gc.collect()
    assert reference() is None, "The hub must not retain an abandoned subscriber or its queue"
    replacement = hub.subscribe({CommandScope.SWITCH})
    assert replacement.pending_count == 0
    replacement.close()


def test_scope_filtering_fanout_and_coalescing_are_independent():
    hub = StateChangeHub()
    switches = hub.subscribe({CommandScope.SWITCH})
    both = hub.subscribe({CommandScope.SWITCH, CommandScope.ROUTE})
    for _ in range(1000):
        hub.publish(CommandScope.SWITCH, 4)
        hub.publish(CommandScope.ROUTE, 7)
        hub.publish(CommandScope.ENGINE, 12)
    assert switches.pending_count == 1
    assert both.pending_count == 2
    assert switches.wait(0)
    assert switches.drain() == {StateChange(CommandScope.SWITCH, 4)}
    assert both.drain() == {StateChange(CommandScope.SWITCH, 4), StateChange(CommandScope.ROUTE, 7)}
    switches.close()
    both.close()


def test_only_one_wakeup_is_outstanding_until_the_consumer_drains():
    hub = StateChangeHub()
    subscription = hub.subscribe({CommandScope.SWITCH})
    hub.publish(CommandScope.SWITCH, 1)
    assert subscription.wait(0)
    for address in range(1, 99):
        hub.publish(CommandScope.SWITCH, address)
    assert not subscription.wait(0), "A busy event loop must not accumulate wake notifications"
    assert subscription.pending_count == 98
    assert len(subscription.drain()) == 98
    hub.publish(CommandScope.SWITCH, 2)
    assert subscription.wait(0)
    subscription.close()
    assert subscription.closed and subscription.pending_count == 0
    assert subscription.drain() == frozenset()
    hub.publish(CommandScope.SWITCH, 3)
    assert not subscription.wait(0) and subscription.pending_count == 0


def test_close_wakes_a_blocking_consumer_without_a_sentinel_backlog():
    hub = StateChangeHub()
    subscription = hub.subscribe({CommandScope.SWITCH})
    entered = Event()
    results = []

    def receive():
        entered.set()
        results.append(subscription.wait())

    thread = Thread(target=receive, daemon=True)
    thread.start()
    assert entered.wait(1)
    subscription.close()
    thread.join(1)
    assert not thread.is_alive()
    assert results == [False]
    subscription.close()


def test_creation_updates_deletion_and_recreation_invalidate_the_same_key(state_environment, monkeypatch):
    states, hub = state_environment
    subscription = hub.subscribe({CommandScope.SWITCH})
    state = states[CommandScope.SWITCH][4]
    expected = {StateChange(CommandScope.SWITCH, 4)}
    assert subscription.drain() == expected
    state.update(CommandReq.build(TMCC1SwitchCommandEnum.OUT, 4))
    assert state.is_out and state.changed.is_set()
    assert subscription.drain() == expected
    state.update(CommandReq.build(TMCC1SwitchCommandEnum.SET_ADDRESS, 4))
    assert not state.changed.is_set()
    assert subscription.drain() == frozenset(), "NO_CHANGE must preserve existing notification semantics"
    state.update(CommandReq.build(TMCC1HaltCommandEnum.HALT))
    assert subscription.drain() == frozenset(), "Ignored updates must not generate invalidations"
    monkeypatch.setattr(ComponentStateStore, "delete_state", lambda item: states[item.scope].pop(item.address))
    assert state.clear(notify=False)
    assert state.is_deleted and not state.changed.is_set()
    assert subscription.drain() == expected
    state.update(CommandReq.build(TMCC1SwitchCommandEnum.THRU, 4))
    assert subscription.drain() == frozenset(), "Late traffic must not update a deleted state"
    replacement = states[CommandScope.SWITCH][4]
    assert replacement is not state and not replacement.is_deleted
    assert subscription.drain() == expected
    subscription.close()


def test_switch_and_nested_routes_keep_legacy_watchers_and_publish_final_alignment(state_environment, monkeypatch):
    states, hub = state_environment
    switch = states[CommandScope.SWITCH][1]

    def configure_route(address, component):
        data = RouteData(None, address)
        data.components = [component]
        request = BaseReq(address, PdiCommand.BASE_MEMORY, scope=CommandScope.ROUTE, data_bytes=data.as_bytes())
        route = states[CommandScope.ROUTE][address]
        route.update(BaseReq(request.as_bytes))
        return route

    child = configure_route(7, RouteComponent(1, 0))
    parent = configure_route(8, RouteComponent(7, 3))
    grandparent = configure_route(9, RouteComponent(8, 3))
    routes = (child, parent, grandparent)
    assert child.is_unknown
    assert all(not route.is_aligned for route in routes)
    subscription = hub.subscribe({CommandScope.SWITCH, CommandScope.ROUTE})
    watched_states = (switch, *routes)
    callbacks = [Event() for _ in watched_states]
    watchers = []

    def legacy_watcher(target_state, event):
        # Announce entry to the real Condition wait without changing its behavior.
        ready = Event()
        wait = target_state.synchronizer.wait

        def announce_wait(timeout=None):
            ready.set()
            return wait(timeout)

        # Patch the real Condition method to synchronize watcher startup in this test.
        # noinspection PyUnresolvedReferences
        monkeypatch.setattr(target_state.synchronizer, "wait", announce_wait)
        new_watcher = StateWatcher(target_state, event.set)
        watchers.append(new_watcher)
        assert ready.wait(1)

    try:
        for state, callback in zip(watched_states, callbacks):
            legacy_watcher(state, callback)
        for command, aligned in ((TMCC1SwitchCommandEnum.OUT, False), (TMCC1SwitchCommandEnum.THRU, True)):
            for callback in callbacks:
                callback.clear()
            switch.update(CommandReq.build(command, 1))
            assert all(callback.wait(1) for callback in callbacks), "Existing StateWatchers must still wake"
            assert all(route.is_aligned == aligned for route in routes)
            assert all(route.is_not_active != aligned and not route.is_unknown for route in routes)
            assert subscription.drain() == {StateChange(state.scope, state.address) for state in watched_states}
        unrelated = states[CommandScope.SWITCH][2]
        subscription.drain()
        unrelated.update(CommandReq.build(TMCC1SwitchCommandEnum.THRU, 2))
        assert subscription.drain() == {StateChange(CommandScope.SWITCH, 2)}
    finally:
        subscription.close()
        for watcher in watchers:
            watcher.shutdown()
            watcher.join(1)
            assert not watcher.is_alive()


def test_shared_condition_does_not_retain_its_state(state_environment):
    states, _hub = state_environment
    state = states[CommandScope.SWITCH][1]
    condition = state.synchronizer
    reference = ref(state)
    del states[CommandScope.SWITCH][1]
    del state
    gc.collect()
    assert reference() is None
    # A retained synchronization object remains usable after its state is gone.
    with condition:
        condition.notify_all()
