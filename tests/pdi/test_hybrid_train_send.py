"""Hybrid train fan-out at the Base 3 send boundary, without network activity."""

from __future__ import annotations

from queue import Queue
from threading import Condition
from typing import cast
from unittest.mock import Mock, patch

import pytest

import pytrain.pdi.base3_buffer as base3_module
from pytrain.comm.comm_buffer import CommBuffer
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.pdi.base3_buffer import Base3Buffer
from pytrain.pdi.constants import KEEP_ALIVE_CMD, PdiCommand
from pytrain.pdi.pdi_req import PdiReq, TmccReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.command_def import CommandDefEnum
from pytrain.protocol.multibyte.dcds_command_req import VariableCommandReq
from pytrain.utils.pollable_queue import PollableQueue
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.multibyte.multibyte_constants import (
    TMCC2LashupCommandEnum,
    TMCC2MaskingControl,
    TMCC2VariableEnum,
)
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

from ..db.test_pseudo_train_index import train_record


@pytest.fixture
# Set up only queue/registry fields to exercise production code without starting its socket thread.
# noinspection PyProtectedMember
def buffer(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda cls: False))
    store = ComponentStateStore.build()
    store(train_record())
    writer = object.__new__(Base3Buffer)
    writer._send_cv = Condition()
    # The in-memory queue supplies the methods used here without allocating socket pairs.
    writer._send_queue = cast(PollableQueue, Queue())
    writer._mbc_registry = {}
    return writer


# Read the isolated test queue without running the network loop.
# noinspection PyProtectedMember
def queued(writer: Base3Buffer) -> list[bytes]:
    packets = []
    while not writer._send_queue.empty():
        packets.append(writer._send_queue.get_nowait())
    return packets


# Scalar commands and variable payloads require this valid scalar-or-list union.
# PyCharm incorrectly rejects its list branch; keep the suppression on this helper only.
# noinspection PyTypeHints
def packet(
    address: int = 550,
    scope: CommandScope = CommandScope.TRAIN,
    command: CommandDefEnum = TMCC2EngineCommandEnum.QUILLING_HORN,
    data: int | list[int] = 7,
) -> bytes:
    if isinstance(data, list):
        assert isinstance(command, TMCC2VariableEnum)
        req = VariableCommandReq.build(command, address, data, scope)
    else:
        req = CommandReq.build(command, address, data, scope)
    pdi_command = PdiCommand(0x2C if req.uses_d4_address else 0x27)
    return TmccReq(req, pdi_command).as_bytes


@pytest.mark.parametrize(
    "value,original,companion",
    (
        (7, "d1 2c f9 01 e7 30 35 35 30 29 df", "d1 27 f9 c9 e7 30 df"),
        (8, "d1 2c f9 01 e8 30 35 35 30 28 df", "d1 27 f9 c9 e8 2f df"),
    ),
)
def test_horn_fanout_matches_cab_capture(buffer, value, original, companion):
    source = packet(data=value)
    assert source == bytes.fromhex(original)
    buffer.send(source)
    assert queued(buffer) == [source, bytes.fromhex(companion)]


@pytest.mark.parametrize(
    "source",
    (
        KEEP_ALIVE_CMD,
        bytes.fromhex("d1 26 64 01 00 02 00 00 00 00 02 c0 b1 df"),
        bytes.fromhex("d1 2f 00 00 11 00 00 b6 01 00 00 00 00 64 a5 df"),
        bytes.fromhex("d1 27 f9 c9 e7 30 df"),
        bytes.fromhex("d1 2d f9 01 e7 30 35 35 30 28 df"),
        b"",
        b"\xd1",
        b"\xd1\x2c\xf9",
    ),
)
def test_non_candidates_never_invoke_command_decoder(buffer, source):
    with patch.object(TmccReq, "__init__", side_effect=AssertionError("Unexpected command conversion")):
        buffer.send(source)
    assert queued(buffer) == ([source] if source else [])


