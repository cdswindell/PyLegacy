"""Focused compatibility checks, not a complete model of EngineState."""

from threading import Event, Thread
from unittest.mock import patch

import pytest

from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.db.comp_data import CompData
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_state import EngineState, TrainState
from src.pytrain.pdi.base3_db_refresh_manager import Base3DbRefreshManager
from src.pytrain.protocol.constants import CommandScope, LEGACY_CONTROL_TYPE, TMCC_CONTROL_TYPE
from src.pytrain.protocol.sequence.speed_ramp import LEGACY_SPEED_MAX, TMCC1_SPEED_MAX, UNSET_MAX_SPEED
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, reset_speed_to_rpm_cache

from .ramp_test_support import FakeEngineState, RampCleanupError, RampEngineState, Recorder, build_ramp, run_ramp

pytestmark = pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning")


def test_refresh_scheduling_is_recorded_without_starting_worker(ramp_refresh_scheduling, ramp_target_update):
    state = RampEngineState()

    with patch.object(Base3DbRefreshManager, "_ensure_started", autospec=True) as ensure_started:
        ramp, _ = run_ramp(state, 12)

    ramp_target_update.assert_called_once_with("RAMP_TARGET_SPEED", 12, state, do_async=False, refresh=False)
    ramp_refresh_scheduling["flush"].assert_called_once_with(state)
    ramp_refresh_scheduling["request_refresh"].assert_called_once_with(state)
    ensure_started.assert_not_called()
    assert ramp.is_active is False
    assert state.is_ramping is False


@pytest.fixture(params=[CommandScope.ENGINE, CommandScope.TRAIN])
def real_states(request, monkeypatch):
    """Initialize records without starting transport or requesting roster data."""
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda _cls: False))

    # Seed received-record internals without sending commands through the dispatcher.
    # noinspection PyProtectedMember
    def create(*, address: int = 12, is_legacy: bool = True) -> EngineState:
        scope = request.param
        state = TrainState(scope) if scope == CommandScope.TRAIN else EngineState(scope)
        state.initialize(scope, address)
        state._address = address
        state._empty = False
        state._is_legacy = is_legacy
        data = state.comp_data
        assert isinstance(data, CompData)
        data._control_type = LEGACY_CONTROL_TYPE if is_legacy else TMCC_CONTROL_TYPE
        return state

    return create


# The metadata flag and record number are independent inputs to the real property.
# noinspection PyProtectedMember
@pytest.mark.parametrize("address", [12, 1234])
@pytest.mark.parametrize(
    "metadata_is_d4, record_no, expected",
    [(False, None, False), (False, 17, False), (True, None, False), (True, 0, True), (True, 17, True)],
)
def test_worker_d4_value_matches_real_metadata(real_states, address, metadata_is_d4, record_no, expected):
    state = real_states(address=address)
    state._is_d4 = metadata_is_d4
    state._d4_rec_no = record_no
    double = RampEngineState(scope=state.scope, tmcc_id=address, is_d4=expected)

    assert state.record_no == record_no
    assert state.is_d4 is expected
    assert double.is_d4 is state.is_d4
    assert (double.scope, double.tmcc_id) == (state.scope, state.tmcc_id)


