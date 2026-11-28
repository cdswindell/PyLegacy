"""Verify explicit packet layouts and backward-compatible direct construction."""

from unittest.mock import Mock

import pytest

from src.pytrain.db.comp_data import CompData, EngineData, SCOPE_TO_CLEARED_MAP, TrainData
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, PDI_EOP, PDI_SOP, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import CommandScope


DATA_CLASSES = [(EngineData, CommandScope.ENGINE), (TrainData, CommandScope.TRAIN)]


def layout_record(scope: CommandScope, address: int, d4: bool) -> bytes:
    record = bytearray(b"\xff" * 192)
    record[2] = 3 if scope == CommandScope.TRAIN else 4
    record[0x1E] = record[0x3E] = 0
    if scope == CommandScope.TRAIN:
        record[0x6D if d4 else 0x6F] = 0x12
        if d4:
            record[0xB6] = 100
    elif d4:
        record[0xB4:0xB8] = b"\x34\x12\x03\x5a"
    if d4:
        record[0xB8:0xBC] = f"{address:04d}".encode("ascii")
    return bytes(record)


@pytest.mark.parametrize("data_cls, scope", DATA_CLASSES)
@pytest.mark.parametrize("address, d4", [(1, True), (99, True), (100, False), (1234, False), (9999, False)])
def test_explicit_layout_overrides_address_for_defaults_and_serialization(data_cls, scope, address, d4):
    component = data_cls(None, address, d4=d4)

    assert component.tmcc_id == address
    if scope == CommandScope.ENGINE:
        assert component.train_record_no == (0xFFFF if d4 else None)
        assert component.train_unit_4d == (0xFF if d4 else None)
    else:
        assert component.pseudo_train_id == (0xFF if d4 else None)
        component.consist_flags = 0x12
    packet = component.as_bytes()
    assert len(packet) == 192
    if d4:
        assert packet[0xB8:0xBC] == f"{address:04d}".encode("ascii")
    else:
        assert packet[0xB4:0xC0] == b"\xff" * 12
    if scope == CommandScope.TRAIN:
        assert packet[0x6D if d4 else 0x6F] == 0x12


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("address, d4", [(1, True), (99, True), (100, False), (1234, False)])
def test_factory_forwards_explicit_layout_for_parsing_and_round_trip(scope, address, d4):
    record = layout_record(scope, address, d4)

    component = CompData.from_bytes(record, scope, tmcc_id=address, d4=d4)

    assert isinstance(component, (EngineData, TrainData))
    assert component.tmcc_id == address
    if scope == CommandScope.ENGINE:
        assert component.train_record_no == (0x1234 if d4 else None)
    else:
        assert component.consist_flags == 0x12
        assert component.pseudo_train_id == (100 if d4 else None)
    assert component.as_bytes() == record


@pytest.mark.parametrize("data_cls, scope", DATA_CLASSES)
@pytest.mark.parametrize("address", [None, 0, 1, 99, 100, 1234, 9999])
def test_direct_constructor_retains_layout_inference(data_cls, scope, address):
    component = data_cls(None, address)
    expected_d4 = address is None or address >= 100

    if scope == CommandScope.ENGINE:
        assert component.train_record_no == (0xFFFF if expected_d4 else None)
    else:
        assert component.pseudo_train_id == (0xFF if expected_d4 else None)
    if address is None:
        component.tmcc_id = 21
    packet = component.as_bytes()
    expected_id = f"{component.tmcc_id:04d}".encode("ascii") if expected_d4 else b"\xff" * 4
    assert packet[0xB8:0xBC] == expected_id
    if address == 0:
        assert packet == SCOPE_TO_CLEARED_MAP[scope]


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("address", [21, 100])
def test_base_memory_reader_explicitly_selects_standard_layout(monkeypatch, scope, address):
    record = layout_record(scope, address, d4=False)
    packet = BaseReq(
        address, PdiCommand.BASE_MEMORY, flags=0xC2, scope=scope, start=0, data_length=192, data_bytes=record
    ).as_bytes
    factory = Mock(wraps=CompData.from_bytes)
    monkeypatch.setattr(CompData, "from_bytes", factory)

    decoded = BaseReq(packet)

    factory.assert_called_once_with(record, scope=scope, tmcc_id=address, d4=False)
    component = decoded.comp_data
    assert isinstance(component, (EngineData, TrainData))
    assert component.tmcc_id == address
    assert component.as_bytes() == record


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("address", [1, 1234])
@pytest.mark.parametrize("action", [D4Action.QUERY, D4Action.UPDATE, D4Action.NEXT_REC])
def test_d4_readers_explicitly_select_d4_layout(monkeypatch, scope, address, action):
    record = layout_record(scope, address, d4=True)
    command = PdiCommand.D4_ENGINE if scope == CommandScope.ENGINE else PdiCommand.D4_TRAIN
    # The four bytes after the length are timestamp bytes for QUERY/UPDATE and
    # next-record metadata for NEXT_REC. Both response layouts carry the record at offset 12.
    payload = command.as_bytes + b"\x07\x00" + action.as_bytes + b"\x00\x00\x00\xc0" + bytes(4) + record
    # Use the framing helper to construct a complete response independently of D4Req decoding.
    # noinspection PyProtectedMember
    stuffed, checksum = PdiReq._calculate_checksum(payload)
    packet = bytes([PDI_SOP]) + stuffed + checksum + bytes([PDI_EOP])
    factory = Mock(wraps=CompData.from_bytes)
    monkeypatch.setattr(CompData, "from_bytes", factory)

    decoded = D4Req(packet)

    factory.assert_called_once_with(record, scope, d4=True)
    assert decoded.tmcc_id == address
    component = decoded.comp_data
    assert isinstance(component, (EngineData, TrainData))
    assert component.as_bytes() == record
