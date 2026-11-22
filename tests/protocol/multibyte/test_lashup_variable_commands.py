"""Documented train programming payloads decode without changing wire bytes."""

import pytest

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.multibyte.dcds_command_req import VariableCommandReq
from pytrain.protocol.multibyte.multibyte_constants import (
    TMCC2DcdsCommandEnum,
    TMCC2LashupCommandEnum,
    TMCC2RawVariableEnum,
    UnitAssignment,
)

from tests.protocol.multibyte.test_pseudo_train_commands import CAPTURED_RAW_COMMANDS, make_packet


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)


def variable_packet(command_id: int, payload: bytes, scope: CommandScope, address: int, d4: bool = False) -> bytes:
    prefix = 0xF9 if scope is CommandScope.TRAIN else 0xF8
    values = (0x6F, len(payload), command_id & 0xFF, command_id >> 8, *payload)
    packet = make_packet(prefix, 0 if d4 else address, values)
    if d4:
        packet = b"".join(packet[i : i + 3] + f"{address:04d}".encode() for i in range(0, len(packet), 3))
    return packet


@pytest.mark.parametrize(
    "unit, position, direction",
    (
        (0, "SINGLE", "FORWARD"),
        (1, "HEAD", "FORWARD"),
        (2, "MIDDLE", "FORWARD"),
        (3, "TAIL", "FORWARD"),
        (4, "SINGLE", "REVERSE"),
        (5, "HEAD", "REVERSE"),
        (6, "MIDDLE", "REVERSE"),
        (7, "TAIL", "REVERSE"),
    ),
)
@pytest.mark.parametrize(
    "scope, address, d4",
    (
        (CommandScope.ENGINE, 37, False),
        (CommandScope.TRAIN, 100, False),
        (CommandScope.ENGINE, 3233, True),
        (CommandScope.TRAIN, 550, True),
        (CommandScope.TRAIN, 100, True),
    ),
)
def test_assignment_decodes_all_positions_in_each_address_format(unit, position, direction, scope, address, d4):
    payload = b"0550" + bytes((unit,))
    packet = variable_packet(0xD000, payload, scope, address, d4)
    req = CommandReq.from_bytes(packet)
    assert isinstance(req, VariableCommandReq)
    assert req.command is TMCC2LashupCommandEnum.ASSIGN_TRAIN
    assert req.assigned_train_id == 550
    assert req.unit_assignment is UnitAssignment(unit)
    assert f"ASSIGN_TRAIN TRAIN 0550 {position} {direction}" in repr(req)
    assert "ID 0xD000 DATA 30 35 35 30" in repr(req)
    assert req.address == address
    assert req.scope is scope
    assert req.is_tmcc4 is d4
    assert req.is_pseudo_train is (scope is CommandScope.TRAIN and address == 100 and not d4)
    assert not req.is_noop
    assert req.as_bytes == packet
    assert req.num_bytes == len(packet)


@pytest.mark.parametrize("entry", CAPTURED_RAW_COMMANDS[:2])
def test_train_level_clear_reassignment_uses_payload_id_not_destination(entry):
    req = CommandReq.from_bytes(bytes.fromhex(entry[0]))
    assert isinstance(req, VariableCommandReq)
    assert req.address in (100, 550)
    assert req.assigned_train_id == 1
    assert req.unit_assignment is UnitAssignment.SINGLE_FORWARD
    assert "ASSIGN_TRAIN TRAIN 0001 SINGLE FORWARD" in repr(req)


@pytest.mark.parametrize("address, d4", ((100, False), (127, False), (100, True), (550, True)))
@pytest.mark.parametrize("from_rx", (False, True))
def test_road_speed_requires_documented_magic_payload(address: int, d4: bool, from_rx: bool):
    packet = variable_packet(0xF012, b"\xef\xbe", CommandScope.TRAIN, address, d4)
    req = CommandReq.from_bytes(packet, from_tmcc_rx=from_rx)
    assert isinstance(req, VariableCommandReq)
    assert req.command is TMCC2LashupCommandEnum.ROAD_SPEED
    assert req.lashup_command is TMCC2LashupCommandEnum.ROAD_SPEED
    assert req.assigned_train_id is None
    assert req.unit_assignment is None
    assert "ROAD_SPEED ID 0xF012 DATA EF BE" in repr(req)
    assert req.is_tmcc_rx is from_rx
    assert not req.is_noop
    assert req.as_bytes == packet