# Raw database limits must pass through the real decoder before entering the double.
# noinspection PyProtectedMember
@pytest.mark.parametrize("is_legacy", [True, False])
@pytest.mark.parametrize(
    "raw_max, raw_limit, legacy_ceiling, tmcc1_ceiling",
    [
        (None, None, LEGACY_SPEED_MAX, TMCC1_SPEED_MAX),
        (UNSET_MAX_SPEED, UNSET_MAX_SPEED, LEGACY_SPEED_MAX, TMCC1_SPEED_MAX),
        (0, 0, LEGACY_SPEED_MAX, TMCC1_SPEED_MAX),
        (120, UNSET_MAX_SPEED, 120, 19),
        (UNSET_MAX_SPEED, 100, 100, 16),
        (120, 100, 100, 16),
        (100, 120, 100, 16),
        (199, 199, LEGACY_SPEED_MAX, TMCC1_SPEED_MAX),
        (None, 100, 100, 16),
        (120, None, 120, 19),
        (0, 100, 100, 16),
        (120, 0, 120, 19),
    ],
)
def test_double_ceiling_matches_decoded_real_limits(
    real_states, is_legacy, raw_max, raw_limit, legacy_ceiling, tmcc1_ceiling
):
    state = real_states(is_legacy=is_legacy)
    data = state.comp_data
    assert isinstance(data, CompData)
    data._max_speed = raw_max
    data._speed_limit = raw_limit
    double = FakeEngineState(is_legacy=is_legacy, max_speed=state.max_speed, speed_limit=state.speed_limit)

    assert state.is_legacy is is_legacy
    assert state.speed_max == (legacy_ceiling if is_legacy else tmcc1_ceiling)
    assert double.speed_max == state.speed_max


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize(
    "is_legacy, is_d4",
    [(False, False), (True, False), (True, True)],
    ids=["tmcc1", "legacy", "d4"],
)
def test_worker_double_completes_synchronously(
    pdi_send, ramp_target_update, ramp_refresh_scheduling, scope, is_legacy, is_d4
):
    state = RampEngineState(scope=scope, is_legacy=is_legacy, is_rpm=is_legacy, is_d4=is_d4, speed_limit=12)

    try:
        # run_ramp calls the actual run() entry point: missing properties fail on this thread.
        ramp, recorder = run_ramp(state, 16)

        pdi_send.assert_not_called()
        ramp_target_update.assert_called_once_with("RAMP_TARGET_SPEED", 12, state, do_async=False, refresh=False)
        ramp_refresh_scheduling["flush"].assert_called_once_with(state)
        ramp_refresh_scheduling["request_refresh"].assert_called_once_with(state)
        speed_command = TMCC2EngineCommandEnum.ABSOLUTE_SPEED if is_legacy else TMCC1EngineCommandEnum.ABSOLUTE_SPEED
        assert recorder.of(speed_command) == list(range(3 if is_legacy else 1, 13, 3 if is_legacy else 1))
        assert all(address == state.tmcc_id and sent_scope == scope for _, address, _, sent_scope in recorder.sent)
        assert ramp.requested_speed == 16
        assert ramp.target_speed == ramp.commanded_speed == 12
        assert ramp.abort_reason is None
        assert ramp.is_active is False
        assert state.is_ramping is False
        assert ramp.ident is None
        assert ramp.is_alive() is False
    finally:
        reset_speed_to_rpm_cache()


def test_cleanup_aborts_a_live_ramp_releases_its_gate_and_verifies_termination(monkeypatch, ramp_workers):
    entered, resume = Event(), Event()
    state = RampEngineState()
    recorder = Recorder()
    ramp = build_ramp(state, 12, recorder)

    def pause(_delay):
        entered.set()
        assert resume.wait(2)

    monkeypatch.setattr(ramp, "_pause", pause)
    ramp_workers.track(ramp, release=resume.set)
    ramp.start()
    assert entered.wait(2)
    assert ramp.is_alive() is True
    assert state.is_ramping is True

    ramp_workers.cleanup()

    assert resume.is_set() is True
    assert ramp.is_alive() is False
    assert ramp.abort_reason == "test cleanup"
    assert state.is_ramping is False
    assert recorder.speeds == [3]
    assert ramp_workers.workers == ()


class ControlledWorker(Thread):
    """Model cleanup failures and survivors without starting or leaking a real thread."""

    def __init__(self, name: str, events: list[tuple[str, str]]) -> None:
        super().__init__(name=name)
        self.events = events
        self.alive = True
        self.was_started = True
        self.survives_join = False
        self.failure_phase: str | None = None
        self.failure: BaseException = RuntimeError("controlled cleanup failure")
        self.timeouts: list[float | None] = []

    @property
    def ident(self) -> int | None:
        return 1 if self.was_started else None

    def record(self, phase: str) -> None:
        self.events.append((self.name, phase))
        if self.failure_phase == phase:
            raise self.failure

    def abort(self) -> None:
        self.record("abort")

    def release(self) -> None:
        self.record("release")

    def join(self, timeout: float | None = None) -> None:
        self.timeouts.append(timeout)
        self.record("join")
        self.alive = self.survives_join

    def is_alive(self) -> bool:
        self.record("is_alive")
        return self.alive


