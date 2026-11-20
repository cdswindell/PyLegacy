"""Client snapshots must resolve 4D engine records before decoding train rosters."""

from threading import Condition
from types import SimpleNamespace
from typing import cast

import pytest

from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.comm.command_listener import CommandDispatcher
from src.pytrain.comm.enqueue_proxy_requests import EnqueueProxyRequests
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.components import ConsistComponent
from src.pytrain.db.engine_state import TrainState
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.pdi.pdi_state_store import PdiStateStore
from src.pytrain.protocol.constants import CommandScope


class SnapshotStore:
    def __init__(self, states):
        self.states = states

    def scopes(self):
        # Deliberately expose trains first; a set may legally iterate in this order.
        return tuple(scope for scope in (CommandScope.TRAIN, CommandScope.ENGINE) if scope in self.states)

    def addresses(self, scope):
        return tuple(self.states[scope])

    def query(self, scope, address):
        return self.states[scope][address]


def snapshot_state(scope, packet):
    return SimpleNamespace(scope=scope, comp_data=object(), as_bytes=lambda: [packet])


def replay_snapshot(monkeypatch, states, receiver):
    store = SnapshotStore(states)
    monkeypatch.setattr(ComponentStateStore, "get", classmethod(lambda _cls: store))
    monkeypatch.setattr(PdiStateStore, "store", staticmethod(dict))
    dispatcher = SimpleNamespace(_server_port=5110, _client_lock=Condition(), send_state_packet=receiver)
    CommandDispatcher.send_current_state(cast(CommandDispatcher, cast(object, dispatcher)), "127.0.0.1", 5110)


@pytest.mark.parametrize("include_engines, include_trains", ((True, True), (True, False), (False, True)))
def test_snapshot_orders_all_engines_before_trains_and_preserves_sync_envelopes(
    monkeypatch, include_engines: bool, include_trains: bool
):
    states = {}
    if include_engines:
        states[CommandScope.ENGINE] = {
            37: snapshot_state(CommandScope.ENGINE, b"engine37"),
            3233: snapshot_state(CommandScope.ENGINE, b"engine3233"),
        }
    if include_trains:
        states[CommandScope.TRAIN] = {500: snapshot_state(CommandScope.TRAIN, b"train500")}
    sent = []

    def receive(_ip, _port, packet):
        sent.append(packet)

    replay_snapshot(monkeypatch, states, receive)
    expected = []
    if include_engines:
        expected.extend((b"engine37", b"engine3233"))
    if include_trains:
        expected.append(b"train500")
    assert sent == [
        EnqueueProxyRequests.sync_begin_response(),
        *expected,
        EnqueueProxyRequests.sync_complete_response(),
    ]


def record_packet(command: PdiCommand, address: int, record_no: int) -> bytes:
    data = bytearray(b"\xff" * 192)
    data[2] = 13 if command == PdiCommand.D4_TRAIN else 12
    data[7:10] = bytes(3)
    data[0x1E] = data[0x3E] = 0
    data[0x43:0x46] = bytes((0, 2, 3))
    data[0xB8:0xBC] = f"{address:04d}".encode()
    if command == PdiCommand.D4_TRAIN:
        data[0xB6] = 100
        data[0x6E:0x76] = bytes.fromhex("ff 31 01 00 ff 17 25 80")
    return D4Req(
        record_no, command, D4Action.QUERY, start=0, data_length=192, data_bytes=bytes(data), timestamp=0
    ).as_bytes


def test_real_client_decodes_hybrid_head_and_tail_when_snapshot_source_lists_train_first(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda _cls: False))
    client = ComponentStateStore.build()
    states = {
        CommandScope.TRAIN: {500: snapshot_state(CommandScope.TRAIN, record_packet(PdiCommand(0x2F), 500, 0))},
        CommandScope.ENGINE: {3233: snapshot_state(CommandScope.ENGINE, record_packet(PdiCommand(0x2E), 3233, 1))},
    }

    def receive(_ip, _port, packet):
        if packet[0] == 0xD1:
            client(PdiReq.from_bytes(packet))

    replay_snapshot(monkeypatch, states, receive)
    train = client.query(CommandScope.TRAIN, 500)
    assert isinstance(train, TrainState)
    assert train.head_tmcc_id == 3233
    assert train.pseudo_train_id == 100
    assert [component.tmcc_id for component in train.consist_components] == [3233, 37]
    tail = train.get_consist_component(37)
    assert isinstance(tail, ConsistComponent)
    assert tail.is_tail
    assert tail.is_reverse
