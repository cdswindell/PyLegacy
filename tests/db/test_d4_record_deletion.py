"""Regression coverage for Base 3 D4 engine/train record deletion."""

from unittest.mock import MagicMock

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
