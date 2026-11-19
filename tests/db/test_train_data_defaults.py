"""Verify default initialization and parsing use the four-digit train schema."""

import pytest

from src.pytrain.db.comp_data import BASE_MEMORY_D4_TRAIN_READ_MAP, TrainData
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import CommandScope


@pytest.mark.parametrize("tmcc_id", [100, 1234, 9999])
def test_four_digit_train_defaults_initialize_pseudo_id_and_empty_consist(tmcc_id):
    train = TrainData(None, tmcc_id=tmcc_id)
    expected_default = BASE_MEMORY_D4_TRAIN_READ_MAP[0xB6].default
    assert train.pseudo_train_id == expected_default
    assert train.record_type == 3
    assert train.consist_comps is None
    assert train.tmcc_id == tmcc_id
    packet = train.as_bytes()
    assert len(packet) == PdiReq.scope_record_length(CommandScope.TRAIN)
    assert packet[0xB6] == expected_default
    assert packet[0x6E:0xAE] == b"\xff" * 64


@pytest.mark.parametrize("tmcc_id", [1, 99])
def test_two_digit_train_defaults_preserve_regular_consist_layout(tmcc_id):
    train = TrainData(None, tmcc_id=tmcc_id)
    assert train.record_type == 3
    assert train.consist_comps is None
    assert train.as_bytes()[0x70:0x90] == b"\xff" * 32


@pytest.mark.parametrize("tmcc_id", [None, 1234])
def test_four_digit_train_parses_pseudo_id_with_or_without_explicit_address(tmcc_id):
    packet = bytearray(TrainData(None, tmcc_id=1234).as_bytes())
    packet[0xB6] = 100
    parsed = TrainData(bytes(packet), tmcc_id=tmcc_id)
    assert parsed.pseudo_train_id == 100
    assert parsed.as_bytes()[0xB6] == 100
