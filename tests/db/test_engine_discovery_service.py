"""Engine discovery coordinator regression contracts."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_discovery_service import EngineDiscoveryService
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.ble_req import BleReq
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_listener import PdiListener
from src.pytrain.pdi.constants import D4Action, PdiCommand
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


def test_set_address_has_no_discovery_subscription(monkeypatch, discovery):
    from src.pytrain.comm.command_observer import CommandObserver

    service, _, callback = discovery
    registered = []
    monkeypatch.setattr(CommandObserver, "register", lambda *args: registered.append(args))
    monkeypatch.setattr(CommandObserver, "unregister", lambda *args: registered.append(args))
    monkeypatch.setattr(
        PdiListener,
        "get",
        lambda: SimpleNamespace(
            subscribe_any=lambda subscriber: None,
            unsubscribe_any=lambda subscriber: None,
        ),
    )
    service.start()
    service.stop()
    assert registered == []
    callback.assert_not_called()


def test_start_subscribes_and_stop_unsubscribes(monkeypatch, discovery):
    service, _, callback = discovery
    subscribers = set()

    def subscribe(subscriber):
        subscribers.add(subscriber)

    def unsubscribe(subscriber):
        subscribers.remove(subscriber)

    monkeypatch.setattr(
        PdiListener,
        "get",
        lambda: SimpleNamespace(subscribe_any=subscribe, unsubscribe_any=unsubscribe),
    )
    monkeypatch.setattr(PdiListener, "enqueue_command", lambda request: None)
    monkeypatch.setattr(service, "_arm_timeout", lambda: None)

    service.start()
    assert service in subscribers
    service.start()  # Idempotent registration.
    assert len(subscribers) == 1

    notification = BleReq(bytes.fromhex("d1760012000030373337a7df"), PdiCommand.BLE_RX)
    for subscriber in tuple(subscribers):
        subscriber(notification)
    callback.assert_called_once_with(notification.tmcc_id)
    assert service._active == notification.tmcc_id

    service.stop()
    assert not subscribers
    service.stop()  # Idempotent shutdown.
    service.start()  # Restart must re-register the listener.
    assert service in subscribers
    service.stop()
    assert not subscribers


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
        "d176001225ff54df",
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

    class FakeWatcher:
        def __init__(self, state, callback):
            self.callback = callback

        def shutdown(self):
            pass

    monkeypatch.setattr("src.pytrain.db.engine_discovery_service.StateWatcher", FakeWatcher)
    assert service.request_discovery(737)
    service(_first_record(0))
    service(_next_record(0, 1, 1065))
    service(_next_record(1, 2, 4062))
    service(_next_record(2, 3, 353))
    assert [request.record_no for request in sent[1:]] == [0, 1, 2, 3]
    state["value"] = SimpleNamespace()
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


@pytest.mark.parametrize("tmcc_id", [37, 737])
def test_discovery_requires_complete_state(tmcc_id):
    valid = dict(
        tmcc_id=tmcc_id,
        is_deleted=False,
        is_comp_data_record=True,
        comp_data=SimpleNamespace(is_active=lambda: True),
        record_no=3 if tmcc_id >= 100 else None,
        is_d4=tmcc_id >= 100,
        is_legacy=tmcc_id >= 100,
    )
    assert EngineDiscoveryService._is_discovery_complete(SimpleNamespace(**valid), tmcc_id, 3)
    for key, invalid in (
        ("tmcc_id", tmcc_id + 1),
        ("is_deleted", True),
        ("is_comp_data_record", False),
        ("comp_data", None),
        *((("record_no", None), ("record_no", 0xFFFF)) if tmcc_id >= 100 else ()),
    ):
        assert not EngineDiscoveryService._is_discovery_complete(
            SimpleNamespace(**(valid | {key: invalid})), tmcc_id, 3
        )
    if tmcc_id >= 100:
        assert not EngineDiscoveryService._is_discovery_complete(SimpleNamespace(**valid), tmcc_id, 4)
    if tmcc_id >= 100:
        for key in ("is_d4", "is_legacy"):
            assert not EngineDiscoveryService._is_discovery_complete(
                SimpleNamespace(**(valid | {key: False})), tmcc_id, 3
            )


def test_2d_discovery_sends_memory_query(traversal, monkeypatch):
    service, state, callback, sent = traversal

    class FakeWatcher:
        def __init__(self, state, action):
            self.action = action
            self.stopped = False

        def shutdown(self):
            self.stopped = True

    monkeypatch.setattr("src.pytrain.db.engine_discovery_service.StateWatcher", FakeWatcher)
    state["value"] = SimpleNamespace(
        tmcc_id=37,
        is_deleted=False,
        is_comp_data_record=False,
        comp_data=None,
        record_no=None,
    )
    assert service.request_discovery(37)
    callback.assert_called_once_with(37)
    assert len(sent) == 1
    assert isinstance(sent[0], BaseReq)
    assert sent[0].pdi_command == PdiCommand.BASE_MEMORY
    assert sent[0].tmcc_id == 37
    watcher = service._watcher
    service._verify_found(37)
    assert service._active == 37  # An incomplete state cannot finish discovery.
    state["value"].is_comp_data_record = True
    state["value"].comp_data = SimpleNamespace(is_active=lambda: True, as_bytes=lambda: bytes(0x19))
    watcher.action()
    assert service._active is None
    assert watcher.stopped


@pytest.mark.parametrize(
    ("momentum", "setting", "expected"),
    [
        (0xFF, 0xFF, [("momentum", 0), ("momentum_setting", 0x63)]),
        (0, 0xFF, []),
        (0xFF, 0x63, []),
        (0, 0x63, []),
    ],
)
def test_correct_default_momentum_only_when_both_bytes_uninitialized(monkeypatch, momentum, setting, expected):
    from src.pytrain.db.comp_data import CompData

    sent = []
    generated = []
    raw = bytearray(0x19)
    raw[0x17] = setting
    raw[0x18] = momentum
    data = SimpleNamespace(momentum=momentum, momentum_setting=setting, as_bytes=lambda: bytes(raw))
    state = SimpleNamespace(tmcc_id=113, comp_data=data)

    def make_request(field, value, state):
        generated.append((field, value))
        return SimpleNamespace(field=field, value=value)

    query = SimpleNamespace(field="query", value=None)
    monkeypatch.setattr(CompData, "generate_update_req", make_request)
    monkeypatch.setattr(BaseReq, "create_base_query_request", lambda current: query)
    monkeypatch.setattr(PdiListener, "enqueue_command", sent.append)

    EngineDiscoveryService._correct_default_momentum(state)

    assert generated == expected
    assert [(request.field, request.value) for request in sent] == (
        expected + ([("query", None)] if expected else [])
    )
    if expected:
        assert sent[-1] is query
    else:
        assert not sent
    assert data.momentum == momentum
    assert data.momentum_setting == setting


@pytest.mark.parametrize("failed_field", ["momentum", "momentum_setting"])
def test_momentum_correction_requires_both_writes_before_queueing(monkeypatch, failed_field):
    from src.pytrain.db.comp_data import CompData

    raw = bytearray(0x19)
    raw[0x17] = raw[0x18] = 0xFF
    data = SimpleNamespace(momentum=0xFF, momentum_setting=0xFF, as_bytes=lambda: bytes(raw))
    state = SimpleNamespace(tmcc_id=113, comp_data=data)
    sent = []

    def make_request(field, value, state):
        return None if field == failed_field else SimpleNamespace(field=field, value=value)

    monkeypatch.setattr(CompData, "generate_update_req", make_request)
    monkeypatch.setattr(PdiListener, "enqueue_command", sent.append)
    monkeypatch.setattr(
        BaseReq,
        "create_base_query_request",
        lambda current: pytest.fail("Query must not be sent when an update cannot be generated"),
    )

    EngineDiscoveryService._correct_default_momentum(state)

    assert not sent
    assert data.momentum == 0xFF
    assert data.momentum_setting == 0xFF
