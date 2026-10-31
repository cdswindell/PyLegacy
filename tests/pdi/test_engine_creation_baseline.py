"""Baseline contracts for Base 3 transmission and BLE programming discovery.

These tests intentionally do not introduce CommandObserver or discovery behavior.
"""

import threading
from unittest.mock import MagicMock, Mock

import pytest

import src.pytrain.pdi.base3_buffer as base3_module
from src.pytrain.pdi.base3_buffer import Base3Buffer
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import PdiCommand
from src.pytrain.pdi.pdi_listener import PdiDispatcher, PdiListener
from src.pytrain.pdi.pdi_req import TmccReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.fixture(autouse=True)
def clean_singletons():
    Base3Buffer.stop()
    if PdiListener.is_built():
        PdiListener.stop()
    if PdiDispatcher.is_built():
        PdiDispatcher.get().shutdown()
    yield
    Base3Buffer.stop()
    if PdiListener.is_built():
        PdiListener.stop()
    if PdiDispatcher.is_built():
        PdiDispatcher.get().shutdown()


def test_base3_send_syncs_after_successful_transmission(monkeypatch):
    """sync_state must not run before socket.sendall has completed."""
    events = []
    packet = bytes.fromhex("d129d7df")
    fake_socket = MagicMock()
    fake_socket.__enter__.return_value = fake_socket
    fake_socket.connect.return_value = None
    fake_socket.sendall.side_effect = lambda data: events.append(("send", data))

    buffer = object.__new__(Base3Buffer)
    buffer._is_running = True
    buffer._base3_addr = "127.0.0.1"
    buffer._base3_port = 1234
    buffer._send_queue = Mock()
    buffer._send_queue.get.return_value = packet
    buffer._listener = None
    monkeypatch.setattr(base3_module.socket, "socket", lambda *args, **kwargs: fake_socket)
    monkeypatch.setattr(base3_module.select, "select", lambda *args: ([buffer._send_queue], [], []))
    monkeypatch.setattr(buffer, "_packetize_multibyte_cmds", lambda data: data)

    def sync(data):
        events.append(("sync", data))
        buffer._is_running = False

    monkeypatch.setattr(buffer, "sync_state", sync)
    buffer.run()
    assert events == [("send", packet.hex().upper().encode()), ("sync", packet)]


def test_multibyte_command_syncs_complete_request_once(monkeypatch):
    """Fragments are queued, while synchronization sees the logical request once."""
    from src.pytrain.protocol.multibyte.multibyte_command_req import MultiByteReq

    cmd = CommandReq.build(
        TMCC2EngineCommandEnum.ABSOLUTE_SPEED,
        address=1234,
        data=42,
        scope=CommandScope.ENGINE,
    )
    packet = TmccReq(cmd, pdi_command=PdiCommand.TMCC4_TX).as_bytes
    fragments = [b"fragment-one", b"fragment-two"]
    buffer = object.__new__(Base3Buffer)
    buffer.send = Mock()
    buffer.sync_state = Mock()
    monkeypatch.setattr(MultiByteReq, "vet_bytes", lambda *args, **kwargs: (False, True, False))
    monkeypatch.setattr(TmccReq, "as_packets", lambda request: fragments)
    monkeypatch.setattr(base3_module.time, "sleep", lambda seconds: None)

    assert buffer._packetize_multibyte_cmds(packet) is None
    assert [call.args[0] for call in buffer.send.call_args_list] == fragments
    buffer.sync_state.assert_called_once()
    assert buffer.sync_state.call_args.args[0] == packet
    assert buffer.sync_state.call_args.kwargs["tmcc_cmd"].command == cmd.command


@pytest.mark.parametrize(
    "enum,address,data",
    [
        (TMCC1EngineCommandEnum.FORWARD_DIRECTION, 7, 0),
        (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 7, 15),
        (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 737, 15),
    ],
)
def test_sync_state_decodes_tmcc_commands(monkeypatch, enum, address, data):
    """Existing sync_state sends decoded logical commands to BaseReq.update_eng."""
    buffer = object.__new__(Base3Buffer)
    buffer.send = Mock()
    monkeypatch.setattr(Base3Buffer, "_instance", buffer)
    seen = []
    monkeypatch.setattr(BaseReq, "update_eng", lambda req: seen.append(req) or None)
    cmd = CommandReq.build(enum, address=address, data=data, scope=CommandScope.ENGINE)
    Base3Buffer.sync_state(cmd.as_bytes)
    assert len(seen) == 1
    assert seen[0].command == cmd.command
    assert seen[0].address == address


@pytest.mark.parametrize(
    "packet_hex,tmcc_id",
    [
        ("d1760012000030373337a7df", 737),
        ("d176001225ff54df", 37),
    ],
)
def test_ble_programming_notification_published_on_engine_scope(packet_hex, tmcc_id):
    """A valid BLE programming message reaches existing scoped subscribers."""
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    received = []
    done = threading.Event()

    def capture(req):
        received.append(req)
        done.set()

    listener.subscribe(capture, CommandScope.ENGINE)
    listener.offer(bytes.fromhex(packet_hex))
    assert done.wait(2), "BLE programming message was not published"
    assert received[0].pdi_command == PdiCommand.BLE_RX
    assert received[0].tmcc_id == tmcc_id
    assert received[0].is_programming


def test_ble_notification_does_not_create_engine_state(monkeypatch):
    """BLE is a trigger, not an authoritative engine database record."""
    from src.pytrain.db.component_state_store import ComponentStateStore

    calls = []
    monkeypatch.setattr(
        ComponentStateStore,
        "get_state",
        lambda *args, **kwargs: calls.append((args, kwargs)) or None,
    )
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    done = threading.Event()
    listener.subscribe(lambda req: done.set(), CommandScope.ENGINE)
    listener.offer(bytes.fromhex("d176001225ff54df"))
    assert done.wait(2)
    assert not calls
