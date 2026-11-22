"""Regression coverage for Cab 3 pseudo trains and variable command decoding."""

import pytest

from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.multibyte.dcds_command_req import VariableCommandReq
from pytrain.protocol.multibyte.multibyte_command_req import MultiByteReq
from pytrain.protocol.multibyte.multibyte_constants import TMCC2LashupCommandEnum, TMCC2RawVariableEnum
from pytrain.protocol.multibyte.param_command_req import ParameterCommandReq
from pytrain.protocol.multibyte.r4lc_command_req import R4LCCommandReq


CAPTURED_RAW_COMMANDS = (
    (
        "f9c96ffbc905fbc900fbc9d0fbc930fbc930fbc930fbc931fbc900fbc920",
        CommandScope.TRAIN,
        100,
        0xD000,
        b"0001\x00",
    ),
    (
        "f9016f30353530fb000530353530fb000030353530fb00d030353530fb003030353530"
        "fb003030353530fb003030353530fb003130353530fb000030353530fb00f930353530",
        CommandScope.TRAIN,
        550,
        0xD000,
        b"0001\x00",
    ),
    (
        "f8016f33323333fb000533323333fb000033323333fb00d033323333fb003033323333"
        "fb003533323333fb003533323333fb003033323333fb000133323333fb00ef33323333",
        CommandScope.ENGINE,
        3233,
        0xD000,
        b"0550\x01",
    ),
    (
        "f9c96ffbc902fbc912fbc9f0fbc9effbc9befbc960",
        CommandScope.TRAIN,
        100,
        0xF012,
        bytes.fromhex("EF BE"),
    ),
    (
        "f9016f30353530fb000230353530fb001230353530fb00f030353530fb00ef30353530fb00be30353530fb00de30353530",
        CommandScope.TRAIN,
        550,
        0xF012,
        bytes.fromhex("EF BE"),
    ),
)


def make_packet(prefix: int, address: int, values: tuple[int, ...]) -> bytes:
    """Build three-byte words with an independent ones-complement checksum."""
    continuation_address = address << 1 | (prefix == 0xF9)
    packet = bytes((prefix, address << 1 | 1, values[0]))
    packet += b"".join(bytes((0xFB, continuation_address, value)) for value in values[1:])
    checksum = ~(sum(packet[i] + packet[i + 1] for i in range(1, len(packet), 3)) + continuation_address) & 0xFF
    return packet + bytes((0xFB, continuation_address, checksum))


@pytest.mark.parametrize("parser", (CommandReq, MultiByteReq, VariableCommandReq))
@pytest.mark.parametrize("from_tmcc_rx", (False, True))
@pytest.mark.parametrize("hex_packet,scope,address,command_id,payload", CAPTURED_RAW_COMMANDS)
def test_captured_variable_ids_and_payloads(
    parser, from_tmcc_rx: bool, hex_packet: str, scope: CommandScope, address: int, command_id: int, payload: bytes
):
    packet = bytes.fromhex(hex_packet)
    req = parser.from_bytes(packet, from_tmcc_rx=from_tmcc_rx)

    assert isinstance(req, VariableCommandReq)
    assert req.scope is scope
    assert req.address == address
    assert req.command_id == command_id
    assert bytes(req.data_bytes) == payload
    assert req.as_bytes == packet
    assert req.num_bytes == len(packet)
    assert req.is_tmcc_rx is from_tmcc_rx
    assert req.is_pseudo_train is (address == 100)
    assert req.is_tmcc4 is (address > 127)
    assert not req.is_noop
    expected = TMCC2LashupCommandEnum.ASSIGN_TRAIN if command_id == 0xD000 else TMCC2LashupCommandEnum.ROAD_SPEED
    assert req.command is expected
    assert f"ID 0x{command_id:04X} DATA {payload.hex(' ').upper()}" in repr(req)


@pytest.mark.parametrize("address", range(100, 128))
@pytest.mark.parametrize("prefix", (0xF8, 0xF9))
@pytest.mark.parametrize(
    "parser,values",
    (
        (CommandReq, (0x76, 0)),
        (MultiByteReq, (0x76, 0)),
        (ParameterCommandReq, (0x76, 0)),
        (R4LCCommandReq, (0x43, 2)),
        (VariableCommandReq, (0x6F, 2, 0x12, 0xF0, 0xEF, 0xBE)),
    ),
)
def test_seven_bit_pseudo_addresses_are_only_accepted_for_trains(
    address: int, prefix: int, parser, values: tuple[int, ...]
):
    packet = make_packet(prefix, address, values)
    if prefix == 0xF8:
        with pytest.raises(AttributeError, match="Cannot decode address from bytes"):
            parser.from_bytes(packet)
    else:
        req = parser.from_bytes(packet)
        assert isinstance(req, MultiByteReq)
        assert req.address == address
        assert req.scope is CommandScope.TRAIN
        assert req.is_pseudo_train
        assert not req.is_tmcc4
        assert req.as_bytes == packet
        assert req.num_bytes == len(packet)


