"""Verify active command-impact refreshes without the unused query-package path."""

from unittest.mock import Mock

import pytest

import src.pytrain.comm.command_listener as listener_module
from src.pytrain.comm.command_listener import CommandDispatcher
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.mark.parametrize(
    "state_present, qualifies, request_present",
    [(False, True, True), (True, False, True), (True, True, False), (True, True, True)],
)
def test_command_impact_sends_only_a_qualifying_refresh(monkeypatch, state_present, qualifies, request_present):
    command = CommandReq.build(TMCC2EngineCommandEnum.NUMERIC, 7, data=0)
    state = Mock() if state_present else None
    predicate = Mock(return_value=qualifies)
    request = Mock() if request_present else None
    factory = Mock(return_value=request)
    get_state = Mock(return_value=state)
    monkeypatch.setattr(listener_module, "COMMAND_IMPACTS", {command.command: (predicate, factory)})
    monkeypatch.setattr(ComponentStateStore, "get_state", get_state)

    CommandDispatcher.request_command_impact(command)

    get_state.assert_called_once_with(command.scope, command.address, create=False)
    if state_present:
        predicate.assert_called_once_with(state)
    else:
        predicate.assert_not_called()
    if state_present and qualifies:
        factory.assert_called_once_with(state, command)
        if request is not None:
            request.send.assert_called_once_with()
    else:
        factory.assert_not_called()
        if request is not None:
            request.send.assert_not_called()


def test_command_without_impact_does_not_query_state(monkeypatch):
    command = CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 7, data=12)
    get_state = Mock()
    monkeypatch.setattr(listener_module, "COMMAND_IMPACTS", {})
    monkeypatch.setattr(ComponentStateStore, "get_state", get_state)

    CommandDispatcher.request_command_impact(command)

    get_state.assert_not_called()
