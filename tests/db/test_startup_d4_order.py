"""Discover 4D engines completely before requesting the 4D train count."""

from threading import Thread
from typing import cast

import pytest

from src.pytrain.comm.command_listener import CommandDispatcher
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.startup_state import StartupState
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_listener import PdiListener
from src.pytrain.pdi.pdi_state_store import PdiStateStore

from .test_startup_state import MockDispatcher, MockPdiListener, MockPdiStateStore, make_dummy_d4req


D4_ENGINE = PdiCommand(0x2E)
D4_TRAIN = PdiCommand(0x2F)


@pytest.fixture
def startup(monkeypatch):
    monkeypatch.setattr(StartupState, Thread.start.__name__, lambda self: None)
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    ComponentStateStore.build()
    listener = MockPdiListener()
    state = StartupState(
        cast(PdiListener, cast(object, listener)),
        cast(CommandDispatcher, cast(object, MockDispatcher())),
        cast(PdiStateStore, cast(object, MockPdiStateStore())),
    )
    return state, listener


def count_response(command: PdiCommand, count: int) -> D4Req:
    return D4Req(D4Req(0, command, D4Action.COUNT, count=count).as_bytes)


def request_sequence(listener):
    return [(req.pdi_command, req.action, req.record_no) for req in listener.enqueued if isinstance(req, D4Req)]


# Set the completion event so the real run() exits after its initial requests without waiting.
# noinspection PyProtectedMember
@pytest.mark.parametrize("no_d4", (False, True))
def test_run_requests_only_engine_count_before_responses(startup, no_d4: bool):
    state, listener = startup
    state._no_d4 = no_d4
    state._ev.set()
    state.run()
    expected = [] if no_d4 else [(D4_ENGINE, D4Action.COUNT, 0)]
    assert request_sequence(listener) == expected


# Inspect pending-request bookkeeping to ensure the transition cannot finish sync early.
# noinspection PyProtectedMember
def test_engine_walk_then_train_count_then_train_walk(startup):
    state, listener = startup
    state(count_response(D4_ENGINE, 2))
    state(make_dummy_d4req(D4Action.FIRST_REC, next_record_no=3))
    next_engine = make_dummy_d4req(D4Action.NEXT_REC, next_record_no=7)
    next_engine._record_no = 3
    state(next_engine)
    assert request_sequence(listener) == [
        (D4_ENGINE, D4Action.FIRST_REC, 0),
        (D4_ENGINE, D4Action.NEXT_REC, 3),
        (D4_ENGINE, D4Action.NEXT_REC, 7),
    ]
    last_engine = make_dummy_d4req(D4Action.NEXT_REC, next_record_no=0xFFFF)
    last_engine._record_no = 7
    state(last_engine)
    train_count = listener.enqueued[-1]
    assert isinstance(train_count, D4Req)
    assert (train_count.pdi_command, train_count.action) == (D4_TRAIN, D4Action.COUNT)
    assert train_count.as_key in state._waiting_for
    assert not state._ev.is_set()

    state(count_response(D4_TRAIN, 1))
    state(make_dummy_d4req(D4Action.FIRST_REC, D4_TRAIN, next_record_no=2))
    last_train = make_dummy_d4req(D4Action.NEXT_REC, D4_TRAIN, next_record_no=0xFFFF)
    last_train._record_no = 2
    state(last_train)
    assert state._waiting_for == {}
    assert state._ev.is_set()
    assert request_sequence(listener)[3:] == [
        (D4_TRAIN, D4Action.COUNT, 0),
        (D4_TRAIN, D4Action.FIRST_REC, 0),
        (D4_TRAIN, D4Action.NEXT_REC, 2),
    ]


@pytest.mark.parametrize("train_count", (0, 1))
def test_zero_engines_still_discovers_trains(startup, train_count: int):
    state, listener = startup
    state(count_response(D4_ENGINE, 0))
    assert request_sequence(listener) == [(D4_TRAIN, D4Action.COUNT, 0)]
    state(count_response(D4_TRAIN, train_count))
    expected = [(D4_TRAIN, D4Action.COUNT, 0)]
    if train_count:
        expected.append((D4_TRAIN, D4Action.FIRST_REC, 0))
    assert request_sequence(listener) == expected


@pytest.mark.parametrize("action", (D4Action.FIRST_REC, D4Action.NEXT_REC))
def test_engine_end_sentinel_requests_train_count_once(startup, action):
    state, listener = startup
    response = make_dummy_d4req(action, next_record_no=0xFFFF)
    state(response)
    state(response)
    assert request_sequence(listener) == [(D4_TRAIN, D4Action.COUNT, 0)]


def test_duplicate_zero_engine_count_does_not_restart_train_discovery(startup):
    state, listener = startup
    state(count_response(D4_ENGINE, 0))
    state(count_response(D4_ENGINE, 0))
    assert request_sequence(listener) == [(D4_TRAIN, D4Action.COUNT, 0)]


@pytest.mark.parametrize("action", (D4Action.FIRST_REC, D4Action.NEXT_REC))
def test_missing_engine_next_pointer_does_not_start_train_discovery(startup, action):
    state, listener = startup
    state(make_dummy_d4req(action, next_record_no=None))
    assert request_sequence(listener) == []


@pytest.mark.parametrize("action", (D4Action.FIRST_REC, D4Action.NEXT_REC))
def test_train_end_sentinel_cannot_start_train_count(startup, action):
    state, listener = startup
    state(make_dummy_d4req(action, D4_TRAIN, next_record_no=0xFFFF))
    assert request_sequence(listener) == []


# Exercise the no-D4 configuration without starting a background worker.
# noinspection PyProtectedMember
def test_no_d4_does_not_start_trains_on_unsolicited_engine_end(startup):
    state, listener = startup
    state._no_d4 = True
    state(make_dummy_d4req(D4Action.NEXT_REC, next_record_no=0xFFFF))
    assert request_sequence(listener) == []
