from unittest.mock import Mock

import pytest

from src.pytrain.db.engine_discovery_service import EngineDiscoveryService
from src.pytrain.pdi.ble_req import BleReq
from src.pytrain.pdi.constants import PdiCommand
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import CommandScope


@pytest.mark.parametrize(
    ("packet_hex", "tmcc_id", "record_no"),
    [
        ("d1760012000030373337a7df", 737, 0),
        ("d176001225ff54df", 37, 0xFFFF),
    ],
)
def test_ble_programming_notification(packet_hex, tmcc_id, record_no):
    packet = bytes.fromhex(packet_hex)
    req = PdiReq.from_bytes(packet)
    assert isinstance(req, BleReq)
    assert req.pdi_command == PdiCommand.BLE_RX
    assert req.is_programming
    assert req.tmcc_id == tmcc_id
    assert req.record_no == record_no
    assert req.scope == CommandScope.ENGINE
    assert req.as_bytes == packet
    assert req.payload_bytes == packet[2:-2]


def test_exact_short_no_address_response_is_not_a_programming_notification():
    packet = bytes.fromhex("d1760212ffff78df")
    req = PdiReq.from_bytes(packet)
    assert isinstance(req, BleReq)
    assert not req.is_programming
    assert req.tmcc_id == 0
    assert req.scope == CommandScope.SYSTEM
    assert req.payload_bytes == bytes.fromhex("0212ffff")
    assert req.as_bytes == packet


def test_short_no_address_response_does_not_match_longer_notifications():
    packet = bytes.fromhex("d1760212ffff30373337a7df")
    req = PdiReq.from_bytes(packet)
    assert isinstance(req, BleReq)
    # Preserve the existing interpretation of longer responses until their format is confirmed.
    assert req.is_programming
    assert req.tmcc_id == 737
    assert req.record_no == 0xFFFF
    assert req.as_bytes == packet


def test_short_no_address_response_skips_discovery_and_next_valid_notification_still_works(monkeypatch):
    service = EngineDiscoveryService(Mock())
    request = Mock()
    monkeypatch.setattr(service, "request_discovery", request)
    service(BleReq(bytes.fromhex("d1760212ffff78df")))
    request.assert_not_called()
    service(BleReq(bytes.fromhex("d17600121fff5adf")))
    request.assert_called_once_with(31)
