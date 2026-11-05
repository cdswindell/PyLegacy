#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# src/tests/pdi/test_pdi_listener.py
import threading
from unittest.mock import Mock

import pytest

from src.pytrain import CommandScope
from src.pytrain.comm.command_listener import SYNC_COMPLETE, CommandDispatcher
from src.pytrain.db.comp_data import EngineData
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_state import EngineState
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_listener import PdiDispatcher, PdiListener
from src.pytrain.pdi.pdi_req import PdiReq, TmccReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import BROADCAST_TOPIC, CREATE_TOPIC
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from tests.test_base import wait_until


class _Catcher:
    def __init__(self):
        self.messages = []
        self.ev = threading.Event()

    def __call__(self, message) -> None:
        self.messages.append(message)
        self.ev.set()

    def wait(self, timeout=1.0):
        return self.ev.wait(timeout)


class _DeletableState:
    is_deletable = True

    def __init__(self) -> None:
        self.is_deleted = False
        self.clear_calls = 0

    def clear(self) -> bool:
        self.clear_calls += 1
        self.is_deleted = True
        return True


def _inactive_base_memory_record(scope: CommandScope, tmcc_id: int) -> BaseReq:
    payload = EngineData(None, tmcc_id).as_bytes()
    req = BaseReq(
        tmcc_id,
        PdiCommand.BASE_MEMORY,
        scope=scope,
        start=0,
        data_length=PdiReq.scope_record_length(scope),
        data_bytes=payload,
    )
    return BaseReq(req.as_bytes)


@pytest.fixture(autouse=True)
def clean_singletons():
    # Ensure prior tests state is cleared without broad excepts
    if PdiListener.is_built():
        PdiListener.stop()
    if PdiDispatcher.is_built():
        PdiDispatcher.get().shutdown()
    if CommandDispatcher.is_built():
        CommandDispatcher.get().shutdown()
    yield
    if PdiListener.is_built():
        PdiListener.stop()
    if PdiDispatcher.is_built():
        PdiDispatcher.get().shutdown()
    if CommandDispatcher.is_built():
        CommandDispatcher.get().shutdown()


def test_build_and_singleton():
    assert PdiListener.is_built() is False
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    assert listener is not None
    assert PdiListener.is_built() is True
    assert PdiListener.get() is listener
    assert PdiListener.is_running() is True

    # Stop and ensure singleton resets
    PdiListener.stop()
    assert PdiListener.is_built() is False
    assert PdiListener.is_running() is False


def test_listen_for_raises_when_not_built():
    with pytest.raises(AttributeError):
        PdiListener.listen_for(_Catcher(), CommandScope.ENGINE)


def test_offer_parses_and_publishes_broadcast():
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    catcher = _Catcher()
    # Subscribe to all broadcasts
    listener.subscribe_any(catcher)

    # Build a valid PDI request (Base Engine query for engine 1)
    req = BaseReq(20, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE)
    data = req.as_bytes

    # Prepend a garbage byte to ensure the listener skips non-SOP leading bytes
    noisy = bytes([0x00]) + data
    listener.offer(noisy)

    # Wait for dispatch
    assert catcher.wait(1.5), "Timed out waiting for dispatched PDI message"

    # Validate we got exactly one parsed message equal to what we sent
    assert len(catcher.messages) >= 1
    got = catcher.messages[-1]
    assert hasattr(got, "as_bytes")
    assert got.as_bytes == data

    # Cleanup
    listener.unsubscribe_any(catcher)
    PdiListener.stop()


def test_scope_subscription_receives_expected_message():
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    catcher = _Catcher()

    # Subscribe specifically to CommandScope.ENGINE
    listener.subscribe(catcher, CommandScope.ENGINE)

    req = BaseReq(33, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE)
    listener.offer(req.as_bytes)

    assert catcher.wait(1.5), "Timed out waiting for scoped PDI message"
    assert len(catcher.messages) >= 1
    got = catcher.messages[-1]
    assert got.scope == CommandScope.ENGINE
    assert got.tmcc_id == 33

    # Unsubscribe and ensure no further messages delivered
    listener.unsubscribe(catcher, CommandScope.ENGINE)
    catcher.ev.clear()

    # a broadcast subscriber sees every dispatched message, so the negative check below
    # waits on the message really having been dispatched rather than on a stopwatch
    sentinel = _Catcher()
    listener.subscribe_any(sentinel)
    listener.offer(req.as_bytes)
    assert sentinel.wait(5), "Timed out waiting for the message to be dispatched"

    # broadcasts are published before the scoped channels, so the dispatcher's queue is
    # drained as well: task_done is called only once every channel has been published to
    assert wait_until(lambda: listener.dispatcher._queue.unfinished_tasks == 0) is True
    assert catcher.ev.is_set() is False
    listener.unsubscribe_any(sentinel)

    PdiListener.stop()


