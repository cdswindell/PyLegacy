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

from src.pytrain.db.comp_data import CompDataMixin
from src.pytrain.db.component_state import ComponentState
from src.pytrain.db.component_state_store import ComponentStateStore, DependencyCache
from src.pytrain.db.sync_state import SyncState
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import IrdaAction, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.irda_req import IrdaReq, IrdaSequence
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
    # Ensure a clean state store each tests
    with ComponentStateStore._lock:
        ComponentStateStore.reset()
        ComponentStateStore._instance = None
    # Force building a new instance by re-instantiating
    # No direct API to clear _instance, so create a new instance for each tests
    yield
    with ComponentStateStore._lock:
        ComponentStateStore.reset()
        ComponentStateStore._instance = None


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


def bluetooth_record(address, bt_id, *, scope=CommandScope.ENGINE, speed=0, record_no=123):
    record = CompDataMixin()
    record.initialize(scope, address)
    record.comp_data._bt_id = bt_id
    record.comp_data._speed = speed
    data = record.comp_data.as_bytes()
    if address > 99:
        command = D4Req(
            record_no,
            PdiCommand.D4_ENGINE if scope == CommandScope.ENGINE else PdiCommand.D4_TRAIN,
            data_length=len(data),
            data_bytes=data,
            timestamp=0,
        )
        return D4Req(command.as_bytes)
    command = BaseReq(address, PdiCommand.BASE_MEMORY, scope=scope, data_length=len(data), data_bytes=data)
    return BaseReq(command.as_bytes)


class TestComponentStateStoreBluetooth:
    def test_lookup_before_build_returns_none(self):
        assert ComponentStateStore.by_bluetooth_id(0xABCD) is None
        assert ComponentStateStore.is_built() is False

    def test_unknown_id_does_not_create_state(self):
        store = build_store()

        assert store.by_bluetooth_id(0xABCD) is None
        assert store.is_empty
        assert store._bt_index == {}

    @pytest.mark.parametrize("address", [1, 98, 100, 9999])
    def test_record_indexes_the_actual_engine_state(self, address):
        store = build_store()
        store(bluetooth_record(address, 0xABCD))

        state = store.query(CommandScope.ENGINE, address)
        assert state is not None
        assert state.bt_int == 0xABCD
        assert store.by_bluetooth_id(0xABCD) is state
        assert store.by_bluetooth_id(0x1234) is None

    @pytest.mark.parametrize("addresses", [(7, 1234), (1234, 7), (42, 7, 1234), (1234, 42, 7)])
    def test_shared_id_selects_highest_address_regardless_of_update_order(self, addresses):
        store = build_store()
        for address in addresses:
            store(bluetooth_record(address, 0xABCD))

        assert store.by_bluetooth_id(0xABCD) is store.query(CommandScope.ENGINE, max(addresses))
        assert list(store._bt_index[0xABCD]) == sorted(addresses)

    def test_different_bluetooth_ids_are_indexed_independently(self):
        store = build_store()
        store(bluetooth_record(7, 0xABCD))
        store(bluetooth_record(1234, 0x1234))

        assert store.by_bluetooth_id(0xABCD) is store.query(CommandScope.ENGINE, 7)
        assert store.by_bluetooth_id(0x1234) is store.query(CommandScope.ENGINE, 1234)

    def test_repeated_record_updates_the_existing_indexed_state(self):
        store = build_store()
        store(bluetooth_record(7, 0xABCD))
        state = store.query(CommandScope.ENGINE, 7)
        store(bluetooth_record(7, 0xABCD, speed=10))

        assert store.by_bluetooth_id(0xABCD) is state
        assert state.comp_data._speed == 10
        assert len(store._bt_index[0xABCD]) == 1

    def test_zero_id_is_not_indexed(self):
        store = build_store()
        store(bluetooth_record(7, 0))

        assert store.query(CommandScope.ENGINE, 7) is not None
        assert store.by_bluetooth_id(0) is None
        assert store._bt_index == {}

    @pytest.mark.parametrize("address", [7, 1234])
    def test_train_records_do_not_replace_engine_bluetooth_entries(self, address):
        store = build_store()
        store(bluetooth_record(address, 0xABCD))
        store(bluetooth_record(address, 0xABCD, scope=CommandScope.TRAIN))

        assert store.query(CommandScope.TRAIN, address) is not None
        assert store.by_bluetooth_id(0xABCD) is store.query(CommandScope.ENGINE, address)
        assert len(store._bt_index[0xABCD]) == 1

    def test_command_without_component_data_does_not_create_bluetooth_index(self):
        store = build_store()
        command = BaseReq(
            7, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE, start=4, data_length=2, data_bytes=b"\xcd\xab"
        )
        store(BaseReq(command.as_bytes))

        assert store.query(CommandScope.ENGINE, 7) is not None
        assert store._bt_index == {}


