from threading import Event

import pytest

from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.sequence.speed_ramp import RampRegistry, SpeedRamp

from ...test_base import TestBase
from .ramp_test_support import RampEngineState, RampWorkers, Recorder

pytestmark = [
    pytest.mark.usefixtures("ramp_target_update"),
    pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning"),
]


class GatedEngineState(RampEngineState):
    """
    An engine whose momentum read parks the ramp thread on its first pass through the
    loop, so a ramp can be held reliably alive for as long as a test needs it, with no
    sleeps and no races.

    Momentum is the one thing the ramp reads outside every one of its own locks, and it
    reads it before anything reaches the wire, so a ramp held here is demonstrably
    running and yet holds nothing. An abort therefore takes the send gate immediately,
    where a hold placed inside the sender - under the send gate - made every abort wait
    out ABORT_GATE_TIMEOUT.

    The gate opens the way an ungated double behaves; `hold` closes it for the tests
    that need a ramp pinned.
    """

    def __init__(self, **kwargs) -> None:
        self.gate = Event()
        self.gate.set()
        self.running = Event()
        super().__init__(**kwargs)

    @property
    def momentum(self) -> int:
        self.running.set()
        self.gate.wait(5)
        return self._momentum

    @momentum.setter
    def momentum(self, value: int) -> None:
        self._momentum = value

    def hold(self) -> None:
        self.running.clear()
        self.gate.clear()

    def release(self) -> None:
        self.gate.set()


def held_ramp(registry: RampRegistry, state: GatedEngineState, target: int, ramp_workers: RampWorkers) -> SpeedRamp:
    """Start a ramp through the registry and wait until it is demonstrably running."""
    state.hold()
    # The gated double supplies the registry's consumed state interface.
    # noinspection PyTypeChecker
    ramp = registry.ramp_to(state, target, sender=Recorder(), linger=0.0, delay_scale=0.0)
    ramp_workers.track(ramp, release=state.release)
    assert state.running.wait(5) is True
    return ramp


