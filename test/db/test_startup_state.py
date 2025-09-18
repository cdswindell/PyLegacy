import time

import pytest

from src.pytrain.comm.command_listener import SYNC_COMPLETE
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.startup_state import StartupState
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_req import AllReq, PdiReq
from src.pytrain.protocol.constants import CommandScope


class MockDispatcher:
    def __init__(self):
        self.offers = []

    def offer(self, cmd):
        self.offers.append(cmd)


class MockPdiListener:
    def __init__(self):
        self.enqueued = []

    def enqueue_command(self, req):
        self.enqueued.append(req)

    # StartupState.run subscribes/unsubscribes, but we patch run out in tests
    def subscribe_any(self, subscriber):
        pass

    def unsubscribe_any(self, subscriber):
        pass

    @property
    def dispatcher(self):
        return None


class MockPdiStateStore:
    def __init__(self, to_return=None):
        self.calls = []
        self.to_return = to_return or []

    def register_pdi_device(self, cmd):
        self.calls.append(cmd)
        # Return any preconfigured follow-up PDI requests
        return list(self.to_return)


@pytest.fixture(autouse=True)
def build_component_store():
    """
    Ensure the ComponentStateStore singleton exists before tests that construct StartupState,
    as StartupState.__init__ accesses it via ComponentStateStore.get_state(...).
    """
    _ = ComponentStateStore()  # build singleton with defaults
    yield
    ComponentStateStore.reset()
    # noinspection PyTypeChecker
    ComponentStateStore._instance = None


@pytest.fixture(autouse=True)
def no_thread_start(monkeypatch, request):
    # Prevent the background thread from running in tests to avoid timing dependencies
    # noinspection PyTypeChecker, PyUnusedLocal
    def dummy_run(self):
        return None

    # Allow specific tests to use the real run() by marking them with @pytest.mark.allow_thread
    if not request.node.get_closest_marker("allow_thread"):
        monkeypatch.setattr(StartupState, "run", dummy_run)
    yield


class FakeConfigReq(PdiReq):
    """
    Minimal concrete PdiReq used for tests to simulate a 'config' message.
    Implements only what's needed by StartupState: action (with is_config, as_bytes),
    tmcc_id, pdi_command, scope, and as_key.
    """

    class _Action:
        def __init__(self, as_bytes: bytes = b"\x10"):
            self.as_bytes = as_bytes
            self.is_config = True

    def __init__(self, pdi_command: PdiCommand, tmcc_id: int, scope: CommandScope = CommandScope.SYSTEM):
        # Do NOT call super(); we just set the minimal attributes StartupState reads.
        self._pdi_command = pdi_command
        self._tmcc_id = tmcc_id
        self._scope = scope
        self._action = FakeConfigReq._Action()

    @property
    def action(self):
        return self._action

    @property
    def as_key(self):
        # Matches the tuple shape used by StartupState for _waiting_for keys
        return self.tmcc_id, self.pdi_command, self.action, self.scope


# noinspection PyPropertyAccess
def make_dummy_basereq_for_memory(scope: CommandScope, tmcc_id: int, data_length: int):
    """
    Create a minimal BaseReq instance without invoking BaseReq.__init__.
    Ensures isinstance(dummy, BaseReq) is True and necessary attributes exist.
    """
    dummy = object.__new__(BaseReq)
    dummy._pdi_command = PdiCommand.BASE_MEMORY
    dummy._scope = scope
    dummy._tmcc_id = tmcc_id
    dummy._data_length = data_length
    dummy._record_no = 0
    return dummy


# noinspection PyPropertyAccess
def make_dummy_d4req(action, pdi_command=PdiCommand.D4_ENGINE, next_record_no=None):
    """
    Create a minimal D4Req instance without invoking D4Req.__init__.
    Ensures isinstance(dummy, D4Req) is True and attributes StartupState uses are present.
    """
    dummy = object.__new__(D4Req)
    dummy._action = action
    dummy._pdi_command = pdi_command
    dummy._scope = CommandScope.ENGINE
    dummy._record_no = 0
    dummy._next_record_no = next_record_no
    return dummy