@pytest.mark.parametrize(
    "address,scope",
    (
        (550, CommandScope.ENGINE),
        (100, CommandScope.ENGINE),
        (551, CommandScope.TRAIN),
        (127, CommandScope.TRAIN),
    ),
)
def test_engines_and_unassociated_trains_are_not_decoded_or_duplicated(buffer, address, scope):
    source = packet(address=address, scope=scope)
    with patch.object(TmccReq, "__init__", side_effect=AssertionError("Unexpected command conversion")):
        buffer.send(source)
    assert queued(buffer) == [source]


def test_sniffer_can_be_disabled_explicitly(buffer):
    source = packet()
    with patch.object(Base3Buffer, "_pseudo_train_command", side_effect=AssertionError("Sniffer must be disabled")):
        buffer.send(source, False)
    assert queued(buffer) == [source]


def test_real_four_digit_train_in_pseudo_range_uses_its_own_association(buffer):
    store = ComponentStateStore.get()
    store(train_record(address=101, pseudo_id=127, record_no=1))
    source = packet(address=101)
    buffer.send(source)
    output = queued(buffer)
    assert output[0] == source
    assert len(output) == 2
    companion = PdiReq.from_bytes(output[1])
    assert isinstance(companion, TmccReq)
    assert companion.pdi_command is PdiCommand.TMCC_TX
    assert companion.tmcc_command.address == 127
    assert companion.tmcc_command.as_bytes == bytes.fromhex("f9 ff e7")


# The fixture name is supplied by pytest's built-in log capture support.
# noinspection SpellCheckingInspection
def test_invalid_candidate_preserves_original_and_logs_failure(buffer, caplog):
    source = packet()
    broken = source[:-2] + bytes((source[-2] ^ 1, source[-1]))
    buffer.send(broken)
    assert queued(buffer) == [broken]
    assert "Cannot create pseudo train command" in caplog.text


@pytest.mark.parametrize(
    "command,data,word_count",
    (
        (TMCC2MaskingControl.NC_NC, 0, 3),
        (TMCC2LashupCommandEnum.ASSIGN_TRAIN, list(b"0001\x00"), 10),
        (TMCC2LashupCommandEnum.ROAD_SPEED, [0xEF, 0xBE], 7),
    ),
)
# Exercise private packetization and completion with no background thread.
# noinspection PyProtectedMember
def test_multibyte_sequences_are_mirrored_once_with_valid_checksums(buffer, command, data, word_count):
    source = packet(command=command, data=data)
    buffer.send(source)
    logical = queued(buffer)
    assert len(logical) == 2
    assert logical[0] == source
    companion = PdiReq.from_bytes(logical[1])
    assert isinstance(companion, TmccReq)
    assert companion.tmcc_command.address == 100
    assert companion.tmcc_command.command is command
    for complete in logical:
        assert buffer._packetize_multibyte_cmds(complete) is None
    fragments = queued(buffer)
    assert len(fragments) == 2 * word_count
    assert all(fragment[1] == PdiCommand.TMCC4_TX for fragment in fragments[:word_count])
    assert all(fragment[1] == PdiCommand.TMCC_TX for fragment in fragments[word_count:])
    # Parsing individual continuation words is inappropriate; framing/checksum validation is sufficient here.
    for fragment in fragments:
        unstuffed, checksum = PdiReq._calculate_checksum(fragment[1:-2], False)
        assert checksum == fragment[-2:-1]
        assert len(unstuffed[1:]) in (3, 7)
    with (
        patch.object(base3_module.CommandObserver, "offer") as observed,
        patch.object(Base3Buffer, "sync_state") as synced,
    ):
        for fragment in fragments:
            result = buffer._check_for_multibyte_packet(fragment)
            if result is not None:
                assert not isinstance(result, bytes)
                result.on_sent_last_packet()
        assert observed.call_count == synced.call_count == 2
    assert not buffer._mbc_registry


