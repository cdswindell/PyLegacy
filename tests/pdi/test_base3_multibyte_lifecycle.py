#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  SPDX-License-Identifier: LGPL-3.0-only
#
import pytest

from src.pytrain.pdi.base3_buffer import Base3Buffer, _MultyByteCommand
from src.pytrain.pdi.constants import PDI_EOP, PDI_SOP, TMCC_TX
from src.pytrain.pdi.pdi_req import TmccReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.multibyte.multibyte_command_req import MultiByteReq
import src.pytrain.pdi.base3_buffer as base3_module


@pytest.fixture
def harness(monkeypatch):
    # Exercise the production packetizer and completion registry without a socket.
    buffer = object.__new__(Base3Buffer)
    buffer._mbc_registry = {}
    enqueued = []
    observed = []
    synchronized = []
    original = bytes([PDI_SOP, TMCC_TX]) + b"\xfb\x01\x02\x03\x04\x05\x06" + bytes([0, PDI_EOP])
    command = object()
    packets = [b"first", b"second", b"third"]

    monkeypatch.setattr(MultiByteReq, "vet_bytes", lambda *args, **kwargs: (False, True, False))
    monkeypatch.setattr(CommandReq, "from_bytes", lambda data: command)
    monkeypatch.setattr(TmccReq, "as_packets", lambda cmd: list(packets))
    monkeypatch.setattr(buffer, "send", lambda data: enqueued.append(data))
    monkeypatch.setattr(base3_module.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(base3_module.CommandObserver, "offer", lambda data: observed.append(data))
    monkeypatch.setattr(Base3Buffer, "sync_state", lambda data, **kwargs: synchronized.append((data, kwargs)))

    return buffer, original, command, packets, enqueued, observed, synchronized


def test_multibyte_packetization_and_deferred_completion(harness):
    buffer, original, command, packets, enqueued, observed, synchronized = harness

    assert buffer._packetize_multibyte_cmds(original) is None
    assert enqueued == packets
    assert observed == []
    assert synchronized == []

    for packet in packets[:-1]:
        assert buffer._check_for_multibyte_packet(packet) is None
        assert observed == []
        assert synchronized == []

    completed = buffer._check_for_multibyte_packet(packets[-1])
    assert isinstance(completed, _MultyByteCommand)
    assert completed.is_dispatched
    completed.on_sent_last_packet()

    assert observed == [original]
    assert synchronized == [(original, {"tmcc_cmd": command})]
    assert buffer._mbc_registry == {}


def test_identical_multibyte_commands_complete_independently(harness):
    buffer, original, command, packets, enqueued, observed, synchronized = harness
    assert buffer._packetize_multibyte_cmds(original) is None
    assert buffer._packetize_multibyte_cmds(original) is None
    assert enqueued == packets + packets

    for packet in packets + packets:
        completed = buffer._check_for_multibyte_packet(packet)
        if isinstance(completed, _MultyByteCommand):
            completed.on_sent_last_packet()

    assert observed == [original, original]
    assert synchronized == [(original, {"tmcc_cmd": command})] * 2
    assert buffer._mbc_registry == {}


def test_incomplete_multibyte_command_is_not_dispatched(harness):
    buffer, original, _, packets, _, observed, synchronized = harness
    buffer._packetize_multibyte_cmds(original)
    assert buffer._check_for_multibyte_packet(packets[0]) is None
    assert observed == []
    assert synchronized == []
    assert buffer._mbc_registry


def test_non_multibyte_command_is_passed_through(harness, monkeypatch):
    buffer, original, _, _, enqueued, observed, synchronized = harness
    monkeypatch.setattr(MultiByteReq, "vet_bytes", lambda *args, **kwargs: (False, False, False))
    assert buffer._packetize_multibyte_cmds(original) == original
    assert buffer._check_for_multibyte_packet(original) == original
    assert enqueued == []
    assert observed == []
    assert synchronized == []