# noinspection PyTypeChecker
def test_config_registration_enqueues_followups_once():
    listener = MockPdiListener()
    dispatcher = MockDispatcher()
    follow_ups = [AllReq()]  # simple, valid PdiReq to enqueue
    pdi_state_store = MockPdiStateStore(to_return=follow_ups)

    ss = StartupState(listener, dispatcher, pdi_state_store)

    # Simulate a config PDI request
    cfg_cmd = FakeConfigReq(PdiCommand.ALL_GET, tmcc_id=7)
    ss(cfg_cmd)

    # State store called once with the config PDI
    assert len(pdi_state_store.calls) == 1
    assert pdi_state_store.calls[0] is cfg_cmd

    # All returned follow-up state requests should be enqueued
    assert len(listener.enqueued) == len(follow_ups)
    assert isinstance(listener.enqueued[0], PdiReq)

    # Re-sending the same config should not call register again (processed only once)
    ss(cfg_cmd)
    assert len(pdi_state_store.calls) == 1  # unchanged


# noinspection PyTypeChecker
def test_base_memory_triggers_next_query(monkeypatch):
    listener = MockPdiListener()
    dispatcher = MockDispatcher()
    pdi_state_store = MockPdiStateStore()

    ss = StartupState(listener, dispatcher, pdi_state_store)

    # Create a BaseReq-like object for TRAIN scope, tmcc_id 98, with correct record length
    record_len = PdiReq.scope_record_length(CommandScope.ENGINE)
    base_cmd = make_dummy_basereq_for_memory(CommandScope.ENGINE, tmcc_id=97, data_length=record_len)

    # Call into StartupState with the "response"
    ss(base_cmd)

    # Sync should not be complete
    assert not any(o.command == SYNC_COMPLETE.command for o in dispatcher.offers)

    # Should enqueue the NEXT BaseReq for tmcc_id+1 (99) when lengths match
    # Verify last enqueued command is a BaseReq with the expected attributes
    assert len(listener.enqueued) >= 1
    next_req = listener.enqueued[-1]
    assert isinstance(next_req, BaseReq)
    assert next_req.pdi_command == PdiCommand.BASE_MEMORY
    assert next_req.tmcc_id == 98
    assert next_req.scope == CommandScope.ENGINE


# noinspection PyTypeChecker
def test_base_memory_triggers_sync_complete_and_next_query(monkeypatch):
    listener = MockPdiListener()
    dispatcher = MockDispatcher()
    pdi_state_store = MockPdiStateStore()

    ss = StartupState(listener, dispatcher, pdi_state_store)

    # Create a BaseReq-like object for TRAIN scope, tmcc_id 98, with correct record length
    record_len = PdiReq.scope_record_length(CommandScope.TRAIN)
    base_cmd = make_dummy_basereq_for_memory(CommandScope.TRAIN, tmcc_id=98, data_length=record_len)

    # Call into StartupState with the "response"
    ss(base_cmd)

    # Should offer SYNC_COMPLETE when TRAIN tmcc_id == 98
    assert any(o.command == SYNC_COMPLETE.command for o in dispatcher.offers)

    # Should be no more enqueued requests
    assert len(listener.enqueued) == 0


# noinspection PyTypeChecker
def test_base_memory_requests_created_for_all_scopes():
    listener = MockPdiListener()
    dispatcher = MockDispatcher()
    pdi_state_store = MockPdiStateStore()

    ss = StartupState(listener, dispatcher, pdi_state_store)

    # For each scope, simulate a valid BASE_MEMORY record and ensure a follow-up request is enqueued
    for scope in [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.SWITCH, CommandScope.ROUTE, CommandScope.ACC]:
        tmcc_id = 1  # less than 98 so that a "next" query should be generated
        record_len = PdiReq.scope_record_length(scope)
        base_cmd = make_dummy_basereq_for_memory(scope, tmcc_id=tmcc_id, data_length=record_len)

        ss(base_cmd)

        # Verify the last enqueued command is a BaseReq "next" record for the same scope
        assert len(listener.enqueued) >= 1
        next_req = listener.enqueued[-1]
        assert isinstance(next_req, BaseReq)
        assert next_req.pdi_command == PdiCommand.BASE_MEMORY
        assert next_req.tmcc_id == tmcc_id + 1
        assert next_req.scope == scope


