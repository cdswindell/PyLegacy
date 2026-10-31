"""Engine discovery coordinator regression contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_discovery_service import EngineDiscoveryService
from src.pytrain.pdi.ble_req import BleReq
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_listener import PdiListener
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
    callback.assert_not_called()  # TMCC1/TMCC2 addresses cannot encode a D4 ID.


def test_existing_engine_does_not_enter_discovery(discovery):
    service, state, callback = discovery
    state["value"] = SimpleNamespace(is_deleted=False, comp_data=object(), is_comp_data_record=True, record_no=3)
    service.request_discovery(737)
    callback.assert_not_called()


def test_placeholder_without_database_record_is_not_existing(discovery):
    service, state, callback = discovery
    state["value"] = SimpleNamespace(is_deleted=False, comp_data=None, is_comp_data_record=False, record_no=None)
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
    state["value"] = SimpleNamespace(is_deleted=False, comp_data=object(), is_comp_data_record=True, record_no=3)
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
    service._started = False
    service.complete(737)


@pytest.fixture
def traversal(discovery, monkeypatch):
    service, state, callback = discovery
    sent = []
    monkeypatch.setattr(PdiListener, "enqueue_command", sent.append)
    monkeypatch.setattr(service, "_arm_timeout", lambda: None)
    service._started = True
    return service, state, callback, sent


def _first_record(record_no):
    response = D4Req(record_no, PdiCommand.D4_ENGINE, D4Action.FIRST_REC)
    response._next_record_no = record_no
    return response


def _next_record(record_no, next_record, tmcc_id, complete=True):
    response = D4Req(record_no, PdiCommand.D4_ENGINE, D4Action.NEXT_REC)
    response._next_record_no = next_record
    response._tmcc_id = tmcc_id
    response._comp_data_record = complete
    response._comp_data = object() if complete else None
    return response


def test_traversal_stops_at_matching_record(traversal, monkeypatch):
    service, state, _, sent = traversal
    verified = []
    monkeypatch.setattr(service, "_verify_found", verified.append)

    # Avoid real asynchronous timers; invoke the verification callback explicitly.
    class ImmediateTimer:
        daemon = True

        def __init__(self, delay, callback, args=()):
            self.callback = callback
            self.args = args

        def start(self):
            self.callback(*self.args)

    monkeypatch.setattr("src.pytrain.db.engine_discovery_service.Timer", ImmediateTimer)
    assert service.request_discovery(737)
    service(_first_record(0))
    service(_next_record(0, 1, 1065))
    service(_next_record(1, 2, 4062))
    service(_next_record(2, 3, 353))
    assert [request.record_no for request in sent[1:]] == [0, 1, 2, 3]
    service(_next_record(3, 4, 737))
    assert verified == [737]
    assert len(sent) == 5


def test_traversal_exhausted_roster_releases_slot(traversal):
    service, _, _, sent = traversal
    assert service.request_discovery(737)
    service(_first_record(0))
    service(_next_record(0, 0xFFFF, 1065))
    assert service._active is None
    assert len(sent) == 2
    assert service.request_discovery(738)
    assert sent[-1].action == D4Action.FIRST_REC


def test_traversal_repeated_record_terminates(traversal):
    service, _, _, sent = traversal
    assert service.request_discovery(737)
    service(_first_record(0))
    service(_next_record(0, 0, 1065))
    assert service._active is None
    assert len(sent) == 2


def test_incomplete_next_record_aborts_discovery(traversal):
    service, _, _, sent = traversal
    assert service.request_discovery(737)
    service(_first_record(3))
    service(_next_record(3, 4, 737, complete=False))
    assert service._active is None
    assert len(sent) == 2


def test_queued_discoveries_run_in_order(traversal):
    service, _, callback, sent = traversal
    assert service.request_discovery(737)
    assert service.request_discovery(738)
    assert not service.request_discovery(738)
    assert len(sent) == 1
    service(_first_record(0xFFFF))
    assert service._active == 738
    assert [request.action for request in sent] == [D4Action.FIRST_REC, D4Action.FIRST_REC]
    assert callback.call_count == 2


def test_timeout_releases_slot_and_starts_next(traversal):
    service, _, _, sent = traversal
    assert service.request_discovery(737)
    assert service.request_discovery(738)
    service._timed_out(737, None)
    assert service._active == 738
    assert len(sent) == 2
    # A stale timeout must not interrupt the next discovery.
    service._timed_out(737, None)
    assert service._active == 738