def test_cleanup_aborts_and_releases_all_gates_before_bounded_joins(ramp_workers):
    events = []
    workers = [ControlledWorker(name, events) for name in ("first", "second")]
    for worker in workers:
        assert ramp_workers.track(worker, abort=worker.abort, release=worker.release) is worker

    ramp_workers.cleanup(timeout=0.25)

    assert events == [
        ("first", "abort"),
        ("second", "abort"),
        ("first", "release"),
        ("second", "release"),
        ("first", "join"),
        ("first", "is_alive"),
        ("second", "join"),
        ("second", "is_alive"),
    ]
    assert all(worker.timeouts == [0.25] and worker.alive is False for worker in workers)
    assert ramp_workers.workers == ()


@pytest.mark.parametrize(
    "phase, diagnostic_phase",
    [("abort", "abort"), ("release", "release gate"), ("join", "join"), ("is_alive", "verify termination")],
)
def test_cleanup_reports_errors_after_attempting_remaining_workers_and_retains_failed_handles(
    ramp_workers, phase, diagnostic_phase
):
    events = []
    broken = ControlledWorker("broken", events)
    healthy = ControlledWorker("healthy", events)
    broken.failure_phase = phase
    for worker in (broken, healthy):
        ramp_workers.track(worker, abort=worker.abort, release=worker.release)
    ramp_workers.track(broken, release=lambda: events.append(("broken", "second gate")))

    try:
        with pytest.raises(RampCleanupError, match="Ramp worker cleanup failed") as raised:
            ramp_workers.cleanup(timeout=0.25)

        failure = raised.value.failures[0]
        assert failure.worker is broken
        assert failure.phase == diagnostic_phase
        assert failure.error is broken.failure
        assert f"broken (ident=1): {diagnostic_phase}\n" in str(raised.value)
        assert "RuntimeError: controlled cleanup failure" in str(raised.value)
        assert "raise self.failure" in str(raised.value)
        assert events == [
            ("broken", "abort"),
            ("healthy", "abort"),
            ("broken", "release"),
            ("broken", "second gate"),
            ("healthy", "release"),
            ("broken", "join"),
            ("broken", "is_alive"),
            ("healthy", "join"),
            ("healthy", "is_alive"),
        ]
        assert len(raised.value.failures) == (2 if phase == "join" else 1)
        if phase == "join":
            survivor_failure = raised.value.failures[1]
            assert survivor_failure.worker is broken
            assert survivor_failure.phase == "verify termination"
            assert isinstance(survivor_failure.error, AssertionError)
            assert "broken (ident=1): verify termination\n" in str(raised.value)
            assert "Worker survived cleanup after a 0.25-second join" in str(raised.value)
        assert broken.timeouts == healthy.timeouts == [0.25]
        assert healthy.alive is False
        assert ramp_workers.workers == (broken,)

        with pytest.raises(RampCleanupError, match="Ramp worker cleanup failed") as retried:
            ramp_workers.cleanup(timeout=0.25)
        assert retried.value.failures[0].error is broken.failure
        assert len(retried.value.failures) == len(raised.value.failures)
        assert str(retried.value).count(f"broken (ident=1): {diagnostic_phase}\n") == 1
        assert ramp_workers.workers == (broken,)
    finally:
        broken.failure_phase = None

    ramp_workers.cleanup(timeout=0.25)
    assert broken.timeouts == [0.25, 0.25, 0.25]
    assert healthy.timeouts == [0.25]
    assert broken.alive is False
    assert ramp_workers.workers == ()


