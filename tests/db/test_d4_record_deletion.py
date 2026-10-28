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