# noinspection PyTypeChecker, PyUnusedLocal, PyPropertyAccess
def test_d4_count_requests_first_record():
    listener = MockPdiListener()
    dispatcher = MockDispatcher()
    pdi_state_store = MockPdiStateStore()

    ss = StartupState(listener, dispatcher, pdi_state_store)

    # Simulate a D4 COUNT response indicating presence of records (count non-zero)
    d4_count = make_dummy_d4req(D4Action.COUNT, pdi_command=PdiCommand.D4_ENGINE, next_record_no=None)
    # Emulate 'count' being truthy as the implementation checks 'if cmd.action == COUNT and cmd.count'
    d4_count._count = 3

    ss(d4_count)

    # Should enqueue a FIRST_REC request
    assert len(listener.enqueued) >= 1
    first_req = listener.enqueued[-1]
    assert isinstance(first_req, D4Req)
    assert first_req.action == D4Action.FIRST_REC
    assert first_req.pdi_command == PdiCommand.D4_ENGINE


# noinspection PyTypeChecker, PyUnusedLocal, PyPropertyAccess
def test_event_set_when_waiting_for_empty():
    listener = MockPdiListener()
    dispatcher = MockDispatcher()
    pdi_state_store = MockPdiStateStore()
    ss = StartupState(listener, dispatcher, pdi_state_store)

    # Ensure waiting_for is empty initially
    with ss._cv:
        ss._waiting_for.clear()
        ss._ev.clear()

    # Send a benign PdiReq that doesn't enqueue any follow-up (and pops as_key if present)
    # We need a valid PdiReq instance; AllReq() is a subclass and OK
    req = AllReq()
    # Provide an as_key so initial pop won't error and then empty waiting map sets the event
    # AllReq might already have as_key, but ensure there is one
    if not hasattr(req, "as_key"):
        req.as_key = ("ALL",)

    ss(req)

    # Event should be set when no outstanding requests remain
    assert ss._ev.is_set()


@pytest.mark.allow_thread
@pytest.mark.timeout(2)
def test_run_enqueues_base_memory_requests_for_all_scopes():
    listener = MockPdiListener()
    dispatcher = MockDispatcher()
    pdi_state_store = MockPdiStateStore()

    # noinspection PyTypeChecker
    ss = StartupState(listener, dispatcher, pdi_state_store)

    # Give the background thread a brief moment to enqueue initial requests
    time.sleep(0.05)

    # Collect BASE_MEMORY requests created by StartupState.run() for tmcc_id 1
    scopes_found = set()
    for req in listener.enqueued:
        if isinstance(req, BaseReq) and req.pdi_command == PdiCommand.BASE_MEMORY and req.tmcc_id == 1:
            scopes_found.add(req.scope)

    assert scopes_found == {
        CommandScope.ENGINE,
        CommandScope.TRAIN,
        CommandScope.SWITCH,
        CommandScope.ACC,
        CommandScope.ROUTE,
    }

    # Unblock the thread's wait loop and allow it to finish
    ss._ev.set()
    ss.join(timeout=1)


def test_base_memory_id1_responses_trigger_id2_requests_per_scope():
    listener = MockPdiListener()
    dispatcher = MockDispatcher()
    pdi_state_store = MockPdiStateStore()

    # noinspection PyTypeChecker
    ss = StartupState(listener, dispatcher, pdi_state_store)

    # Simulate BASE_MEMORY responses for tmcc_id=1 across all scopes
    scopes = [CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ROUTE, CommandScope.SWITCH, CommandScope.ACC]
    for scope in scopes:
        record_len = PdiReq.scope_record_length(scope)
        resp = make_dummy_basereq_for_memory(scope, tmcc_id=1, data_length=record_len)
        ss(resp)

    # For each scope ensure a follow-up BASE_MEMORY request for tmcc_id=2 was enqueued
    for scope in scopes:
        assert any(
            isinstance(req, BaseReq)
            and req.pdi_command == PdiCommand.BASE_MEMORY
            and req.scope == scope
            and req.tmcc_id == 2
            for req in listener.enqueued
        ), f"Expected BASE_MEMORY tmcc_id=2 for scope {scope}"