def test_cleanup_aggregates_worker_phase_and_traceback_diagnostics(ramp_workers):
    events = []
    first = ControlledWorker("first", events)
    first.failure_phase = "abort"
    first.failure = ValueError("first failure")
    second = ControlledWorker("second", events)
    second.failure_phase = "release"
    second.failure = RuntimeError("second failure")
    second.failure.__cause__ = OSError("original cause")
    healthy = ControlledWorker("healthy", events)
    for worker in (first, second, healthy):
        ramp_workers.track(worker, abort=worker.abort, release=worker.release)

    try:
        with pytest.raises(RampCleanupError, match="Ramp worker cleanup failed") as raised:
            ramp_workers.cleanup(timeout=0.25)

        assert [(failure.worker, failure.phase, failure.error) for failure in raised.value.failures] == [
            (first, "abort", first.failure),
            (second, "release gate", second.failure),
        ]
        diagnostics = str(raised.value)
        assert "first (ident=1): abort" in diagnostics
        assert "second (ident=1): release gate" in diagnostics
        assert "ValueError: first failure" in diagnostics
        assert "RuntimeError: second failure" in diagnostics
        assert "OSError: original cause" in diagnostics
        assert diagnostics.count("Traceback (most recent call last):") == 2
        assert diagnostics.count("raise self.failure") == 2
        assert all(worker.timeouts == [0.25] and worker.alive is False for worker in (first, second, healthy))
        assert ramp_workers.workers == (first, second)
    finally:
        first.failure_phase = second.failure_phase = None

    ramp_workers.cleanup(timeout=0.25)
    assert first.timeouts == second.timeouts == [0.25, 0.25]
    assert healthy.timeouts == [0.25]
    assert ramp_workers.workers == ()


def test_cleanup_reports_survivors_and_keeps_them_for_an_explicit_retry(ramp_workers):
    events = []
    survivor = ControlledWorker("survivor", events)
    survivor.survives_join = True
    healthy = ControlledWorker("healthy", events)
    for worker in (survivor, healthy):
        ramp_workers.track(worker, abort=worker.abort, release=worker.release)

    try:
        with pytest.raises(RampCleanupError, match="Ramp worker cleanup failed") as raised:
            ramp_workers.cleanup(timeout=0.25)

        assert len(raised.value.failures) == 1
        failure = raised.value.failures[0]
        assert failure.worker is survivor
        assert failure.phase == "verify termination"
        error = failure.error
        assert isinstance(error, AssertionError)
        assert "survived cleanup after a 0.25-second join" in str(error)
        assert "survivor (ident=1): verify termination\n" in str(raised.value)
        assert "AssertionError: Worker survived cleanup after a 0.25-second join" in str(raised.value)
        assert survivor.timeouts == healthy.timeouts == [0.25]
        assert healthy.alive is False
        assert ramp_workers.workers == (survivor,)
    finally:
        survivor.survives_join = False

    ramp_workers.cleanup(timeout=0.25)
    assert survivor.alive is False
    assert ramp_workers.workers == ()


@pytest.mark.parametrize("phase", ["abort", "release", "join", "is_alive"])
@pytest.mark.parametrize("cancellation", [KeyboardInterrupt, SystemExit])
def test_cleanup_preserves_genuine_cancellation_and_ownership(ramp_workers, phase, cancellation):
    worker = ControlledWorker("canceled", [])
    worker.failure_phase = phase
    worker.failure = cancellation("cancel cleanup")
    ramp_workers.track(worker, abort=worker.abort, release=worker.release)

    try:
        with pytest.raises(cancellation, match="cancel cleanup") as raised:
            ramp_workers.cleanup()

        assert raised.value is worker.failure
        assert ramp_workers.workers == (worker,)
    finally:
        worker.failure_phase = None

    ramp_workers.cleanup()
    assert ramp_workers.workers == ()


def test_tracking_twice_keeps_one_handle_and_all_gate_releases(ramp_workers):
    events = []
    worker = ControlledWorker("worker", events)
    ramp_workers.track(worker, abort=worker.abort, release=worker.release)
    ramp_workers.track(worker, release=lambda: events.append(("worker", "second gate")))
    assert ramp_workers.workers == (worker,)

    ramp_workers.cleanup()

    assert events == [
        ("worker", "abort"),
        ("worker", "release"),
        ("worker", "second gate"),
        ("worker", "join"),
        ("worker", "is_alive"),
    ]
    assert worker.timeouts == [1.0]
    assert ramp_workers.workers == ()


def test_cleanup_does_not_join_an_unstarted_worker(ramp_workers):
    worker = ControlledWorker("unstarted", [])
    worker.was_started = worker.alive = False
    ramp_workers.track(worker, abort=worker.abort, release=worker.release)

    ramp_workers.cleanup()

    assert worker.events == [("unstarted", "abort"), ("unstarted", "release"), ("unstarted", "is_alive")]
    assert worker.timeouts == []
    assert ramp_workers.workers == ()
