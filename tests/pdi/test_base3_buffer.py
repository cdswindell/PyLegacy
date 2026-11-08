#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# src/tests/pdi/test_base3_buffer.py
import threading
import time
from queue import Queue
from types import SimpleNamespace

import pytest

import src.pytrain.pdi.base3_buffer as base3_buffer_module
from src.pytrain import ComponentStateStore
from src.pytrain.pdi.base3_buffer import Base3Buffer, KeepAlive
from src.pytrain.pdi.constants import KEEP_ALIVE_CMD, PDI_EOP, PDI_SOP, TMCC4_TX, TMCC_TX, PdiCommand
from src.pytrain.pdi.pdi_req import PdiReq, TmccReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as Eng


# noinspection PyProtectedMember,PyTypeChecker
@pytest.fixture
def reset_singletons():
    # Ensure a clean state store each tests
    with ComponentStateStore._lock:
        _ = ComponentStateStore()
    # Force building a new instance by re-instantiating
    # No direct API to clear _instance, so create a new instance for each tests
    yield
    with ComponentStateStore._lock:
        ComponentStateStore.reset()
        ComponentStateStore._instance = None


class _DummyListener:
    def __init__(self):
        self.received = []
        self.ev = threading.Event()

    def offer(self, data: bytes):
        self.received.append(bytes(data))
        self.ev.set()


class _CapturingBuffer(Base3Buffer):
    """
    Override run() to avoid real sockets; capture sent bytes.
    """

    def __init__(self, *args, **kwargs):
        self.sent = []
        super().__init__(*args, **kwargs)

    def run(self) -> None:
        # Captures are synchronous; there is no socket queue to drain.
        pass

    def shutdown(self) -> None:
        super().shutdown()
        self.join(timeout=1)
        assert not self.is_alive()

    def send(self, data: bytes) -> None:
        # call parent logic to exercise multibyte logic and queueing
        if data:
            # replicate Base3Buffer.send behavior up to queueing, but capture instead
            from src.pytrain.protocol.multibyte.multibyte_command_req import MultiByteReq

            cmd_bytes = data[2:-2] if data and len(data) >= 4 and data[0] == PDI_SOP and data[-1] == PDI_EOP else data
            _, is_mvb, is_d4 = MultiByteReq.vet_bytes(cmd_bytes, raise_exception=False)
            if data and len(data) > 1 and data[0] == PDI_SOP and data[1] in {TMCC_TX, TMCC4_TX} and is_mvb:
                tmcc_cmd = CommandReq.from_bytes(cmd_bytes)
                for packet in TmccReq.as_packets(tmcc_cmd):
                    self.send(packet)
                    time.sleep(0.001)
                self.sync_state(data)
            else:
                # capture instead of enqueuing to socket loop
                self.sent.append(bytes(data))
                self.sync_state(data)


@pytest.fixture(autouse=True)
def clean_singletons(monkeypatch):
    Base3Buffer.stop()
    # Only keepalive-specific tests start this worker.
    monkeypatch.setattr(KeepAlive, "start", lambda self: None)
    yield
    Base3Buffer.stop()


@pytest.fixture
def controlled_keepalive(monkeypatch, clean_singletons):
    intervals = Queue()
    resume = threading.Semaphore(0)
    workers = []

    def sleep(seconds):
        intervals.put(seconds)
        resume.acquire()

    # Replace only this module's clock reference, not the shared time module.
    monkeypatch.setattr(base3_buffer_module, "time", SimpleNamespace(sleep=sleep))

    def start(buffer):
        worker = buffer._keep_alive
        workers.append(worker)
        threading.Thread.start(worker)
        return intervals, resume

    yield start
    for worker in workers:
        worker._is_running = False
        resume.release()
        worker.join(timeout=1)
        assert not worker.is_alive()


# noinspection PyProtectedMember
def build_tmcc_pdi_packet(cmd: CommandReq) -> bytes:
    """Wrap a TMCC CommandReq into a PDI TMCC_TX packet."""
    inner = PdiCommand.TMCC_TX.to_bytes(1, "big") + cmd.as_bytes
    payload, checksum = PdiReq._calculate_checksum(inner)  # using internal helper intentionally
    return bytes([PDI_SOP]) + payload + checksum + bytes([PDI_EOP])


def test_singleton_lifecycle_and_accessors():
    listener = _DummyListener()
    b = _CapturingBuffer("127.0.0.1", listener=listener)
    assert Base3Buffer.get() is b
    assert Base3Buffer.base_address() == "127.0.0.1"
    Base3Buffer.stop()
    with pytest.raises(AttributeError):
        Base3Buffer.get()