class TestComponentStateStoreBasics:
    @pytest.mark.parametrize(
        "operation",
        [
            lambda: ComponentStateStore.get(),
            lambda: ComponentStateStore.get_state(CommandScope.ENGINE, 7),
            lambda: ComponentStateStore.set_state(CommandScope.ENGINE, 7, None),
            lambda: ComponentStateStore.delete_state(None),
        ],
    )
    def test_state_access_requires_a_built_store(self, operation):
        with pytest.raises(AttributeError, match="ComponentStateStore not built"):
            operation()

    @pytest.mark.parametrize("is_base, is_ser2", [(False, False), (False, True), (True, False), (True, True)])
    def test_build_flags_and_reinitialization(self, is_base, is_ser2):
        store = ComponentStateStore.build(is_base=is_base, is_ser2=is_ser2)

        assert ComponentStateStore.build() is store
        assert store.is_base is is_base
        assert store.is_ser2 is is_ser2
        assert store.is_filter_updates is (is_base and is_ser2)

    def test_query_without_creation_and_state_deletion(self):
        store = build_store()
        assert store.get_state(CommandScope.ENGINE, 7, create=False) is None
        assert store.query(CommandScope.ENGINE) is None
        assert store.keys(CommandScope.ENGINE) == []
        assert store.get_all(CommandScope.ENGINE) == []
        assert store.is_empty

        state = store.get_state(CommandScope.ENGINE, 7)
        assert store.query(CommandScope.ENGINE) == [state]
        assert CommandScope.ENGINE in store
        store.delete_state(state)
        store.delete_state(state)
        store.delete_state(None)
        assert store.query(CommandScope.ENGINE, 7) is None

        store.reset()
        assert store.is_empty
        assert store.get() is store

    def test_road_number_alias_is_omitted_and_replaced_by_real_engine(self):
        store = build_store()
        store(bluetooth_record(7, 0xABCD))
        state = store.query(CommandScope.ENGINE, 7)
        store.set_state(CommandScope.ENGINE, 1234, state)

        assert store.get_all(CommandScope.ENGINE) == [state]
        assert store.keys(CommandScope.ENGINE) == [7]
        store(bluetooth_record(1234, 0x1234))
        replacement = store.query(CommandScope.ENGINE, 1234)
        assert replacement is not state
        assert replacement.address == 1234
        assert store.get_all(CommandScope.ENGINE) == [state, replacement]

    def test_record_number_lookup_uses_engine_records_only(self):
        store = build_store()
        assert store.by_record_no(123) is None
        store(bluetooth_record(1234, 0xABCD, record_no=123))
        store(bluetooth_record(2345, 0x1234, scope=CommandScope.TRAIN, record_no=456))

        assert store.by_record_no(123) is store.query(CommandScope.ENGINE, 1234)
        assert store.by_record_no(456) is None

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

    def test_irda_config_marks_corresponding_accessory_as_sensor_track(self):
        assert ComponentStateStore.is_built() is False
        store = build_store()
        addr = 18

        config = IrdaReq(
            addr,
            PdiCommand.IRDA_RX,
            IrdaAction.CONFIG,
            sequence=IrdaSequence.SLOW_SPEED_NORMAL_SPEED,
        )
        store(config)

        irda_state = store.query(CommandScope.IRDA, addr)
        acc_state = ComponentStateStore.get_state(CommandScope.ACC, addr)
        assert irda_state is not None
        assert acc_state.is_sensor_track is False

        store._process_config_cache()

        assert acc_state.parent is irda_state
        assert acc_state.is_sensor_track is True
        assert acc_state.is_lcs_component is True
        assert acc_state.as_dict()["type"] == "sensor track"

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
            # but we can simulate presence by touching keys directly using engine scope for this tests)
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
        assert Engine2.ABSOLUTE_SPEED in res

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
