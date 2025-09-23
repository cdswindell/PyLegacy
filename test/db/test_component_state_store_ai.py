#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import threading
from unittest import mock

import pytest

from src.pytrain.db.component_state import ComponentState
from src.pytrain.db.component_state_store import ComponentStateStore, DependencyCache
from src.pytrain.db.sync_state import SyncState
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import BROADCAST_ADDRESS, CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum as Aux,
)
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1HaltCommandEnum as Halt1,
)
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1SyncCommandEnum,
)
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as Engine2


class DummyListener:
    def __init__(self):
        self.calls = []

    def listen_for(self, subscriber, topic, *args, **kwargs):
        self.calls.append((subscriber, topic, args, kwargs))


# noinspection PyProtectedMember,PyTypeChecker
@pytest.fixture(autouse=True)
def reset_singletons():
    # Ensure a clean state store each test
    with ComponentStateStore._lock:
        ComponentStateStore.reset()
        ComponentStateStore._instance = None
    # Force building a new instance by re-instantiating
    # No direct API to clear _instance, so create a new instance for each test
    yield
    ComponentStateStore.reset()


def build_store(*, is_base=False, is_ser2=False, topics=None, listeners=()):
    # Build a new store with provided options
    store = ComponentStateStore(
        topics=topics,
        listeners=listeners,
        is_base=is_base,
        is_ser2=is_ser2,
    )
    return store


# Ensure request_config doesn't try to schedule/raise; instead, initialize
# noinspection PyUnusedLocal
def _mock_request_config(self, command):
    # address is set in update() before request_config() is called
    self.initialize(self.scope, self.address)
    # Do not requeue or raise
    return None


class TestComponentStateStoreBasics:
    def test_valid_topic_checks(self):
        assert ComponentStateStore.is_built() is False
        # Accepts CommandScope
        assert ComponentStateStore.is_valid_topic(CommandScope.ENGINE) is True
        # Accepts tuple with CommandScope[0]
        assert ComponentStateStore.is_valid_topic((CommandScope.ENGINE, 7)) is True
        # Rejects tuple without valid first element
        assert ComponentStateStore.is_valid_topic((None, 7)) is False
        assert ComponentStateStore.is_valid_topic(("engine", 7)) is False

    def test_build_and_get_singleton(self):
        assert ComponentStateStore.is_built() is False
        store = build_store()
        assert ComponentStateStore.is_built() is True
        assert ComponentStateStore.get() is store
        # __repr__ sanity
        assert "ComponentStateStore" in repr(store)

    def test_listen_for_registers_topics_with_listeners(self):
        dl = DummyListener()
        store = build_store(listeners=(dl,))
        store.listen_for([CommandScope.ENGINE, (CommandScope.ACC, 12)])
        # Two successful listen_for calls
        assert len(dl.calls) == 2
        assert dl.calls[0][1] == CommandScope.ENGINE
        assert dl.calls[1][1] == (CommandScope.ACC, 12)

    def test_keys_scopes_addresses_and_get_all_sorting(self):
        store = build_store()

        with mock.patch.object(ComponentState, "request_config", _mock_request_config):
            # Populate via state updates; dict auto-creates states per scope
            for addr in [22, 7, 13]:
                store(CommandReq.build(Aux.AUX1_ON, addr))

            # scopes present
            scopes = store.scopes()
            assert CommandScope.ACC in scopes

            # addresses contain all added
            addrs = list(store.addresses(CommandScope.ACC))
            for a in [7, 13, 22]:
                assert a in addrs

            # keys(None) returns scopes; keys(scope) returns addresses sorted
            top_keys = store.keys()
            assert CommandScope.ACC in top_keys
            addr_keys = store.keys(CommandScope.ACC)
            assert addr_keys == [7, 13, 22]

            all_states = store.get_all(CommandScope.ACC)
            assert [s.address for s in all_states] == [7, 13, 22]

    def test_component_validations_and_query(self):
        store = build_store()
        # Valid
        st = store.component(CommandScope.ACC, 42)
        assert st.scope == CommandScope.ACC and st.address == 42
        # Query by scope/address
        assert store.query(CommandScope.ACC, 42) is st
        # Invalid address for scope
        with pytest.raises(ValueError):
            store.component(CommandScope.ACC, 1000)

    def test_is_empty_property_and_keys(self):
        assert ComponentStateStore.is_built() is False

        store = build_store()
        # Initially, dict has builders; but no concrete entries till accessed
        assert store.is_empty  # SystemStateDict holds factories per scope
        # Ensure no keys until we touch a scope
        assert CommandScope.ENGINE not in store.scopes()

        with mock.patch.object(ComponentState, "request_config", _mock_request_config):
            # Touch engine scope via update to create it
            store(CommandReq.build(Engine2.SPEED_STOP_HOLD, 90))
            assert CommandScope.ENGINE in store.scopes()

    def test_set_and_get_state_and_is_state_synchronized(self):
        assert ComponentStateStore.is_built() is False
        _ = build_store()
        assert ComponentStateStore.is_state_synchronized() is False
        sync = SyncState(CommandScope.SYNC)
        # initialize to ensure condition/synchronizer created
        sync.update(CommandReq(TMCC1SyncCommandEnum.SYNCHRONIZED, 99))
        ComponentStateStore.set_state(CommandScope.SYNC, 99, sync)
        assert ComponentStateStore.is_state_synchronized() is True


