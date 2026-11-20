"""Deterministic regression coverage for association changes during hybrid fan-out."""

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Condition, Event
from typing import cast

import pytest

from pytrain.comm.comm_buffer import CommBuffer
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.pdi.base3_buffer import Base3Buffer
from pytrain.pdi.constants import PdiCommand
from pytrain.pdi.pdi_req import TmccReq
from pytrain.protocol.command_req import CommandReq
from pytrain.utils.pollable_queue import PollableQueue

from ..db.test_pseudo_train_index import train_record

SOURCE = bytes.fromhex("d1 2c f9 01 e7 30 35 35 30 29 df")
COMPANION = bytes.fromhex("d1 27 f9 c9 e7 30 df")


@pytest.fixture
# Initialize only the queue fields needed for send(), without starting network threads.
# noinspection PyProtectedMember
def writer(monkeypatch) -> Base3Buffer:
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda cls: False))
    ComponentStateStore.build()(train_record())
    instance = object.__new__(Base3Buffer)
    instance._send_cv = Condition()
    instance._send_queue = cast(PollableQueue, Queue())
    return instance


# Read the isolated in-memory queue; no worker thread is running.
# noinspection PyProtectedMember
def queued(writer: Base3Buffer) -> list[bytes]:
    result = []
    while not writer._send_queue.empty():
        result.append(writer._send_queue.get_nowait())
    return result


@pytest.mark.parametrize("replacement", (None, 127))
def test_association_is_rechecked_after_decoding(writer, monkeypatch, replacement):
    original_init = TmccReq.__init__

    def decode_and_change(request, data, pdi_command=None):
        original_init(request, data, pdi_command)
        if data == SOURCE:
            if replacement is None:
                ComponentStateStore.reset()
            else:
                ComponentStateStore.get()(train_record(pseudo_id=replacement))

    monkeypatch.setattr(TmccReq, "__init__", decode_and_change)
    writer.send(SOURCE)
    expected = [SOURCE] if replacement is None else [SOURCE, bytes.fromhex("d1 27 f9 ff e7 fa df")]
    assert queued(writer) == expected


# Probe the real store lock from another thread at the exact setter and serializer boundaries.
# noinspection PyProtectedMember
def test_reset_cannot_change_association_during_retargeting_or_serialization(writer, monkeypatch):
    lock = ComponentStateStore._lock
    setter_entered, setter_checked = Event(), Event()
    serializer_entered, serializer_checked = Event(), Event()
    probes = []
    address_property = cast(property, CommandReq.__dict__["address"])
    original_setter = address_property.fset
    assert original_setter is not None
    bytes_property = cast(property, TmccReq.__dict__["as_bytes"])
    original_serializer = bytes_property.fget
    assert original_serializer is not None

    def checked_setter(command, address):
        if address == 100:
            setter_entered.set()
            assert setter_checked.wait(5), "The reset thread did not probe the setter boundary"
            assert probes == [False], "The association was unlocked during retargeting"
        original_setter(command, address)

    def checked_serializer(request):
        if request.pdi_command == PdiCommand.TMCC_TX:
            serializer_entered.set()
            assert serializer_checked.wait(5), "The reset thread did not probe the serializer boundary"
            assert probes == [False, False], "The association was unlocked during serialization"
        return original_serializer(request)

    def reset_during_send():
        for entered, checked in ((setter_entered, setter_checked), (serializer_entered, serializer_checked)):
            assert entered.wait(5), "The send thread did not reach the expected boundary"
            acquired = lock.acquire(blocking=False)
            probes.append(acquired)
            if acquired:
                lock.release()
            checked.set()
        ComponentStateStore.reset()

    monkeypatch.setattr(CommandReq, "address", property(address_property.fget, checked_setter))
    monkeypatch.setattr(TmccReq, "as_bytes", property(checked_serializer))
    with ThreadPoolExecutor(max_workers=2) as executor:
        reset = executor.submit(reset_during_send)
        sending = executor.submit(lambda: writer.send(SOURCE))
        sending.result(timeout=10)
        reset.result(timeout=10)
    assert probes == [False, False]
    assert ComponentStateStore.pseudo_train_ids() == set()
    assert queued(writer) == [SOURCE, COMPANION]


# Another thread must be able to acquire the store lock while send() is queueing either packet.
# noinspection PyProtectedMember
def test_snapshot_lock_is_released_before_queueing(writer, monkeypatch):
    lock = ComponentStateStore._lock
    queue = cast(Queue, writer._send_queue)
    original_put = queue.put

    def can_acquire():
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
        return acquired

    with ThreadPoolExecutor(max_workers=1) as executor:

        def checked_put(item, block=True, timeout=None):
            assert executor.submit(can_acquire).result(timeout=5), "Store lock held while queueing"
            original_put(item, block=block, timeout=timeout)

        monkeypatch.setattr(queue, "put", checked_put)
        writer.send(SOURCE)
    assert queued(writer) == [SOURCE, COMPANION]


# An exception inside the context must release the real lock for other threads.
# noinspection PyProtectedMember
def test_snapshot_releases_lock_when_companion_serialization_fails(writer, monkeypatch):
    lock = ComponentStateStore._lock

    def fail_serialization(_request):
        raise ValueError("Simulated serialization failure")

    monkeypatch.setattr(TmccReq, "as_bytes", property(fail_serialization))
    writer.send(SOURCE)
    assert queued(writer) == [SOURCE]

    def can_acquire():
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
        return acquired

    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(can_acquire).result(timeout=5)


def test_snapshot_does_not_create_a_state_store(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    with ComponentStateStore.pseudo_train_snapshot(550) as pseudo_id:
        assert pseudo_id is None
    assert not ComponentStateStore.is_built()
