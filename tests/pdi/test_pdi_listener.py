#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# src/tests/pdi/test_pdi_listener.py
import threading

import pytest

from src.pytrain import CommandScope
from src.pytrain.comm.command_listener import CommandDispatcher
from src.pytrain.db.comp_data import EngineData
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import PdiCommand
from src.pytrain.pdi.pdi_listener import PdiDispatcher, PdiListener
from src.pytrain.pdi.pdi_req import PdiReq


class _Catcher:
    def __init__(self):
        self.messages = []
        self.ev = threading.Event()

    def __call__(self, msg):
        self.messages.append(msg)
        self.ev.set()

    def wait(self, timeout=1.0):
        return self.ev.wait(timeout)


class _DeletableState:
    is_deletable = True

    def __init__(self) -> None:
        self.is_deleted = False
        self.clear_calls = 0

    def clear(self) -> bool:
        self.clear_calls += 1
        self.is_deleted = True
        return True


def _inactive_base_memory_record(scope: CommandScope, tmcc_id: int) -> BaseReq:
    payload = EngineData(None, tmcc_id).as_bytes()
    req = BaseReq(
        tmcc_id,
        PdiCommand.BASE_MEMORY,
        scope=scope,
        start=0,
        data_length=PdiReq.scope_record_length(scope),
        data_bytes=payload,
    )
    return BaseReq(req.as_bytes)


@pytest.fixture(autouse=True)
def clean_singletons():
    # Ensure prior tests state is cleared without broad excepts
    if PdiListener.is_built():
        PdiListener.stop()
    if PdiDispatcher.is_built():
        PdiDispatcher.get().shutdown()
    if CommandDispatcher.is_built():
        CommandDispatcher.get().shutdown()
    yield
    if PdiListener.is_built():
        PdiListener.stop()
    if PdiDispatcher.is_built():
        PdiDispatcher.get().shutdown()
    if CommandDispatcher.is_built():
        CommandDispatcher.get().shutdown()


def test_build_and_singleton():
    assert PdiListener.is_built() is False
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    assert listener is not None
    assert PdiListener.is_built() is True
    assert PdiListener.get() is listener
    assert PdiListener.is_running() is True

    # Stop and ensure singleton resets
    PdiListener.stop()
    assert PdiListener.is_built() is False
    assert PdiListener.is_running() is False


def test_listen_for_raises_when_not_built():
    with pytest.raises(AttributeError):
        PdiListener.listen_for(_Catcher(), CommandScope.ENGINE)


def test_offer_parses_and_publishes_broadcast():
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    catcher = _Catcher()
    # Subscribe to all broadcasts
    listener.subscribe_any(catcher)

    # Build a valid PDI request (Base Engine query for engine 1)
    req = BaseReq(20, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE)
    data = req.as_bytes

    # Prepend a garbage byte to ensure the listener skips non-SOP leading bytes
    noisy = bytes([0x00]) + data
    listener.offer(noisy)

    # Wait for dispatch
    assert catcher.wait(1.5), "Timed out waiting for dispatched PDI message"

    # Validate we got exactly one parsed message equal to what we sent
    assert len(catcher.messages) >= 1
    got = catcher.messages[-1]
    assert hasattr(got, "as_bytes")
    assert got.as_bytes == data

    # Cleanup
    listener.unsubscribe_any(catcher)
    PdiListener.stop()


def test_scope_subscription_receives_expected_message():
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    catcher = _Catcher()

    # Subscribe specifically to CommandScope.ENGINE
    listener.subscribe(catcher, CommandScope.ENGINE)

    req = BaseReq(33, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE)
    listener.offer(req.as_bytes)

    assert catcher.wait(1.5), "Timed out waiting for scoped PDI message"
    assert len(catcher.messages) >= 1
    got = catcher.messages[-1]
    assert got.scope == CommandScope.ENGINE
    assert got.tmcc_id == 33

    # Unsubscribe and ensure no further messages delivered
    listener.unsubscribe(catcher, CommandScope.ENGINE)
    catcher.ev.clear()
    listener.offer(req.as_bytes)
    # Give it a bit of time; should not receive
    assert catcher.wait(0.3) is False

    PdiListener.stop()


def test_dispatcher_offer_accepts_bytes_or_req_and_filters_ack_ping_free_path():
    listener = PdiListener.build(base3=None, build_base3_reader=False)
    catcher = _Catcher()
    listener.subscribe_any(catcher)

    # Normal, non-ack, non-ping request should be dispatched
    req = BaseReq(2, PdiCommand.BASE_MEMORY, scope=CommandScope.TRAIN)  # a standard request
    listener.dispatcher.offer(req)  # as object
    listener.dispatcher.offer(req.as_bytes)  # as bytes too

    # Should receive at least one (often two) messages
    assert catcher.wait(1.5)
    assert len(catcher.messages) >= 1

    # Sanity check last received equals something we offered
    last = catcher.messages[-1]
    assert last.as_bytes == req.as_bytes

    listener.unsubscribe_any(catcher)
    PdiListener.stop()


def test_dispatcher_publishes_delete_for_inactive_base_memory_record(monkeypatch):
    dispatcher = PdiDispatcher.build()
    catcher = _Catcher()
    state = _DeletableState()
    scope = CommandScope.ENGINE
    tmcc_id = 55

    def get_state(request_scope, request_tmcc_id, create=False):
        if (request_scope, request_tmcc_id, create) == (scope, tmcc_id, False):
            return state
        return None

    monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(get_state), raising=True)
    dispatcher.subscribe_delete(catcher)

    dispatcher.offer(_inactive_base_memory_record(scope, tmcc_id))

    assert catcher.wait(1.5), "Timed out waiting for delete notification"
    assert catcher.messages == [state]
    assert state.clear_calls == 1
    assert state.is_deleted is True

    dispatcher.unsubscribe_delete(catcher)