def test_dispatcher_offer_accepts_bytes_or_req_and_filters_ack_ping_free_path():
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    catcher = _Catcher()
    listener.subscribe_any(catcher)

    # Normal, non-ack, non-ping request should be dispatched
    req = BaseReq(2, PdiCommand.BASE_MEMORY, scope=CommandScope.TRAIN)  # a standard request
    listener.dispatcher.offer(req)  # as object
    listener.dispatcher.offer(req.as_bytes)  # as bytes too

    # Should receive at least one (often two) messages
    assert catcher.wait(1.5)
    assert len(catcher.messages) >= 1

    # Sanity check last received equals something we offered
    last = catcher.messages[-1]
    assert last.as_bytes == req.as_bytes

    listener.unsubscribe_any(catcher)
    PdiListener.stop()


@pytest.fixture
def server_dispatcher(monkeypatch: pytest.MonkeyPatch) -> tuple[PdiDispatcher, Mock]:
    dispatcher = PdiDispatcher.build()
    forwarded = Mock()
    monkeypatch.setattr(PdiDispatcher, "is_server", property(lambda _dispatcher: True))
    monkeypatch.setattr(dispatcher, "update_client_state", forwarded)
    return dispatcher, forwarded


def _wait_for_dispatch(dispatcher: PdiDispatcher) -> None:
    # Only the queue can confirm all publication and forwarding for the packet are finished.
    # noinspection PyProtectedMember
    assert wait_until(lambda: dispatcher._queue.unfinished_tasks == 0), "Timed out draining the PDI dispatcher"


@pytest.mark.parametrize(
    ("packet", "tmcc_id"),
    [("d17600121fff5adf", 31), ("d1760012000030373337a7df", 737), ("d1760212ffff78df", 0)],
)
def test_ble_rx_publishes_raw_and_create_topics_and_forwards_to_clients(server_dispatcher, packet, tmcc_id):
    dispatcher, forwarded = server_dispatcher
    deliveries = []

    def receive_create(message):
        deliveries.append((CREATE_TOPIC, message))

    dispatcher.subscribe_any(lambda message: deliveries.append((BROADCAST_TOPIC, message)))
    dispatcher.subscribe(receive_create, CREATE_TOPIC)
    dispatcher.subscribe(lambda message: deliveries.append((PdiCommand.BLE_RX, message)), PdiCommand.BLE_RX)
    forwarded.side_effect = lambda message: deliveries.append(("forwarded", message))
    request = PdiReq.from_bytes(bytes.fromhex(packet))

    dispatcher.offer(request)
    _wait_for_dispatch(dispatcher)

    assert request.tmcc_id == tmcc_id
    assert deliveries == [
        (BROADCAST_TOPIC, request),
        (CREATE_TOPIC, request),
        (PdiCommand.BLE_RX, request),
        ("forwarded", request),
    ]
    dispatcher.unsubscribe(receive_create, CREATE_TOPIC)
    assert not dispatcher.is_creates_enabled


def test_dispatcher_delegates_tmcc_rx_without_forwarding_pdi(monkeypatch, server_dispatcher):
    dispatcher, forwarded = server_dispatcher
    command = CommandReq.build(TMCC1EngineCommandEnum.FORWARD_DIRECTION, 7)
    packet = TmccReq(command, PdiCommand.TMCC_RX).as_bytes
    request = TmccReq(packet)
    delegated = Mock()
    publish = Mock()
    monkeypatch.setattr(CommandDispatcher.get(), "offer", delegated)
    monkeypatch.setattr(dispatcher, "publish", publish)

    dispatcher.offer(request)
    _wait_for_dispatch(dispatcher)

    assert request.tmcc_command.is_tmcc_rx
    delegated.assert_called_once_with(request.tmcc_command, from_pdi=True)
    publish.assert_not_called()
    forwarded.assert_not_called()


def test_dispatcher_forwards_base_record_100_without_publishing_local_topics(monkeypatch, server_dispatcher):
    dispatcher, forwarded = server_dispatcher
    request = BaseReq(100, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE)
    publish = Mock()
    monkeypatch.setattr(dispatcher, "publish", publish)

    dispatcher.offer(request)
    _wait_for_dispatch(dispatcher)

    publish.assert_not_called()
    forwarded.assert_called_once_with(request)


def test_dispatcher_signals_sync_complete_for_base_train_98(monkeypatch):
    dispatcher = PdiDispatcher.build()
    delegated = Mock()
    monkeypatch.setattr(CommandDispatcher.get(), "offer", delegated)
    # BASE_TRAIN reply for ID 98 with a nonempty validity mask.
    request = BaseReq(bytes.fromhex("d121620200000100000000007adf"))

    dispatcher.offer(request)
    _wait_for_dispatch(dispatcher)

    delegated.assert_called_once_with(SYNC_COMPLETE)