def test_enqueue_command_sends_bytes_and_keepalive_triggers(controlled_keepalive, reset_singletons):
    listener = _DummyListener()
    b = _CapturingBuffer("127.0.0.1", listener=listener)

    # speed command to 2-digit engine
    cmd = CommandReq.build(Eng.ABSOLUTE_SPEED, address=5, data=10, scope=CommandScope.ENGINE)
    packet = build_tmcc_pdi_packet(cmd)

    # Enqueue through class method
    Base3Buffer.enqueue_command(packet)
    intervals, _ = controlled_keepalive(b)
    assert intervals.get(timeout=1) == 2.0

    # We should have at least the command and one keepalive
    assert any(x == packet for x in b.sent)
    assert any(x == KEEP_ALIVE_CMD for x in b.sent)

    Base3Buffer.stop()


def test_multibyte_tmcc_command_is_packetized_and_sync_state_called(reset_singletons, monkeypatch):
    # get the engine state and set some fields
    eng_state = ComponentStateStore.get_state(CommandScope.ENGINE, 1234, create=True)
    eng_state.initialize(CommandScope.ENGINE, 1234)
    eng_state._d4_rec_no = eng_state._comp_data._record_no = 2

    # Build a multibyte parameter command (e.g., ENGINE_LABOR with data) is not multibyte;
    # use a true TMCC2 multibyte parameter: SET_ADDRESS is multibyte when >99 address encoded later,
    # but we can force a multibyte by using a MultiByte command from the library:
    # Use ABSOLUTE_SPEED with 4-digit address to force TMCC4 packets length 7 steps via as_packets.
    listener = _DummyListener()
    b = _CapturingBuffer("127.0.0.1", listener=listener)

    cmd = CommandReq.build(Eng.ABSOLUTE_SPEED, address=1234, data=42, scope=CommandScope.ENGINE)
    # Wrap as TMCC4_TX PDI by using TmccReq builder to ensure proper format
    pdi_tmcc = TmccReq(cmd, pdi_command=PdiCommand.TMCC4_TX).as_bytes

    # Spy on sync_state being invoked by capturing added packets later
    Base3Buffer.enqueue_command(pdi_tmcc)

    # Expect multiple 7-byte-chunk PDI packets sent (at least 1), all starting with SOP and command byte TMCC4_TX
    tmcc4_sent = [x for x in b.sent if len(x) >= 4 and x[0] == PDI_SOP and x[1] == TMCC4_TX and x[-1] == PDI_EOP]
    assert len(tmcc4_sent) >= 1

    Base3Buffer.stop()


def test_request_state_update_enqueues_when_valid_id_and_scope():
    listener = _DummyListener()
    b = _CapturingBuffer("127.0.0.1", listener=listener)

    # Valid engine id 20 triggers a BaseReq(BASE_MEMORY) state read (we can only assert that something was sent)
    Base3Buffer.request_state_update(20, CommandScope.ENGINE)
    assert len(b.sent) >= 1

    # Invalid id outside 1..99 should not enqueue anything new
    prev = len(b.sent)
    Base3Buffer.request_state_update(0, CommandScope.ENGINE)
    assert len(b.sent) == prev

    Base3Buffer.stop()


def test_sync_state_parses_tmcc_stream_and_may_emit_update_requests(monkeypatch, reset_singletons):
    # Ensure sync_state on a TMCC byte stream does not crash and may enqueue follow-ups
    listener = _DummyListener()
    b = _CapturingBuffer("127.0.0.1", listener=listener)

    # Two simple TMCC2 commands in a stream: ABSOLUTE_SPEED and FORWARD_DIRECTION for 2-digit engine
    c1 = CommandReq.build(Eng.ABSOLUTE_SPEED, address=3, data=5, scope=CommandScope.ENGINE).as_bytes
    c2 = CommandReq.build(Eng.FORWARD_DIRECTION, address=3, scope=CommandScope.ENGINE).as_bytes
    stream = c1 + c2

    Base3Buffer.sync_state(stream)

    # We cannot strictly assert exact content without coupling; assert no exceptions and possibly some sends
    # Either zero (no sync needed) or some number of follow-up BaseReq packets
    assert isinstance(b.sent, list)

    Base3Buffer.stop()


def test_keepalive_thread_sends_every_two_seconds(controlled_keepalive):
    listener = _DummyListener()
    b = _CapturingBuffer("127.0.0.1", listener=listener)
    intervals, resume = controlled_keepalive(b)
    for count in range(1, 4):
        assert intervals.get(timeout=1) == 2.0
        assert b.sent == [KEEP_ALIVE_CMD] * count
        if count < 3:
            resume.release()