class TestComponentStateStoreUpdates:
    def test_update_single_device(self):
        assert ComponentStateStore.is_built() is False
        store = build_store()
        with mock.patch.object(ComponentState, "request_config", _mock_request_config):
            addr = 12
            store(CommandReq.build(Aux.AUX1_ON, addr))
        st = store.query(CommandScope.ACC, addr)
        # Accessory aux1 transitions on
        assert st is not None
        assert st.aux1_state in {Aux.AUX1_ON, Aux.AUX1_OPT_ONE}

        # Toggle off
        store(CommandReq.build(Aux.AUX1_OFF, addr))
        assert st.aux1_state == Aux.AUX1_OFF

    def test_broadcast_updates_update_all_known_for_scope(self):
        assert ComponentStateStore.is_built() is False
        store = build_store()
        with mock.patch.object(ComponentState, "request_config", _mock_request_config):
            # Seed two accessories by touching them once
            for addr in [3, 9]:
                store(CommandReq.build(Aux.AUX1_ON, addr))
            # Broadcast AUX2_OFF across ACC scope
            store(CommandReq.build(Aux.AUX2_OFF, BROADCAST_ADDRESS))
        for addr in [3, 9]:
            st = store.query(CommandScope.ACC, addr)
            assert st.aux2_state == Aux.AUX2_OFF

    def test_halt_updates_all_components_when_not_filtered(self):
        assert ComponentStateStore.is_built() is False
        # If both base and ser2 listening, filtered updates are suppressed.
        # Here, do not filter, so HALT should flow to all existing devices.
        store = build_store(is_base=False, is_ser2=True)
        with mock.patch.object(ComponentState, "request_config", _mock_request_config):
            # Seed two different scopes
            store(CommandReq.build(Aux.AUX1_ON, 5))  # ACC
            store(CommandReq.build(Engine2.SPEED_MEDIUM, 777))  # ENGINE

            # Send TMCC1 HALT (is_halt)
            store(CommandReq(Halt1.HALT))
        # Accessory state remains valid; Engine should have SPEED_STOP_HOLD or STOP
        eng = store.query(CommandScope.ENGINE, 777)
        assert eng is not None
        assert eng.speed == 0

    def test_halt_filtered_is_suppressed_when_both_base_and_ser2(self):
        assert ComponentStateStore.is_built() is False
        # With both base and ser2, filtered commands are suppressed.
        store = build_store(is_base=True, is_ser2=True)
        with mock.patch.object(ComponentState, "request_config", _mock_request_config):
            # Seed engine and set non-zero speed
            store(CommandReq.build(Engine2.SPEED_MEDIUM, 21))
            eng = store.query(CommandScope.ENGINE, 21)
            assert eng.speed > 0

            # TMCC1 HALT is filtered; should be suppressed
            store(CommandReq(Halt1.HALT))
            # Speed remains unchanged by the suppressed HALT
            assert eng.speed > 0

    def test_system_halt_updates_engines_and_trains(self):
        assert ComponentStateStore.is_built() is False
        store = build_store()
        with mock.patch.object(ComponentState, "request_config", _mock_request_config):
            # Seed engine and a fake train (Engine2 address valid; train uses TMCC1 train commands typically,
            # but we can simulate presence by touching keys directly using engine scope for this test)
            store(CommandReq.build(Engine2.SPEED_MEDIUM, 41))
            before = store.query(CommandScope.ENGINE, 41).speed
            assert before > 0

            # SYSTEM_HALT applies to engines and trains
            store(CommandReq(Engine2.SYSTEM_HALT))
        after = store.query(CommandScope.ENGINE, 41).speed
        assert after == 0