# noinspection PyMethodMayBeStatic
class TestRampRegistry(TestBase):
    """Registry call-site suppressions permit the lightweight worker state interface."""

    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.registry = RampRegistry()

    def teardown_method(self, test_method):
        RampRegistry.reset()
        super().teardown_method(test_method)

    def engine(self, **kwargs) -> GatedEngineState:
        return GatedEngineState(**kwargs)

    #
    # the singleton accessor
    #
    def test_build_returns_one_registry(self):
        assert RampRegistry.build() is RampRegistry.build()

    def test_reset_drops_the_singleton(self):
        first = RampRegistry.build()
        RampRegistry.reset()
        assert RampRegistry.build() is not first

    #
    # keying
    #
    def test_engine_and_train_with_the_same_id_are_distinct_targets(self, ramp_workers):
        engine = self.engine(scope=CommandScope.ENGINE, tmcc_id=12)
        train = self.engine(scope=CommandScope.TRAIN, tmcc_id=12)
        engine_ramp = held_ramp(self.registry, engine, 60, ramp_workers)
        train_ramp = held_ramp(self.registry, train, 40, ramp_workers)

        assert engine_ramp is not train_ramp
        # noinspection PyTypeChecker
        assert self.registry.get(engine) is engine_ramp
        # noinspection PyTypeChecker
        assert self.registry.get(train) is train_ramp
        assert len(self.registry.active_ramps) == 2

    def test_distinct_targets_ramp_concurrently_without_cross_talk(self, ramp_workers):
        states = [
            self.engine(scope=CommandScope.ENGINE, tmcc_id=12),
            self.engine(scope=CommandScope.ENGINE, tmcc_id=13),
            self.engine(scope=CommandScope.TRAIN, tmcc_id=12),
        ]
        targets = [60, 90, 40]
        ramps = [held_ramp(self.registry, s, t, ramp_workers) for s, t in zip(states, targets)]

        assert len({id(r) for r in ramps}) == 3
        assert len({r.ident for r in ramps}) == 3
        for ramp, state, target in zip(ramps, states, targets):
            assert ramp.requested_speed == target
            assert ramp.tmcc_id == state.tmcc_id
            assert ramp.scope == state.scope

    #
    # retarget, never restart
    #
    def test_second_ramp_to_retargets_the_running_thread(self, ramp_workers):
        state = self.engine(tmcc_id=12)
        first = held_ramp(self.registry, state, 60, ramp_workers)

        # noinspection PyTypeChecker
        second = self.registry.ramp_to(state, 120)
        assert second is first
        assert second.ident == first.ident
        assert second.requested_speed == 120
        assert len(self.registry.active_ramps) == 1

    def test_burst_of_requests_yields_one_thread_and_nine_retargets(self, ramp_workers):
        state = self.engine(tmcc_id=12)
        ramps = [held_ramp(self.registry, state, 10, ramp_workers)]
        for target in range(20, 110, 10):
            # noinspection PyTypeChecker
            ramps.append(self.registry.ramp_to(state, target))

        assert len(ramps) == 10
        assert len({id(r) for r in ramps}) == 1
        assert len({r.ident for r in ramps}) == 1
        assert ramps[0].requested_speed == 100
        assert len(self.registry.active_ramps) == 1

    def test_ramp_to_carries_the_dialog_flag_through_a_retarget(self, ramp_workers):
        state = self.engine(tmcc_id=12)
        ramp = held_ramp(self.registry, state, 60, ramp_workers)
        assert ramp.dialog is False

        # noinspection PyTypeChecker
        self.registry.ramp_to(state, 80, dialog=True)
        assert ramp.dialog is True

    #
    # thread hygiene
    #
    def test_every_ramp_thread_is_a_daemon(self, ramp_workers):
        states = [
            self.engine(scope=CommandScope.ENGINE, tmcc_id=12),
            self.engine(scope=CommandScope.TRAIN, tmcc_id=12),
        ]
        for state in states:
            held_ramp(self.registry, state, 60, ramp_workers)
        assert all(r.daemon is True for r in self.registry.active_ramps)
        assert all(r.is_alive() is True for r in self.registry.active_ramps)

    def test_settled_ramps_are_reaped(self, ramp_workers):
        state = RampEngineState(tmcc_id=12)
        # noinspection PyTypeChecker
        ramp = self.registry.ramp_to(state, 12, sender=Recorder(), linger=0.0, delay_scale=0.0)
        ramp_workers.track(ramp)
        ramp.join(timeout=5)

        assert ramp.is_alive() is False
        # noinspection PyTypeChecker
        assert self.registry.get(state) is None
        assert self.registry.active_ramps == []
        assert len(self.registry) == 0

    def test_a_reaped_target_gets_a_new_thread(self, ramp_workers):
        state = self.engine(tmcc_id=12)
        # noinspection PyTypeChecker
        first = self.registry.ramp_to(state, 12, sender=Recorder(), linger=0.0, delay_scale=0.0)
        ramp_workers.track(first, release=state.release)
        first.join(timeout=5)
        assert first.is_alive() is False

        second = held_ramp(self.registry, state, 60, ramp_workers)
        assert second is not first
        assert len(self.registry.active_ramps) == 1

    #
    # aborts
    #
    def test_abort_stops_and_forgets_one_ramp(self, ramp_workers):
        state = self.engine(tmcc_id=12)
        ramp = held_ramp(self.registry, state, 60, ramp_workers)

        # noinspection PyTypeChecker
        self.registry.abort(state, "test")
        assert ramp.is_active is False
        assert ramp.abort_reason == "test"
        # noinspection PyTypeChecker
        assert self.registry.get(state) is None
        assert self.registry.active_ramps == []
        assert ramp.is_alive() is True
        assert ramp_workers.workers == (ramp,)

        ramp_workers.cleanup()

        assert state.gate.is_set() is True
        assert ramp.is_alive() is False
        assert ramp_workers.workers == ()

    def test_abort_of_an_unknown_target_is_harmless(self):
        # noinspection PyTypeChecker
        self.registry.abort(RampEngineState(tmcc_id=99))

    def test_abort_all_by_scope_leaves_the_other_scope_alone(self, ramp_workers):
        engine = self.engine(scope=CommandScope.ENGINE, tmcc_id=12)
        train = self.engine(scope=CommandScope.TRAIN, tmcc_id=12)
        engine_ramp = held_ramp(self.registry, engine, 60, ramp_workers)
        train_ramp = held_ramp(self.registry, train, 40, ramp_workers)

        self.registry.abort_all(scope=CommandScope.ENGINE, reason="halt")
        assert engine_ramp.is_active is False
        assert engine_ramp.abort_reason == "halt"
        assert train_ramp.is_active is True
        # noinspection PyTypeChecker
        assert self.registry.get(engine) is None
        # noinspection PyTypeChecker
        assert self.registry.get(train) is train_ramp

    def test_abort_all_stops_every_scope(self, ramp_workers):
        engine = self.engine(scope=CommandScope.ENGINE, tmcc_id=12)
        train = self.engine(scope=CommandScope.TRAIN, tmcc_id=12)
        ramps = [
            held_ramp(self.registry, engine, 60, ramp_workers),
            held_ramp(self.registry, train, 40, ramp_workers),
        ]

        self.registry.abort_all()
        assert all(r.is_active is False for r in ramps)
        assert self.registry.active_ramps == []


# noinspection PyMethodMayBeStatic
class TestEngineStateRoutesThroughTheRegistry(TestBase):
    def teardown_method(self, test_method):
        RampRegistry.reset()
        super().teardown_method(test_method)

    # Exercise real routing methods with a gated state double, without real transport.
    # noinspection PyTypeChecker
    def test_state_ramp_to_registers_and_mirrors_the_handle(self, ramp_workers):
        from src.pytrain.db.engine_state import EngineState

        state = GatedEngineState(tmcc_id=12)
        ramp = held_ramp(RampRegistry.build(), state, 60, ramp_workers)

        # what EngineState.ramp_to does: retarget through the registry, mirror the handle
        state._ramp = None
        again = EngineState.ramp_to(state, 120)
        assert again is ramp
        assert state._ramp is ramp
        assert ramp.requested_speed == 120

        EngineState.abort_ramp(state, "test")
        assert state._ramp is None
        assert ramp.is_active is False
        assert RampRegistry.build().get(state) is None
