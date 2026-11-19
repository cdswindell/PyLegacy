"""Pseudo train echoes refresh the owner record rather than inventing a D4 record."""

from typing import cast

import pytest

from pytrain.comm.comm_buffer import CommBuffer
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.engine_state import EngineState, TrainState
from pytrain.pdi.base3_db_refresh_manager import Base3DbRefreshManager
from pytrain.pdi.base_req import BaseReq
from pytrain.pdi.constants import D4Action, PdiCommand
from pytrain.pdi.d4_req import D4Req
from pytrain.pdi.pdi_req import PdiReq, TmccReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from pytrain.protocol.constants import CommandScope

from .test_pseudo_train_index import train_record


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda cls: False))
    return ComponentStateStore.build()


def pseudo_state() -> TrainState:
    state = ComponentStateStore.get_state(CommandScope.TRAIN, 100)
    assert isinstance(state, TrainState)
    assert state.record_no is None
    return state


def test_pseudo_train_with_no_record_number_queries_its_owner(store):
    store(train_record())
    state = pseudo_state()
    owner = ComponentStateStore.by_pseudo_train_id(100)
    assert isinstance(owner, TrainState)
    assert BaseReq.resolve_query_state(state) is owner
    request = BaseReq.create_base_query_request(state)
    assert isinstance(request, D4Req)
    assert request.pdi_command is PdiCommand.D4_TRAIN
    assert request.record_no == 0
    assert request.action is D4Action.QUERY
    assert request.start == 0
    assert request.data_length == 192
    assert request.as_bytes.startswith(bytes.fromhex("d1 2f 00 00 10"))
    assert state.record_no is None


@pytest.mark.parametrize("address", range(100, 128))
def test_real_four_digit_train_in_pseudo_range_keeps_its_record(store, address: int):
    pseudo_id = 127 if address == 100 else 100
    store(train_record(address=address, pseudo_id=pseudo_id, record_no=7))
    real = ComponentStateStore.get_state(CommandScope.TRAIN, address, create=False)
    assert isinstance(real, TrainState)
    assert BaseReq.resolve_query_state(real) is real
    request = BaseReq.create_base_query_request(real)
    assert isinstance(request, D4Req)
    assert request.pdi_command is PdiCommand.D4_TRAIN
    assert request.record_no == 7


def test_engine_in_pseudo_range_is_not_redirected_to_train(store):
    store(train_record())
    engine = ComponentStateStore.get_state(CommandScope.ENGINE, 100)
    assert isinstance(engine, EngineState)
    engine.update(D4Req(7, PdiCommand.D4_ENGINE, D4Action.MAP, tmcc_id=100))
    assert BaseReq.resolve_query_state(engine) is engine
    request = BaseReq.create_base_query_request(engine)
    assert isinstance(request, D4Req)
    assert request.pdi_command is PdiCommand.D4_ENGINE
    assert request.record_no == 7


def test_ordinary_train_keeps_base_memory_query(store):
    store(train_record())
    state = ComponentStateStore.get_state(CommandScope.TRAIN, 37)
    assert isinstance(state, TrainState)
    assert BaseReq.resolve_query_state(state) is state
    request = BaseReq.create_base_query_request(state)
    assert isinstance(request, BaseReq)
    assert request.pdi_command is PdiCommand.BASE_MEMORY
    assert request.tmcc_id == 37
    assert request.scope is CommandScope.TRAIN


# Exercise debounce bookkeeping without starting the worker thread or sending packets.
# noinspection PyProtectedMember
def test_owner_and_pseudo_refreshes_share_one_debounce_bucket(store):
    store(train_record())
    owner = ComponentStateStore.by_pseudo_train_id(100)
    assert isinstance(owner, TrainState)
    state = pseudo_state()
    manager = object.__new__(Base3DbRefreshManager)
    Base3DbRefreshManager.__init__(manager)
    manager._enqueue(owner)
    manager._enqueue(state)
    assert len(manager._buckets) == 1
    bucket = next(iter(manager._buckets.values()))
    latest = bucket.latest_state
    assert isinstance(latest, TrainState)
    assert latest is owner
    assert bucket.pending
    request = BaseReq.create_base_query_request(cast(TrainState, latest))
    assert isinstance(request, D4Req)
    assert request.record_no == 0


# Exercise the immediate-refresh bookkeeping without the singleton worker thread.
# noinspection PyProtectedMember
def test_forced_pseudo_refresh_uses_owner_record(store):
    store(train_record())
    owner = ComponentStateStore.by_pseudo_train_id(100)
    assert isinstance(owner, TrainState)
    manager = object.__new__(Base3DbRefreshManager)
    Base3DbRefreshManager.__init__(manager)
    manager._force_ready(pseudo_state())
    assert len(manager._buckets) == 1
    assert next(iter(manager._buckets.values())).latest_state is owner


# Reproduce the paired RX reset stream using real state updates and isolated debounce bookkeeping.
# noinspection PyProtectedMember
def test_reset_echoes_refresh_owner_without_a_pseudo_record_number(store):
    store(train_record())
    owner = ComponentStateStore.by_pseudo_train_id(100)
    assert isinstance(owner, TrainState)
    manager = object.__new__(Base3DbRefreshManager)
    Base3DbRefreshManager.__init__(manager)
    reset_commands = (
        (TMCC2EngineCommandEnum.NUMERIC, 0),
        (TMCC2EngineCommandEnum.DIESEL_RPM, 0),
        (TMCC2EngineCommandEnum.STOP_IMMEDIATE, 0),
        (TMCC2EngineCommandEnum.ENGINE_LABOR, 12),
        (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 0),
        (TMCC2EngineCommandEnum.BELL_OFF, 0),
        (TMCC2EngineCommandEnum.FORWARD_DIRECTION, 0),
    )
    for address in (550, 100):
        for command, data in reset_commands:
            sent = CommandReq.build(command, address, data, CommandScope.TRAIN)
            response = TmccReq(sent, PdiCommand(0x2D if address == 550 else 0x28)).as_bytes
            received = PdiReq.from_bytes(response)
            assert isinstance(received, TmccReq)
            assert received.tmcc_command.is_tmcc_rx
            store(received.tmcc_command)
            state = ComponentStateStore.get_state(CommandScope.TRAIN, address, create=False)
            assert isinstance(state, TrainState)
            manager._enqueue(state)
    pseudo = pseudo_state()
    assert pseudo.record_no is None
    assert len(manager._buckets) == 1
    pending = next(iter(manager._buckets.values())).latest_state
    assert pending is owner
    for state in (cast(TrainState, pending), pseudo):
        request = BaseReq.create_base_query_request(state)
        assert isinstance(request, D4Req)
        assert request.pdi_command is PdiCommand.D4_TRAIN
        assert request.record_no == 0
        assert request.as_bytes.startswith(bytes.fromhex("d1 2f 00 00 10"))