@pytest.mark.parametrize(
    "command_id, payload",
    (
        (0xD000, b"0"),
        (0xD000, b"0550"),
        (0xD000, b"0550\x00\x00"),
        (0xD000, b"05X0\x01"),
        (0xD000, b"\xff550\x01"),
        (0xD000, b"0550\x08"),
        (0xD000, b"0550\x80"),
        (0xF012, b"\xbe\xef"),
        (0xF012, b"\xef\xbf"),
        (0xF012, b"\xef\xbe\x00"),
        (0xF012, b"\x00"),
    ),
)
def test_undocumented_payloads_stay_raw_and_lossless(command_id: int, payload: bytes):
    packet = variable_packet(command_id, payload, CommandScope.TRAIN, 100)
    req = CommandReq.from_bytes(packet)
    assert isinstance(req, VariableCommandReq)
    assert isinstance(req.command, TMCC2RawVariableEnum)
    assert req.lashup_command is None
    assert req.assigned_train_id is None
    assert req.unit_assignment is None
    assert req.is_noop
    assert "VARIABLE ID" in repr(req)
    assert "ASSIGN_TRAIN" not in repr(req)
    assert "ROAD_SPEED" not in repr(req)
    assert bytes(req.data_bytes) == payload
    assert req.as_bytes == packet
    assert req.num_bytes == len(packet)


def test_road_speed_in_engine_space_keeps_raw_fallback():
    packet = variable_packet(0xF012, b"\xef\xbe", CommandScope.ENGINE, 37)
    req = CommandReq.from_bytes(packet)
    assert isinstance(req, VariableCommandReq)
    assert req.command is TMCC2RawVariableEnum.RAW_F012
    assert req.lashup_command is None
    assert req.as_bytes == packet


@pytest.mark.parametrize("default_data", (None, 0))
def test_factory_default_builds_ef_be_payload_and_correct_checksum(default_data):
    req = VariableCommandReq.build(TMCC2DcdsCommandEnum.FACTORY_DEFAULT, 37, default_data, CommandScope.ENGINE)
    expected = variable_packet(0xF000, b"\xef\xbe", CommandScope.ENGINE, 37)
    assert bytes(req.data_bytes) == b"\xef\xbe"
    assert req.as_bytes == expected
    decoded = CommandReq.from_bytes(expected)
    assert isinstance(decoded, VariableCommandReq)
    assert decoded.command is TMCC2DcdsCommandEnum.FACTORY_DEFAULT
    assert bytes(decoded.data_bytes) == b"\xef\xbe"
    assert decoded.as_bytes == expected


def test_common_builder_uses_factory_default_definition():
    req = CommandReq.build(TMCC2DcdsCommandEnum.FACTORY_DEFAULT, 37)
    assert isinstance(req, VariableCommandReq)
    assert req.as_bytes == variable_packet(0xF000, b"\xef\xbe", CommandScope.ENGINE, 37)


def test_fixed_defaults_are_copied_into_requests():
    first = VariableCommandReq.build(TMCC2DcdsCommandEnum.FACTORY_DEFAULT, 37)
    data = first.data_bytes
    assert isinstance(data, list)
    data[0] = 0
    second = VariableCommandReq.build(TMCC2DcdsCommandEnum.FACTORY_DEFAULT, 37)
    assert bytes(second.data_bytes) == b"\xef\xbe"
    assert TMCC2DcdsCommandEnum.FACTORY_DEFAULT.value.data_bytes == [0xEF, 0xBE]


def test_road_speed_builder_uses_magic_payload_by_default():
    req = CommandReq.build(TMCC2LashupCommandEnum.ROAD_SPEED, 37, scope=CommandScope.TRAIN)
    assert isinstance(req, VariableCommandReq)
    assert req.as_bytes == variable_packet(0xF012, b"\xef\xbe", CommandScope.TRAIN, 37)


@pytest.mark.parametrize("payload", (b"0550\x08", b"05X0\x00", b"0550"))
def test_typed_assignment_builder_rejects_unsupported_payloads(payload: bytes):
    with pytest.raises(ValueError, match="Invalid payload or scope"):
        VariableCommandReq.build(TMCC2LashupCommandEnum.ASSIGN_TRAIN, 37, payload, CommandScope.ENGINE)


def test_payload_mutation_removes_semantic_claim_but_keeps_bytes():
    packet = variable_packet(0xD000, b"0550\x01", CommandScope.TRAIN, 100)
    req = CommandReq.from_bytes(packet)
    assert isinstance(req, VariableCommandReq)
    data = req.data_bytes
    assert isinstance(data, list)
    data[2] = ord("X")
    assert req.assigned_train_id is None
    assert req.unit_assignment is None
    assert "VARIABLE ID" in repr(req)
    assert req.as_bytes == variable_packet(0xD000, b"05X0\x01", CommandScope.TRAIN, 100)