# Set up the minimum network-loop fields and queue to simulate exactly one failed transmission.
# noinspection PyProtectedMember
def test_broken_pipe_retry_does_not_expand_a_second_time(buffer, monkeypatch):
    source = packet()
    buffer.send(source)
    buffer._base3_addr = "127.0.0.1"
    buffer._base3_port = 5000
    buffer._is_running = True
    buffer._listener = None
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connections = 0

    def connect(_address):
        nonlocal connections
        connections += 1
        if connections == 2:
            buffer._is_running = False

    connection.connect.side_effect = connect
    connection.sendall.side_effect = BrokenPipeError("Simulated retry")
    monkeypatch.setattr(base3_module.socket, "socket", Mock(return_value=connection))
    monkeypatch.setattr(base3_module.select, "select", lambda *_args: ([buffer._send_queue], [], []))
    buffer.run()
    remaining = queued(buffer)
    assert len(remaining) == 2
    assert remaining[0] == bytes.fromhex("d1 27 f9 c9 e7 30 df")
    assert remaining[1] == source
    assert connection.sendall.call_count == 1


@pytest.mark.parametrize("labor", (17, 30, 31))
def test_stuffed_command_byte_does_not_hide_the_train_address(buffer, labor):
    source = packet(command=TMCC2EngineCommandEnum.ENGINE_LABOR, data=labor)
    buffer.send(source)
    output = queued(buffer)
    assert len(output) == 2
    assert output[0] == source
    companion = PdiReq.from_bytes(output[1])
    assert isinstance(companion, TmccReq)
    assert companion.tmcc_command.address == 100
    assert companion.tmcc_command.command is TMCC2EngineCommandEnum.ENGINE_LABOR
    assert companion.tmcc_command.data == labor


@pytest.mark.parametrize(
    "pdi_command",
    tuple(command for command in dict.fromkeys(PdiCommand.__members__.values()) if command != PdiCommand.TMCC4_TX),
)
def test_every_other_pdi_command_type_bypasses_sniffer_decoding(buffer, pdi_command):
    # A train-looking payload must not override the outer command type.
    source = bytes((0xD1, pdi_command, 0xF9, 1, 0xE7)) + b"0550" + bytes((0, 0xDF))
    with patch.object(
        ComponentStateStore, "pseudo_train_id_for_train", side_effect=AssertionError("Unexpected lookup")
    ):
        with patch.object(TmccReq, "__init__", side_effect=AssertionError("Unexpected conversion")):
            buffer.send(source)
    assert queued(buffer) == [source]


@pytest.mark.parametrize("prefix", (0xF8, 0xFB, 0xFE))
def test_only_train_command_prefix_can_trigger_companion(buffer, prefix):
    source = bytes((0xD1, 0x2C, prefix, 1, 0xE7)) + b"0550" + bytes((0, 0xDF))
    with patch.object(
        ComponentStateStore, "pseudo_train_id_for_train", side_effect=AssertionError("Unexpected lookup")
    ):
        with patch.object(TmccReq, "__init__", side_effect=AssertionError("Unexpected conversion")):
            buffer.send(source)
    assert queued(buffer) == [source]


def test_association_is_required_even_for_a_valid_four_digit_train(buffer):
    source = packet()
    ComponentStateStore.reset()
    with patch.object(TmccReq, "__init__", side_effect=AssertionError("Unexpected conversion")):
        buffer.send(source)
    assert queued(buffer) == [source]


# Check real stuffed bytes against the private packetizer, without transmitting anything.
# noinspection PyProtectedMember
def test_stuffed_f012_capture_is_recognized_as_a_multibyte_command(buffer):
    inner = bytes.fromhex(
        "f9 01 6f 30 35 35 30 fb 00 02 30 35 35 30 fb 00 12 30 35 35 30 "
        "fb 00 f0 30 35 35 30 fb 00 ef 30 35 35 30 fb 00 be 30 35 35 30 fb 00 de 30 35 35 30"
    )
    source = TmccReq(CommandReq.from_bytes(inner), PdiCommand(0x2C)).as_bytes
    assert bytes.fromhex("de de") in source
    buffer.send(source)
    originals = queued(buffer)
    assert len(originals) == 2
    assert buffer._packetize_multibyte_cmds(originals[0]) is None
    fragments = queued(buffer)
    assert len(fragments) == 7
    recovered = []
    for fragment in fragments:
        payload, checksum = PdiReq._calculate_checksum(fragment[1:-2], False)
        assert checksum == fragment[-2:-1]
        recovered.append(payload[1:])
    assert b"".join(recovered) == inner
