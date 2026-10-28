"""Regression coverage for Base 3 D4 engine/train record deletion."""

from unittest.mock import MagicMock, patch

import pytest

from src.pytrain.db.comp_data import CompData
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.protocol.constants import CommandScope


@pytest.mark.parametrize(
    ("scope", "command"),
    [
        (CommandScope.ENGINE, PdiCommand.D4_ENGINE),
        (CommandScope.TRAIN, PdiCommand.D4_TRAIN),
    ],
)
def test_d4_clear_is_single_request(scope, command):
    state = MagicMock()
    state.scope = scope
    state.address = 88
    state.is_d4 = True
    state.record_no = 0

    requests = CompData.clear_record_reqs(state)

    assert len(requests) == 1
    req = requests[0]
    assert isinstance(req, D4Req)
    assert req.pdi_command == command
    assert req.action == D4Action.CLEAR
    assert req.record_no == 0
    if scope == CommandScope.ENGINE:
        assert req.as_bytes == bytes.fromhex("D12E00001300BFDF")


@pytest.mark.parametrize("record_no", [None, -1, 65535])
def test_d4_clear_rejects_invalid_record(record_no):
    state = MagicMock()
    state.scope = CommandScope.ENGINE
    state.address = 88
    state.is_d4 = True
    state.record_no = record_no

    with pytest.raises(ValueError):
        CompData.clear_record_reqs(state)


def test_delete_state_removes_aliases_and_bt_index():
    store = object.__new__(ComponentStateStore)
    state = MagicMock()
    state.scope = CommandScope.ENGINE
    state.address = 88
    store._state = {CommandScope.ENGINE: {88: state, 2021: state}}
    store._bt_index = {123: {88: state}}
    store._deleted_addresses = set()

    store._delete_state(CommandScope.ENGINE, 88)

    assert store._state[CommandScope.ENGINE] == {}
    assert store._bt_index == {}
    assert store._deleted_addresses == {
        (CommandScope.ENGINE, 88),
        (CommandScope.ENGINE, 2021),
    }


@pytest.mark.parametrize(
    ("scope", "command"),
    [
        (CommandScope.ENGINE, PdiCommand.D4_ENGINE),
        (CommandScope.TRAIN, PdiCommand.D4_TRAIN),
    ],
)
@pytest.mark.parametrize("record_no", [0, 1, 255, 256, 65534])
def test_d4_clear_round_trip(scope, command, record_no):
    state = MagicMock(scope=scope, address=50, is_d4=True, record_no=record_no)
    req = CompData.clear_record_reqs(state)[0]

    decoded = D4Req(req.as_bytes)

    assert decoded.pdi_command == command
    assert decoded.action == D4Action.CLEAR
    assert decoded.record_no == record_no
    assert decoded.as_bytes == req.as_bytes


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_deleted_address_ignores_late_updates(scope):
    store = object.__new__(ComponentStateStore)
    store._state = {scope: {}}
    store._deleted_addresses = {(scope, 50)}

    command = MagicMock()
    command.scope = scope
    command.address = 50
    command.is_filtered = False

    store._filter_updates = False
    store(command)

    assert store._state[scope] == {}
    assert (scope, 50) in store._deleted_addresses


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_deleted_alias_ignores_late_updates(scope):
    store = object.__new__(ComponentStateStore)
    state = MagicMock()
    state.scope = scope
    state.address = 50
    store._state = {scope: {50: state, 737: state}}
    store._bt_index = {}
    store._deleted_addresses = set()
    store._filter_updates = False

    store._delete_state(scope, 50)

    command = MagicMock()
    command.scope = scope
    command.address = 737
    command.is_filtered = False
    store(command)

    assert store._state[scope] == {}
    assert (scope, 737) in store._deleted_addresses


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_explicit_state_recreation_clears_tombstone(scope):
    store = object.__new__(ComponentStateStore)
    store._state = {scope: {}}
    store._deleted_addresses = {(scope, 50)}
    previous = ComponentStateStore._instance
    try:
        ComponentStateStore._instance = store
        replacement = MagicMock()
        ComponentStateStore.set_state(scope, 50, replacement)
        assert store.query(scope, 50) is replacement
        assert (scope, 50) not in store._deleted_addresses
    finally:
        ComponentStateStore._instance = previous


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_deleted_component_rejects_queued_update(scope):
    from src.pytrain.db.component_state import ComponentState

    state = object.__new__(ComponentState)
    state._deleted = True
    state._cv = __import__("threading").Condition()
    command = MagicMock()
    with patch.object(ComponentState, "_prepare_update") as prepare:
        with patch.object(ComponentState, "_update_state") as update:
            state.update(command)
    prepare.assert_not_called()
    update.assert_not_called()


@pytest.mark.parametrize(
    ("scope", "command"),
    [
        (CommandScope.ENGINE, PdiCommand.D4_ENGINE),
        (CommandScope.TRAIN, PdiCommand.D4_TRAIN),
    ],
)
def test_d4_clear_dispatch_removes_state_and_notifies_clients(scope, command, monkeypatch):
    import threading
    from queue import Queue

    from src.pytrain.pdi.pdi_listener import PdiDispatcher

    state = MagicMock()
    state.record_no = 7
    state.is_deleted = False
    state.is_deletable = True
    state.clear.return_value = True

    queue = Queue()
    queue.put(D4Req(7, command, D4Action.CLEAR))
    dispatcher = object.__new__(PdiDispatcher)
    dispatcher._queue = queue
    dispatcher._cv = threading.Condition()
    dispatcher._is_running = True
    dispatcher._broadcasts = False
    dispatcher._deletes = True
    dispatcher._is_server = True
    published = []
    forwarded = []
    dispatcher.publish = lambda topic, payload: published.append((topic, payload))
    dispatcher.update_client_state = lambda payload: forwarded.append(payload)

    monkeypatch.setattr(ComponentStateStore, "by_record_no", lambda record, requested_scope: (
        state if record == 7 and requested_scope == scope else None
    ))

    def stop_after_first():
        dispatcher._is_running = False

    original_task_done = queue.task_done
    def finish():
        original_task_done()
        stop_after_first()
    queue.task_done = finish

    dispatcher.run()

    from src.pytrain.pdi.pdi_listener import DELETE_TOPIC

    state.clear.assert_called_once_with()
    assert (DELETE_TOPIC, state) in published
    assert len(forwarded) == 1
    assert forwarded[0].record_no == 7
    assert forwarded[0].scope == scope


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_d2_deleted_address_rejects_late_base_memory_update(scope):
    from src.pytrain.pdi.base_req import BaseReq
    from src.pytrain.pdi.constants import PdiCommand

    store = object.__new__(ComponentStateStore)
    store._state = {scope: {}}
    store._deleted_addresses = {(scope, 50)}
    store._filter_updates = False
    command = MagicMock(spec=BaseReq)
    command.scope = scope
    command.address = 50
    command.is_filtered = False
    command.is_comp_data_record = False
    store(command)

    assert store._state[scope] == {}
    assert (scope, 50) in store._deleted_addresses
