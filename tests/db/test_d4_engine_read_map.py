"""Decode the 4D engine train reference while preserving adjacent unknown bytes."""

import pytest

from src.pytrain.db.comp_data import BASE_MEMORY_ENGINE_READ_MAP, CompData, EngineData, TrainData
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.protocol.constants import CommandScope


def engine_record(address: int = 3233, reference: bytes = b"\x00\x00\x01\x00") -> bytes:
    record = bytearray(b"\xff" * 192)
    record[2] = 0x0E
    record[0x1C] = 37
    record[0x1E] = record[0x3E] = 0
    record[0xB4:0xB8] = reference
    record[0xB8:0xBC] = f"{address:04d}".encode()
    record[0xBC:0xC0] = bytes(4)
    return bytes(record)


@pytest.mark.parametrize(
    "reference, expected_record",
    (
        (bytes.fromhex("00 00 01 00"), 0),
        (bytes.fromhex("01 00 00 00"), 1),
        (bytes.fromhex("ff ff ff 00"), 0xFFFF),
        (bytes.fromhex("34 12 a5 5a"), 0x1234),
    ),
)
def test_d4_engine_reference_decodes_little_endian_and_round_trips(reference: bytes, expected_record: int):
    record = engine_record(reference=reference)
    data = CompData.from_bytes(record, CommandScope.ENGINE)
    assert isinstance(data, EngineData)
    assert data.train_record_no == expected_record
    assert data.train_tmcc_id == 37
    assert data.unk_b6 == reference[2]
    assert data.unk_b7 == reference[3]
    assert data.as_bytes() == record


@pytest.mark.parametrize("address", (21, 100, 127, 737, 3233, 9999))
def test_d4_channel_retains_layout_for_real_four_digit_engine_addresses(address: int):
    record = engine_record(address)
    data = CompData.from_bytes(record, CommandScope.ENGINE)
    assert isinstance(data, EngineData)
    assert data.tmcc_id == address
    assert data.train_record_no == 0
    assert data.as_bytes() == record


def test_changing_train_record_reference_preserves_unknown_bytes_and_one_byte_assignment():
    record = engine_record(reference=bytes.fromhex("34 12 a5 5a"))
    data = CompData.from_bytes(record, CommandScope.ENGINE)
    assert isinstance(data, EngineData)
    data.train_record_no = 0xABCD
    updated = data.as_bytes()
    assert updated[0xB4:0xB8] == bytes.fromhex("cd ab a5 5a")
    assert updated[:0xB4] == record[:0xB4]
    assert updated[0xB6:] == record[0xB6:]
    assert data.train_tmcc_id == 37


@pytest.mark.parametrize("address", (37, 3233))
def test_defaults_only_include_d4_reference_for_four_digit_engines(address: int):
    data = EngineData(None, address)
    assert data.train_record_no == (0xFFFF if address > 99 else None)
    assert data.unk_b6 == (0xFF if address > 99 else None)
    assert data.unk_b7 == (0xFF if address > 99 else None)
    assert data.as_bytes()[0xB4:0xB8] == bytes.fromhex("ff ff ff ff")


def test_two_digit_engine_record_uses_standard_map_and_one_byte_train_assignment():
    record = engine_record(reference=bytes.fromhex("34 12 a5 5a"))
    data = CompData.from_bytes(record, CommandScope.ENGINE, tmcc_id=37)
    assert isinstance(data, EngineData)
    assert data.tmcc_id == 37
    assert data.train_tmcc_id == 37
    assert data.train_record_no is None
    assert data.unk_b6 is None
    assert data.unk_b7 is None
    serialized = data.as_bytes()
    assert serialized[0x1C] == 37
    assert serialized[0xB4:0xC0] == b"\xff" * 12


def test_full_d4_response_exposes_reference_and_preserves_it_during_state_serialization():
    record = engine_record(reference=bytes.fromhex("34 12 01 00"))
    packet = D4Req(1, PdiCommand(0x2E), D4Action.QUERY, start=0, data_length=192, data_bytes=record, timestamp=0)
    decoded = D4Req(packet.as_bytes)
    data = decoded.comp_data
    assert isinstance(data, EngineData)
    assert decoded.tmcc_id == 3233
    assert data.train_record_no == 0x1234
    assert data.as_bytes() == record


def test_d4_train_pseudo_id_stays_separate_from_engine_reference_map():
    train = TrainData(None, 550)
    train.pseudo_train_id = 100
    train.timestamp = 0x12345678
    train.train_record_no = 0x1234
    record = train.as_bytes()
    assert record[0xB4:0xB8] == bytes.fromhex("ff ff 64 ff")
    decoded = CompData.from_bytes(record, CommandScope.TRAIN)
    assert isinstance(decoded, TrainData)
    assert decoded.pseudo_train_id == 100
    assert decoded.tmcc_id == 550
    assert decoded.timestamp == 0x12345678
    assert decoded.train_record_no is None
    assert decoded.unk_b6 is None


def test_standard_engine_map_contains_no_d4_only_fields():
    assert not any(handler.is_d4_only for handler in BASE_MEMORY_ENGINE_READ_MAP.values())
    assert not ({0xB4, 0xB6, 0xB7, 0xB8, 0xBC} & BASE_MEMORY_ENGINE_READ_MAP.keys())


@pytest.mark.parametrize(
    "command, offset, value, expected",
    (
        (PdiCommand(0x2E), 0xB4, bytes.fromhex("34 12"), "4660"),
        (PdiCommand(0x2E), 0xB8, b"3233", "3233"),
        (PdiCommand(0x2E), 0xBC, bytes.fromhex("78 56 34 12"), "305419896"),
        (PdiCommand(0x2F), 0xB8, b"0550", "550"),
        (PdiCommand(0x2F), 0xB6, b"\x64", "100"),
    ),
)
def test_partial_d4_response_formats_fields_with_its_specific_map(command, offset: int, value: bytes, expected: str):
    packet = D4Req(1, command, D4Action.QUERY, start=offset, data_length=len(value), data_bytes=value, timestamp=0)
    decoded = D4Req(packet.as_bytes)
    assert f"Data: {expected}" in decoded.payload