@pytest.mark.parametrize("address", (100, 127))
def test_single_word_engine_commands_reject_pseudo_addresses(address):
    with pytest.raises(AttributeError, match="Cannot decode address from bytes"):
        CommandReq.from_bytes(bytes((0xF8, address << 1, 0)))
    req = CommandReq.from_bytes(bytes((0xF9, address << 1, 0)))
    assert req.address == address
    assert req.scope is CommandScope.TRAIN


@pytest.mark.parametrize("address", (1, 99))
@pytest.mark.parametrize("prefix", (0xF8, 0xF9))
def test_ordinary_multibyte_addresses_keep_their_wire_format(address, prefix):
    packet = make_packet(prefix, address, (0x76, 0))
    req = CommandReq.from_bytes(packet)
    assert isinstance(req, MultiByteReq)
    assert req.address == address
    assert not req.is_pseudo_train
    assert not req.is_tmcc4
    assert req.as_bytes == packet


@pytest.mark.parametrize("address", (100, 127, 550))
@pytest.mark.parametrize("prefix", (0xF8, 0xF9))
def test_four_digit_addresses_are_distinct_from_pseudo_trains(address: int, prefix: int):
    template = make_packet(prefix, 0, (0x76, 0))
    packet = b"".join(template[i : i + 3] + f"{address:04d}".encode() for i in range(0, len(template), 3))
    req = CommandReq.from_bytes(packet)
    assert isinstance(req, MultiByteReq)
    assert req.address == address
    assert req.is_tmcc4
    assert not req.is_pseudo_train
    assert req.as_bytes == packet
    assert req.num_bytes == len(packet)


@pytest.mark.parametrize("command_id", (0xD000, 0xF012))
@pytest.mark.parametrize("payload", (b"\x00", b"\x00\xff\xde\xdf\xf8\xf9\xfb"))
def test_raw_variable_payload_is_not_interpreted_or_replaced(command_id, payload):
    values = (0x6F, len(payload), command_id & 0xFF, command_id >> 8, *payload)
    packet = make_packet(0xF9, 127, values)
    req = CommandReq.from_bytes(packet)
    assert isinstance(req, VariableCommandReq)
    assert req.command_id == command_id
    assert bytes(req.data_bytes) == payload
    assert req.as_bytes == packet
    assert req.num_bytes == len(packet)
    assert isinstance(req.command, TMCC2RawVariableEnum)
    assert req.is_noop
    assert "VARIABLE ID" in repr(req)


@pytest.mark.parametrize("values", ((0x76, 0), (0x43, 2), (0x6F, 2, 0x12, 0xF0, 0xEF, 0xBE)))
def test_pseudo_train_commands_reject_bad_checksums(values: tuple[int, ...]):
    packet = make_packet(0xF9, 100, values)
    with pytest.raises(ValueError, match="checksum"):
        CommandReq.from_bytes(packet[:-1] + bytes((packet[-1] ^ 1,)))


def test_raw_variable_command_rejects_mismatched_payload_length():
    packet = make_packet(0xF9, 100, (0x6F, 3, 0x12, 0xF0, 0xEF, 0xBE))
    with pytest.raises(ValueError, match="Command requires"):
        CommandReq.from_bytes(packet)


def test_decoded_bytes_do_not_hide_a_changed_address():
    req = CommandReq.from_bytes(make_packet(0xF9, 100, (0x76, 0)))
    assert isinstance(req, MultiByteReq)
    req.address = 101
    # With no indexed pseudo association, the new destination uses four-digit addressing.
    assert req.uses_d4_address
    assert req.as_bytes == bytes.fromhex("f9 01 76 30 31 30 31 fb 01 00 30 31 30 31 fb 01 86 30 31 30 31")


def test_raw_variable_command_rebuilds_after_payload_change():
    req = CommandReq.from_bytes(bytes.fromhex(CAPTURED_RAW_COMMANDS[0][0]))
    assert isinstance(req, VariableCommandReq)
    payload = req.data_bytes
    assert isinstance(payload, list)
    payload[0] = 0x31
    assert req.command is TMCC2LashupCommandEnum.ASSIGN_TRAIN
    assert req.as_bytes == make_packet(0xF9, 100, (0x6F, 5, 0, 0xD0, *b"1001\x00"))