def test_dispatcher_publishes_addressless_d4_first_record_to_action_topic(monkeypatch, server_dispatcher):
    dispatcher, forwarded = server_dispatcher
    request = D4Req(0, PdiCommand.D4_ENGINE, D4Action.FIRST_REC)
    publish = Mock(wraps=dispatcher.publish)
    monkeypatch.setattr(dispatcher, "publish", publish)
    catcher = _Catcher()
    dispatcher.subscribe(catcher, PdiCommand.D4_ENGINE, action=D4Action.FIRST_REC)

    dispatcher.offer(request)
    _wait_for_dispatch(dispatcher)

    publish.assert_called_once_with((PdiCommand.D4_ENGINE, D4Action.FIRST_REC), request)
    assert catcher.messages == [request]
    forwarded.assert_not_called()


# Pytest requires the fixture parameter to use its registered name.
# noinspection SpellCheckingInspection
def test_dispatcher_finishes_failed_packet_and_processes_next_packet(monkeypatch, caplog):
    dispatcher = PdiDispatcher.build()
    first = D4Req(0, PdiCommand.D4_ENGINE, D4Action.FIRST_REC)
    second = D4Req(0, PdiCommand.D4_TRAIN, D4Action.FIRST_REC)
    publish = Mock(side_effect=[RuntimeError("Dispatch failed"), None])
    monkeypatch.setattr(dispatcher, "publish", publish)

    dispatcher.offer(first)
    dispatcher.offer(second)
    _wait_for_dispatch(dispatcher)

    assert publish.call_count == 2
    publish.assert_called_with((PdiCommand.D4_TRAIN, D4Action.FIRST_REC), second)
    assert "Dispatch failed" in caplog.text


def test_dispatcher_publishes_delete_for_inactive_base_memory_record(monkeypatch):
    dispatcher = PdiDispatcher.build()
    catcher = _Catcher()
    state = _DeletableState()
    scope = CommandScope.ENGINE
    tmcc_id = 55

    def get_state(request_scope, request_tmcc_id, create=False):
        if (request_scope, request_tmcc_id, create) == (scope, tmcc_id, False):
            return state
        return None

    monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(get_state), raising=True)
    dispatcher.subscribe_delete(catcher)

    dispatcher.offer(_inactive_base_memory_record(scope, tmcc_id))

    assert catcher.wait(1.5), "Timed out waiting for delete notification"
    assert catcher.messages == [state]
    assert state.clear_calls == 1
    assert state.is_deleted is True

    dispatcher.unsubscribe_delete(catcher)


@pytest.mark.parametrize("tmcc_id,record_no", [(737, 7), (100, 0)])
def test_next_rec_broadcast_creates_and_updates_client_engine_state(monkeypatch, tmcc_id, record_no):
    """The server forwards complete NEXT_REC packets; clients consume them as state updates."""
    from src.pytrain.db.component_state import ComponentState

    ComponentStateStore.reset()
    # Avoid configuration requests while constructing the new engine state.
    monkeypatch.setattr(ComponentState, "request_config", lambda self, command: None)
    dispatcher = PdiDispatcher.build()
    forwarded = []
    monkeypatch.setattr(dispatcher, "update_client_state", lambda cmd: forwarded.append(cmd.as_bytes))
    dispatcher._is_server = True
    store = ComponentStateStore()
    dispatcher.subscribe(lambda message: store(message), CommandScope.ENGINE)

    data = EngineData(None, tmcc_id)
    data.road_name = "Amtrak"
    data.road_name_len = 6
    data.bt_id = 0x573A
    record = data.as_bytes()
    assert len(record) == 0xC0

    # NEXT_REC reply: record number, action, post-action, start, length,
    # next record pointer, two metadata bytes, then the complete record.
    payload = (
        PdiCommand.D4_ENGINE.as_bytes
        + record_no.to_bytes(2, "little")
        + D4Action.NEXT_REC.as_bytes
        + b"\x00\x00\x00\xc0\xff\xff\xc0\x10"
        + record
    )
    escaped, checksum = PdiReq._calculate_checksum(payload)
    packet = b"\xd1" + escaped + checksum + b"\xdf"
    response = PdiReq.from_bytes(packet)
    assert isinstance(response, D4Req)
    assert response.is_comp_data_record
    assert response.tmcc_id == tmcc_id

    dispatcher.offer(response)
    assert wait_until(lambda: len(forwarded) == 1)
    assert forwarded == [packet]
    server_state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, False)
    assert isinstance(server_state, EngineState)
    assert server_state.record_no == record_no
    server_data = server_state.comp_data
    assert isinstance(server_data, EngineData)
    assert server_data.bt_id == 0x573A

    # Simulate a separate client receiving the forwarded packet.
    ComponentStateStore.reset()
    client_store = ComponentStateStore()
    client_response = PdiReq.from_bytes(forwarded[0])
    client_store(client_response)
    client_state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, False)
    assert isinstance(client_state, EngineState)
    assert client_state.record_no == record_no
    client_data = client_state.comp_data
    assert isinstance(client_data, EngineData)
    assert client_data.bt_id == 0x573A
    assert client_state.road_name == "Amtrak"

    # Replaying the same packet updates the existing client state, not a second engine.
    client_store(client_response)
    assert ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, False) is client_state
