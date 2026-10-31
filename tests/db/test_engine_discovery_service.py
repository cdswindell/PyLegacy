"""Engine discovery coordinator regression contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_discovery_service import EngineDiscoveryService, four_digit_map_request
from src.pytrain.pdi.ble_req import BleReq
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


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


@pytest.mark.parametrize(
    "command",
    [
        TMCC1EngineCommandEnum.SET_ADDRESS,
        TMCC2EngineCommandEnum.SET_ADDRESS,
    ],
)
def test_set_address_discovers_unknown_engine(discovery, command):
    service, _, callback = discovery
    request = CommandReq.build(command, address=37, scope=CommandScope.ENGINE)
    service.on_command(request)
    callback.assert_called_once_with(37)


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


@pytest.mark.parametrize("tmcc_id", [100, 101, 737, 9999])
def test_four_digit_map_request(tmcc_id):
    request = four_digit_map_request(tmcc_id)
    assert request.pdi_command == PdiCommand.D4_ENGINE
    assert request.action == D4Action.MAP
    assert request.record_no == 0
    assert request.tmcc_id == tmcc_id
    assert request.as_bytes.startswith(bytes.fromhex("d12e"))


@pytest.mark.parametrize("tmcc_id", [0, 37, 99, 10000])
def test_four_digit_map_request_rejects_non_d4_address(tmcc_id):
    with pytest.raises(ValueError, match="between 100 and 9999"):
        four_digit_map_request(tmcc_id)
