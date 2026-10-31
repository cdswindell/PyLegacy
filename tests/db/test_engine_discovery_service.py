"""Engine discovery coordinator regression contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_discovery_service import EngineDiscoveryService
from src.pytrain.pdi.ble_req import BleReq
from src.pytrain.pdi.constants import PdiCommand
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
    request = CommandReq.build(command, address=737, scope=CommandScope.ENGINE)
    service.on_command(request)
    callback.assert_called_once_with(737)


def test_existing_engine_does_not_enter_discovery(discovery):
    service, state, callback = discovery
    state["value"] = SimpleNamespace(is_deleted=False, comp_data=object())
    service.request_discovery(737)
    callback.assert_not_called()


def test_placeholder_without_database_record_is_not_existing(discovery):
    service, state, callback = discovery
    state["value"] = SimpleNamespace(is_deleted=False, comp_data=None)
    assert service.request_discovery(737)
    callback.assert_called_once_with(737)


def test_duplicate_requests_from_multiple_sources_are_suppressed(discovery):
    service, _, callback = discovery
    assert service.request_discovery(737)
    assert not service.request_discovery(737)
    callback.assert_called_once_with(737)
    service.complete(737)
    assert service.request_discovery(737)
    assert callback.call_count == 2


@pytest.mark.parametrize(
    "packet_hex",
    [
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
    service(BleReq(bytes.fromhex("d1760012000030373337a7df"), PdiCommand.BLE_RX))
    callback.assert_not_called()


def test_callback_failure_releases_pending_slot(discovery):
    service, _, callback = discovery
    callback.side_effect = [RuntimeError("failed"), None]
    with pytest.raises(RuntimeError, match="failed"):
        service.request_discovery(737)
    assert service.request_discovery(737)
    assert callback.call_count == 2


def test_invalid_addresses_are_ignored(discovery):
    service, _, callback = discovery
    assert not service.request_discovery(0)
    assert not service.request_discovery(10000)
    callback.assert_not_called()

def test_d4_traversal_requests_first_and_full_next_record(discovery, monkeypatch):
    from src.pytrain.pdi.constants import D4Action
    from src.pytrain.pdi.d4_req import D4Req
    from src.pytrain.pdi.pdi_listener import PdiListener
    from src.pytrain.pdi.pdi_req import PdiReq

    service, _, callback = discovery
    sent = []
    monkeypatch.setattr(PdiListener, "enqueue_command", lambda request: sent.append(request))
    monkeypatch.setattr(service, "_arm_timeout", lambda: None)
    service._started = True
    assert service.request_discovery(737)
    assert sent[-1].action == D4Action.FIRST_REC
    first = D4Req(3, action=D4Action.FIRST_REC)
    first._next_record_no = 3
    service(first)
    assert sent[-1].action == D4Action.NEXT_REC
    assert sent[-1].record_no == 3
    assert sent[-1].data_length == PdiReq.scope_record_length(CommandScope.ENGINE)
    service.stop()
