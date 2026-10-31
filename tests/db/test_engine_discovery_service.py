"""Engine discovery coordinator regression contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_discovery_service import EngineDiscoveryService
from src.pytrain.pdi.ble_req import BleReq
from src.pytrain.pdi.constants import PdiCommand
from src.pytrain.protocol.constants import CommandScope


@pytest.fixture
def discovery(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "is_built", lambda: True)
    state = {"value": None}
    monkeypatch.setattr(
        ComponentStateStore,
        "get_state",
        lambda scope, address, create=False: state["value"],
    )
    callback = Mock()
    return EngineDiscoveryService(callback), state, callback


def test_existing_engine_does_not_enter_discovery(discovery):
    service, state, callback = discovery
    state["value"] = SimpleNamespace(is_deleted=False, comp_data=object())
    service.request_discovery(37)
    callback.assert_not_called()


def test_placeholder_without_database_record_is_not_existing(discovery):
    service, state, callback = discovery
    state["value"] = SimpleNamespace(is_deleted=False, comp_data=None)
    assert service.request_discovery(37)
    callback.assert_called_once_with(37)


def test_duplicate_requests_from_multiple_sources_are_suppressed(discovery):
    service, _, callback = discovery
    assert service.request_discovery(37)
    assert not service.request_discovery(37)
    callback.assert_called_once_with(37)
    service.complete(37)
    assert service.request_discovery(37)
    assert callback.call_count == 2


@pytest.mark.parametrize(
    "packet_hex",
    [
        "d176001225ff54df",
        "d1760012000030373337a7df",
    ],
)
def test_ble_programming_requests_discovery(discovery, packet_hex):
    service, _, callback = discovery
    notification = BleReq(bytes.fromhex(packet_hex), PdiCommand.BLE_RX)
    service(notification)
    callback.assert_called_once_with(notification.tmcc_id)


def test_ble_programming_existing_engine_is_ignored(discovery):
    service, state, callback = discovery
    state["value"] = SimpleNamespace(is_deleted=False, comp_data=object())
    service(BleReq(bytes.fromhex("d176001225ff54df"), PdiCommand.BLE_RX))
    callback.assert_not_called()


def test_callback_failure_releases_pending_slot(discovery):
    service, _, callback = discovery
    callback.side_effect = [RuntimeError("failed"), None]
    with pytest.raises(RuntimeError, match="failed"):
        service.request_discovery(37)
    assert service.request_discovery(37)
    assert callback.call_count == 2


def test_invalid_addresses_are_ignored(discovery):
    service, _, callback = discovery
    assert not service.request_discovery(0)
    assert not service.request_discovery(10000)
    callback.assert_not_called()