class TestDependencyCacheMappings:
    def test_results_in_and_caused_by_have_known_entries(self):
        cache = DependencyCache.build()
        # RESET results in STOP_IMMEDIATE (among others)
        res = cache.results_in(Engine2.RESET, dereference_aliases=True, include_aliases=False)
        assert Engine2.STOP_IMMEDIATE in res

        # STOP_IMMEDIATE is caused by RESET, FORWARD_DIRECTION, REVERSE_DIRECTION, TOGGLE_DIRECTION
        causes = cache.caused_by(Engine2.STOP_IMMEDIATE, dereference_aliases=True, include_aliases=False)
        assert Engine2.FORWARD_DIRECTION in causes
        assert Engine2.REVERSE_DIRECTION in causes
        assert Engine2.TOGGLE_DIRECTION in causes

    def test_toggles_and_disabled_by_switch(self):
        cache = DependencyCache.build()
        # Switch.OUT and Switch.THRU are mutually exclusive via toggles
        from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum as Switch

        disabled = cache.disabled_by(Switch.OUT, dereference_aliases=True, include_aliases=False)
        assert Switch.THRU in disabled

        disabled_thru = cache.disabled_by(Switch.THRU, dereference_aliases=True, include_aliases=False)
        assert Switch.OUT in disabled_thru

    def test_enabled_by_and_disabled_by_for_effects(self):
        cache = DependencyCache.build()
        from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EffectsControl as Effects

        # Effects.SMOKE_HIGH disables the other smoke levels
        disabled = set(cache.disabled_by(Effects.SMOKE_HIGH, dereference_aliases=True, include_aliases=False))
        for other in (Effects.SMOKE_LOW, Effects.SMOKE_MEDIUM, Effects.SMOKE_OFF):
            assert other in disabled

        # Enabled_by is typically a reverse mapping; for a base command without extra relationships,
        # the command itself should be present
        enabled = set(cache.enabled_by(Engine2.FORWARD_DIRECTION, dereference_aliases=True, include_aliases=False))
        assert Engine2.FORWARD_DIRECTION in enabled


@pytest.mark.timeout(2)
def test_thread_safety_basic_concurrent_updates():
    """
    Ensure store does not crash on concurrent updates and that final state is consistent.
    """
    assert ComponentStateStore.is_built() is False
    store = build_store()
    addr = 33

    def worker():
        # Flip aux1 on/off quickly
        with mock.patch.object(ComponentState, "request_config", _mock_request_config):
            for i in range(50):
                cmd = Aux.AUX1_ON if i % 2 == 0 else Aux.AUX1_OFF
                store(CommandReq.build(cmd, addr))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    st = store.query(CommandScope.ACC, addr)
    assert st is not None
    # Should end either on or off consistently; just ensure it's one of the valid states
    assert st.aux1_state in {Aux.AUX1_ON, Aux.AUX1_OFF}
