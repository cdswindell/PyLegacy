import pytest

from src.pytrain.pdi.ble_req import BleReq
from src.pytrain.pdi.constants import PdiCommand
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import CommandScope


@pytest.mark.parametrize(
    ("packet_hex", "tmcc_id"),
    [
        ("d1760012000030373337a7df", 737),
        ("d176001225ff54df", 37),
    ],
)
def test_ble_programming_notification(packet_hex, tmcc_id):
    packet = bytes.fromhex(packet_hex)
    req = PdiReq.from_bytes(packet)
    assert isinstance(req, BleReq)
    assert req.pdi_command == PdiCommand.BLE_RX
    assert req.is_programming
    assert req.tmcc_id == tmcc_id
    assert req.scope == CommandScope.ENGINE
    assert req.as_bytes == packet
    assert req.payload_bytes == packet[2:-2]
