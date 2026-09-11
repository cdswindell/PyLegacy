from threading import Event

from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.sequence.speed_ramp import RampRegistry, SpeedRamp

from ...test_base import TestBase
from .test_speed_ramp import RampEngineState, Recorder


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


def held_ramp(registry: RampRegistry, state: GatedEngineState, target: int) -> SpeedRamp:
    """Start a ramp through the registry and wait until it is demonstrably running."""
    state.hold()
    ramp = registry.ramp_to(state, target, sender=Recorder(), linger=0.0, delay_scale=0.0)
    assert state.running.wait(5) is True
    return ramp


# noinspection PyMethodMayBeStatic
class TestRampRegistry(TestBase):
    def setup_method(self, test_method):
        super().setup_method(test_method)
        self.registry = RampRegistry()
        self.states: list[GatedEngineState] = []

    def teardown_method(self, test_method):
        # the handles are taken before the aborts, because abort_all forgets them
        ramps = self.registry.active_ramps
        self.registry.abort_all()
        for state in self.states:
            state.release()
        for ramp in ramps:
            ramp.join(timeout=5)
        RampRegistry.reset()
        super().teardown_method(test_method)

    def engine(self, **kwargs) -> GatedEngineState:
        state = GatedEngineState(**kwargs)
        self.states.append(state)
        return state

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
    def test_engine_and_train_with_the_same_id_are_distinct_targets(self):
        engine = self.engine(scope=CommandScope.ENGINE, tmcc_id=12)
        train = self.engine(scope=CommandScope.TRAIN, tmcc_id=12)
        engine_ramp = held_ramp(self.registry, engine, 60)
        train_ramp = held_ramp(self.registry, train, 40)

        assert engine_ramp is not train_ramp
        assert self.registry.get(engine) is engine_ramp
        assert self.registry.get(train) is train_ramp
        assert len(self.registry.active_ramps) == 2

    def test_distinct_targets_ramp_concurrently_without_cross_talk(self):
        states = [
            self.engine(scope=CommandScope.ENGINE, tmcc_id=12),
            self.engine(scope=CommandScope.ENGINE, tmcc_id=13),
            self.engine(scope=CommandScope.TRAIN, tmcc_id=12),
        ]
        targets = [60, 90, 40]
        ramps = [held_ramp(self.registry, s, t) for s, t in zip(states, targets)]

        assert len({id(r) for r in ramps}) == 3
        assert len({r.ident for r in ramps}) == 3
        for ramp, state, target in zip(ramps, states, targets):
            assert ramp.requested_speed == target
            assert ramp.tmcc_id == state.tmcc_id
            assert ramp.scope == state.scope

    #
    # retarget, never restart
    #
    def test_second_ramp_to_retargets_the_running_thread(self):
        state = self.engine(tmcc_id=12)
        first = held_ramp(self.registry, state, 60)

        second = self.registry.ramp_to(state, 120)
        assert second is first
        assert second.ident == first.ident
        assert second.requested_speed == 120
        assert len(self.registry.active_ramps) == 1

    def test_burst_of_requests_yields_one_thread_and_nine_retargets(self):
        state = self.engine(tmcc_id=12)
        ramps = [held_ramp(self.registry, state, 10)]
        for target in range(20, 110, 10):
            ramps.append(self.registry.ramp_to(state, target))

        assert len(ramps) == 10
        assert len({id(r) for r in ramps}) == 1
        assert len({r.ident for r in ramps}) == 1
        assert ramps[0].requested_speed == 100
        assert len(self.registry.active_ramps) == 1

    def test_ramp_to_carries_the_dialog_flag_through_a_retarget(self):
        state = self.engine(tmcc_id=12)
        ramp = held_ramp(self.registry, state, 60)
        assert ramp.dialog is False

        self.registry.ramp_to(state, 80, dialog=True)
        assert ramp.dialog is True

    #
    # thread hygiene
    #
    def test_every_ramp_thread_is_a_daemon(self):
        states = [
            self.engine(scope=CommandScope.ENGINE, tmcc_id=12),
            self.engine(scope=CommandScope.TRAIN, tmcc_id=12),
        ]
        for state in states:
            held_ramp(self.registry, state, 60)
        assert all(r.daemon is True for r in self.registry.active_ramps)
        assert all(r.is_alive() is True for r in self.registry.active_ramps)

    def test_settled_ramps_are_reaped(self):
        state = RampEngineState(tmcc_id=12)
        ramp = self.registry.ramp_to(state, 12, sender=Recorder(), linger=0.0, delay_scale=0.0)
        ramp.join(timeout=5)

        assert ramp.is_alive() is False
        assert self.registry.get(state) is None
        assert self.registry.active_ramps == []
        assert len(self.registry) == 0

    def test_a_reaped_target_gets_a_new_thread(self):
        state = self.engine(tmcc_id=12)
        first = self.registry.ramp_to(state, 12, sender=Recorder(), linger=0.0, delay_scale=0.0)
        first.join(timeout=5)

        second = held_ramp(self.registry, state, 60)
        assert second is not first
        assert len(self.registry.active_ramps) == 1

    #
    # aborts
    #
    def test_abort_stops_and_forgets_one_ramp(self):
        state = self.engine(tmcc_id=12)
        ramp = held_ramp(self.registry, state, 60)

        self.registry.abort(state, "test")
        assert ramp.is_active is False
        assert ramp.abort_reason == "test"
        assert self.registry.get(state) is None

    def test_abort_of_an_unknown_target_is_harmless(self):
        self.registry.abort(RampEngineState(tmcc_id=99))

    def test_abort_all_by_scope_leaves_the_other_scope_alone(self):
        engine = self.engine(scope=CommandScope.ENGINE, tmcc_id=12)
        train = self.engine(scope=CommandScope.TRAIN, tmcc_id=12)
        engine_ramp = held_ramp(self.registry, engine, 60)
        train_ramp = held_ramp(self.registry, train, 40)

        self.registry.abort_all(scope=CommandScope.ENGINE, reason="halt")
        assert engine_ramp.is_active is False
        assert engine_ramp.abort_reason == "halt"
        assert train_ramp.is_active is True
        assert self.registry.get(engine) is None
        assert self.registry.get(train) is train_ramp

    def test_abort_all_stops_every_scope(self):
        engine = self.engine(scope=CommandScope.ENGINE, tmcc_id=12)
        train = self.engine(scope=CommandScope.TRAIN, tmcc_id=12)
        ramps = [
            held_ramp(self.registry, engine, 60),
            held_ramp(self.registry, train, 40),
        ]

        self.registry.abort_all()
        assert all(r.is_active is False for r in ramps)
        assert self.registry.active_ramps == []


# noinspection PyMethodMayBeStatic
class TestEngineStateRoutesThroughTheRegistry(TestBase):
    def teardown_method(self, test_method):
        RampRegistry.reset()
        super().teardown_method(test_method)

    def test_state_ramp_to_registers_and_mirrors_the_handle(self):
        from src.pytrain.db.engine_state import EngineState

        state = GatedEngineState(tmcc_id=12)
        ramp = None
        try:
            state.hold()
            ramp = RampRegistry.build().ramp_to(state, 60, sender=Recorder(), linger=0.0, delay_scale=0.0)
            assert state.running.wait(5) is True

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
        finally:
            state.release()
            if ramp is not None:
                ramp.join(timeout=5)
