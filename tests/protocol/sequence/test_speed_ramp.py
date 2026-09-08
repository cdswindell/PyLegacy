from typing import Callable

import pytest

from src.pytrain.protocol.constants import CommandScope, PROGRAM_NAME
from src.pytrain.protocol.sequence.speed_ramp import (
    DEFAULT_RAMP_LINGER,
    MAX_RPM,
    SpeedRamp,
    biased_rpm,
    labor_delta,
)
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum,
    reset_speed_to_rpm_cache,
    tmcc2_speed_to_rpm,
)

from ...test_base import TestBase
from .test_speed_ramp_geometry import UNSET_MAX_SPEED, FakeEngineState

SPEED_ENUMS = {TMCC1EngineCommandEnum.ABSOLUTE_SPEED, TMCC2EngineCommandEnum.ABSOLUTE_SPEED}
SCALED_MAX_SPEED = 100


class RampEngineState(FakeEngineState):
    """The step 2 double, plus the handful of attributes the ramp thread itself reads."""

    def __init__(self, *, scope: CommandScope = CommandScope.ENGINE, tmcc_id: int = 12, **kwargs) -> None:
        super().__init__(**kwargs)
        self.scope = scope
        self.tmcc_id = tmcc_id
        self.is_ramping = False


class Recorder:
    """A recording send path: the ramp's command stream, with a hook to poke it mid-flight."""

    def __init__(self, hook: Callable[["Recorder", int], None] = None) -> None:
        self.sent: list[tuple] = []
        self.hook = hook

    def __call__(self, command, address: int, data: int, scope: CommandScope) -> None:
        self.sent.append((command, address, data, scope))
        if self.hook is not None:
            self.hook(self, len(self.sent))

    def of(self, command) -> list[int]:
        return [data for cmd, _, data, _ in self.sent if cmd == command]

    @property
    def speeds(self) -> list[int]:
        return [data for cmd, _, data, _ in self.sent if cmd in SPEED_ENUMS]

    @property
    def rpms(self) -> list[int]:
        return self.of(TMCC2EngineCommandEnum.DIESEL_RPM)

    @property
    def labors(self) -> list[int]:
        return self.of(TMCC2EngineCommandEnum.ENGINE_LABOR)

    @property
    def commands(self) -> list:
        return [cmd for cmd, _, _, _ in self.sent]


def build_ramp(state: RampEngineState, target: int, recorder: Recorder, **kwargs) -> SpeedRamp:
    """A ramp whose waits collapse to nothing, so the loop can be driven synchronously."""
    kwargs.setdefault("linger", 0.0)
    kwargs.setdefault("delay_scale", 0.0)
    return SpeedRamp(state, target, sender=recorder, **kwargs)


def run_ramp(state: RampEngineState, target: int, recorder: Recorder = None, **kwargs) -> tuple[SpeedRamp, Recorder]:
    recorder = recorder if recorder is not None else Recorder()
    ramp = build_ramp(state, target, recorder, **kwargs)
    ramp.run()
    return ramp, recorder


def expected_rpms(speeds: list[int], bias: int, max_speed: int = None, initial: int = None) -> list[int]:
    """
    The RPM stream an accelerating ramp should emit: the biased notch for each speed it
    commands, de-duplicated against the value already in effect, so a notch the engine is
    already sitting at is never re-announced. Derived from the table, never typed in.
    """
    expected: list[int] = []
    last = initial
    for speed in speeds:
        rpm = biased_rpm(speed, bias, max_speed)
        if rpm != last:
            expected.append(rpm)
            last = rpm
    return expected


# noinspection PyMethodMayBeStatic
class TestSpeedRamp(TestBase):
    def teardown_method(self, test_method):
        reset_speed_to_rpm_cache()
        super().teardown_method(test_method)

    #
    # thread identity
    #
    def test_thread_is_a_named_daemon(self):
        state = RampEngineState(scope=CommandScope.TRAIN, tmcc_id=7)
        ramp = build_ramp(state, 40, Recorder())
        assert ramp.daemon is True
        assert ramp.name == f"{PROGRAM_NAME} Speed Ramp Train 7"

    def test_thread_runs_and_exits_on_its_own(self):
        state = RampEngineState()
        recorder = Recorder()
        ramp = build_ramp(state, 12, recorder)
        ramp.start()
        ramp.join(timeout=5)
        assert ramp.is_alive() is False
        assert ramp.is_active is False
        assert recorder.speeds[-1] == 12
        assert state.is_ramping is False

    #
    # ramp up and down
    #
    def test_ramp_up_is_monotonic_and_lands_exactly(self):
        state = RampEngineState(speed=0, max_speed=UNSET_MAX_SPEED)
        ramp, recorder = run_ramp(state, 60)
        speeds = recorder.speeds
        assert speeds[0] == 3
        assert speeds == sorted(speeds)
        assert speeds[-1] == 60
        assert max(speeds) == 60
        assert ramp.commanded_speed == 60

    def test_ramp_down_is_monotonic_and_drops_rpm_and_effort_up_front(self):
        state = RampEngineState(speed=120, rpm=tmcc2_speed_to_rpm(120), labor=12)
        ramp, recorder = run_ramp(state, 20)
        speeds = recorder.speeds
        assert speeds == sorted(speeds, reverse=True)
        assert speeds[-1] == 20
        # the very first two commands are the up front effort and RPM drop
        assert recorder.commands[0] == TMCC2EngineCommandEnum.ENGINE_LABOR
        assert recorder.commands[1] == TMCC2EngineCommandEnum.DIESEL_RPM
        assert recorder.rpms[0] == biased_rpm(20, ramp.rpm_bias)
        # RPM is dropped once, not step by step
        assert len(recorder.rpms) == 1

    #
    # retarget
    #
    def test_retarget_up_to_up_continues_from_the_commanded_speed(self):
        state = RampEngineState(speed=0)

        def hook(_rec: Recorder, count: int) -> None:
            if count == 1:
                ramp.retarget(60)

        recorder = Recorder(hook)
        ramp = build_ramp(state, 12, recorder)
        ramp.run()
        speeds = recorder.speeds
        assert speeds == sorted(speeds)
        assert len(speeds) == len(set(speeds))
        assert speeds[-1] == 60

    def test_retarget_up_to_down_reverses_from_the_commanded_speed(self):
        state = RampEngineState(speed=0)

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 4 and ramp.requested_speed == 90:
                ramp.retarget(6)

        recorder = Recorder(hook)
        ramp = build_ramp(state, 90, recorder)
        ramp.run()
        speeds = recorder.speeds
        turn = speeds.index(max(speeds))
        assert speeds[: turn + 1] == sorted(speeds[: turn + 1])
        assert speeds[turn:] == sorted(speeds[turn:], reverse=True)
        assert speeds[-1] == 6
        # the reversal happens from where the ramp actually was, not from state.speed
        assert max(speeds) == 12

    def test_retarget_does_not_resample_the_effort_baseline(self):
        state = RampEngineState(speed=0, labor=20)

        def hook(_rec: Recorder, count: int) -> None:
            if count == 1:
                state.labor = 3
                ramp.retarget(30)

        recorder = Recorder(hook)
        ramp = build_ramp(state, 12, recorder)
        ramp.run()
        assert ramp.init_labor == 20
        assert recorder.labors[-1] == 20

    #
    # abort
    #
    def test_abort_mid_ramp_sends_nothing_further(self):
        state = RampEngineState(speed=0)

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 3:
                ramp.abort("test")

        recorder = Recorder(hook)
        ramp = build_ramp(state, 120, recorder)
        ramp.run()
        assert len(recorder.speeds) == 3
        assert recorder.speeds[-1] == 9
        assert ramp.commanded_speed == 9
        assert ramp.abort_reason == "test"
        assert ramp.is_active is False
        # nothing further, in particular no settle at the target
        assert 120 not in recorder.speeds

    def test_abort_before_the_first_step(self):
        state = RampEngineState(speed=0)
        recorder = Recorder()
        ramp = build_ramp(state, 60, recorder)
        ramp.abort("early")
        ramp.run()
        assert recorder.sent == []

    #
    # live momentum
    #
    def test_momentum_raised_mid_ramp_changes_the_next_increment(self):
        state = RampEngineState(speed=0, momentum=0)

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 2:
                state.momentum = 6

        recorder = Recorder(hook)
        ramp = build_ramp(state, 30, recorder)
        ramp.run()
        speeds = recorder.speeds
        assert speeds[:2] == [3, 6]
        # increment 3 easing to 1 on the very next step
        assert speeds[2] == 7
        deltas = [b - a for a, b in zip(speeds[2:], speeds[3:])]
        assert set(deltas) == {1}

    #
    # the live speed ceiling
    #
    def test_speed_limit_lowered_mid_ramp_caps_the_ramp(self):
        state = RampEngineState(speed=0)

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 2:
                state.speed_limit = 40

        recorder = Recorder(hook)
        ramp = build_ramp(state, 120, recorder)
        ramp.run()
        assert max(recorder.speeds) == 40
        assert recorder.speeds[-1] == 40
        # the operator's intent survives the clamp
        assert ramp.requested_speed == 120

    @pytest.mark.parametrize("cleared", [180, UNSET_MAX_SPEED])
    def test_speed_limit_raised_or_cleared_mid_ramp_resumes_the_original_target(self, cleared):
        state = RampEngineState(speed=0, speed_limit=40)

        def hook(rec: Recorder, _count: int) -> None:
            if max(rec.speeds, default=0) == 40:
                state.speed_limit = cleared

        recorder = Recorder(hook)
        ramp = build_ramp(state, 120, recorder)
        ramp.run()
        assert recorder.speeds[-1] == 120
        assert ramp.commanded_speed == 120

    def test_speed_limit_below_the_commanded_speed_reverses_the_ramp(self):
        state = RampEngineState(speed=80, rpm=tmcc2_speed_to_rpm(80))

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 1:
                state.speed_limit = 20

        recorder = Recorder(hook)
        ramp = build_ramp(state, 120, recorder)
        ramp.run()
        assert recorder.speeds[0] > 80
        assert recorder.speeds[-1] == 20
        assert min(recorder.speeds) == 20

    def test_max_speed_and_speed_limit_together_take_the_lower(self):
        state = RampEngineState(speed=0, max_speed=100, speed_limit=40)
        ramp, recorder = run_ramp(state, 199)
        assert recorder.speeds[-1] == 40
        assert ramp.target_speed == 40

    #
    # settle
    #
    def test_settle_sends_the_target_once_with_biased_rpm_and_restored_effort(self):
        # the plan's example: speed 30 reporting RPM 3 where the table says 2 is a +1 bias
        state = RampEngineState(speed=30, rpm=tmcc2_speed_to_rpm(30) + 1, labor=17)
        ramp, recorder = run_ramp(state, 60)
        assert ramp.rpm_bias == 1
        assert recorder.speeds.count(60) == 1
        assert recorder.rpms[-1] == min(MAX_RPM, tmcc2_speed_to_rpm(60) + 1)
        assert recorder.labors[-1] == 17
        assert state.is_ramping is False
        # every RPM the ramp emitted carries the bias, and none is re-announced
        assert recorder.rpms == expected_rpms(recorder.speeds, 1, initial=state.rpm)

    def test_target_equals_current_speed_sends_one_absolute_speed(self):
        state = RampEngineState(speed=45, rpm=tmcc2_speed_to_rpm(45), labor=12)
        ramp, recorder = run_ramp(state, 45)
        assert recorder.speeds == [45]
        assert ramp.commanded_speed == 45
        assert state.is_ramping is False

    def test_effort_follows_the_shared_curve_and_only_on_change(self):
        state = RampEngineState(speed=0, labor=12)
        ramp, recorder = run_ramp(state, 60)
        expected = []
        for speed in recorder.speeds[:-1]:
            labor = labor_delta(speed, 60, 12)
            if not expected or labor != expected[-1]:
                expected.append(labor)
        expected.append(12)
        assert recorder.labors == expected

    def test_rpm_is_emitted_only_on_change(self):
        state = RampEngineState(speed=0, rpm=0)
        ramp, recorder = run_ramp(state, 90)
        assert recorder.rpms == sorted(recorder.rpms)
        assert len(recorder.rpms) == len(set(recorder.rpms))
        assert recorder.rpms[-1] == tmcc2_speed_to_rpm(90)

    #
    # the RPM map is the engine's own
    #
    def test_scaled_engine_reaches_the_top_notch_at_its_own_ceiling(self):
        scaled = RampEngineState(speed=0, rpm=0, max_speed=SCALED_MAX_SPEED)
        _, scaled_rec = run_ramp(scaled, SCALED_MAX_SPEED)
        assert scaled_rec.rpms[-1] == MAX_RPM
        assert scaled_rec.rpms[-1] == tmcc2_speed_to_rpm(SCALED_MAX_SPEED, SCALED_MAX_SPEED)

        base = RampEngineState(speed=0, rpm=0)
        _, base_rec = run_ramp(base, SCALED_MAX_SPEED)
        assert base_rec.rpms[-1] == tmcc2_speed_to_rpm(SCALED_MAX_SPEED)
        assert base_rec.rpms[-1] < MAX_RPM

    def test_speed_limit_does_not_move_the_notches(self):
        # the ceiling changes, the engine's voice does not
        state = RampEngineState(speed=0, rpm=0, speed_limit=SCALED_MAX_SPEED)
        _, recorder = run_ramp(state, 199)
        assert recorder.speeds[-1] == SCALED_MAX_SPEED
        # every notch the ramp emitted comes from the base table, not a rescaled one
        assert recorder.rpms == expected_rpms(recorder.speeds, 0, initial=state.rpm)
        assert set(recorder.rpms) <= {tmcc2_speed_to_rpm(speed) for speed in recorder.speeds}
        assert recorder.rpms[-1] == tmcc2_speed_to_rpm(SCALED_MAX_SPEED)
        assert recorder.rpms[-1] < MAX_RPM

    def test_bias_on_a_scaled_curve_is_preserved(self):
        bias = 1
        rpm = tmcc2_speed_to_rpm(50, SCALED_MAX_SPEED) + bias
        state = RampEngineState(speed=50, rpm=rpm, max_speed=SCALED_MAX_SPEED)
        ramp, recorder = run_ramp(state, SCALED_MAX_SPEED)
        assert ramp.rpm_bias == bias
        assert recorder.rpms[-1] == biased_rpm(SCALED_MAX_SPEED, bias, SCALED_MAX_SPEED)

    def test_max_speed_changed_mid_ramp_switches_maps_and_rederives_the_bias(self):
        state = RampEngineState(speed=0, rpm=0)
        switched = []

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 5 and not switched:
                switched.append(True)
                state.max_speed = SCALED_MAX_SPEED

        recorder = Recorder(hook)
        ramp = build_ramp(state, SCALED_MAX_SPEED, recorder)
        ramp.run()
        assert ramp.rpm_max_speed == SCALED_MAX_SPEED
        # no abort, and RPM never jumps by more than a notch
        assert recorder.speeds[-1] == SCALED_MAX_SPEED
        deltas = [b - a for a, b in zip(recorder.rpms, recorder.rpms[1:])]
        assert all(abs(d) <= 1 for d in deltas)
        assert recorder.rpms[-1] == biased_rpm(SCALED_MAX_SPEED, ramp.rpm_bias, SCALED_MAX_SPEED)

    #
    # a trim applied at rest reaches every emitted RPM
    #
    def test_a_trim_applied_at_rest_survives_the_whole_ramp(self):
        # the reported scenario: reset the engine, notch RPM up to 2, then open the throttle
        trim = 2
        state = RampEngineState(speed=0, rpm=trim, labor=12)
        ramp, recorder = run_ramp(state, 90)
        assert ramp.rpm_bias == trim
        assert recorder.rpms == expected_rpms(recorder.speeds, trim, initial=trim)
        # the trim is never given back: the stream cannot dip below where the operator set it
        assert min(recorder.rpms) >= trim
        assert recorder.rpms[-1] == biased_rpm(90, trim)
        assert recorder.labors[-1] == 12
        assert state.is_ramping is False

    def test_a_trim_carries_into_the_up_front_deceleration_drop(self):
        trim = 2
        state = RampEngineState(speed=120, rpm=tmcc2_speed_to_rpm(120) + trim, labor=12)
        ramp, recorder = run_ramp(state, 20)
        assert ramp.rpm_bias == trim
        # the single drop at the head of the ramp is the biased notch, not the bare table value
        assert recorder.rpms == [biased_rpm(20, trim)]
        assert recorder.rpms[0] != tmcc2_speed_to_rpm(20)
        assert recorder.speeds[-1] == 20

    def test_no_redundant_opening_rpm(self):
        # the engine already sits at the notch the first step would ask for
        state = RampEngineState(speed=0, rpm=0, labor=12)
        ramp, recorder = run_ramp(state, 60)
        assert ramp.rpm_bias == 0
        assert recorder.rpms[0] != 0
        assert recorder.rpms == expected_rpms(recorder.speeds, 0, initial=0)

    def test_a_trim_at_the_ceiling_pins_every_notch(self):
        state = RampEngineState(speed=0, rpm=MAX_RPM, labor=12)
        ramp, recorder = run_ramp(state, 120)
        assert ramp.rpm_bias == MAX_RPM
        # every biased notch is already the ceiling the engine reports, so nothing is re-sent
        assert all(biased_rpm(speed, MAX_RPM) == MAX_RPM for speed in recorder.speeds)
        assert recorder.rpms == []

    def test_a_trim_at_rest_on_a_scaled_map(self):
        trim = 2
        state = RampEngineState(speed=0, rpm=trim, labor=12, max_speed=SCALED_MAX_SPEED)
        ramp, recorder = run_ramp(state, SCALED_MAX_SPEED)
        assert ramp.rpm_bias == trim
        assert ramp.rpm_max_speed == SCALED_MAX_SPEED
        assert recorder.rpms == expected_rpms(recorder.speeds, trim, SCALED_MAX_SPEED, initial=trim)
        assert recorder.rpms[-1] == MAX_RPM

    def test_a_trim_survives_a_burst_of_retargets(self):
        trim = 2
        state = RampEngineState(speed=0, rpm=trim, labor=12)
        targets = [30, 60, 45, 90]

        def hook(rec: Recorder, _count: int) -> None:
            if targets and len(rec.speeds) % 2 == 0:
                ramp.retarget(targets.pop(0))

        recorder = Recorder(hook)
        ramp = build_ramp(state, 12, recorder)
        ramp.run()
        assert ramp.rpm_bias == trim
        assert min(recorder.rpms) >= trim
        assert recorder.rpms[-1] == biased_rpm(ramp.commanded_speed, trim)

    def test_a_foreign_rpm_overrides_a_trim_derived_at_rest(self):
        from src.pytrain.protocol.command_req import CommandReq

        state = RampEngineState(speed=0, rpm=2, labor=12)
        trimmed: list[int] = []

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 4 and not trimmed:
                foreign = CommandReq.build(TMCC2EngineCommandEnum.DIESEL_RPM, state.tmcc_id, 5, state.scope)
                assert ramp.on_state_command(foreign) is True
                trimmed.append(ramp.rpm_bias)

        recorder = Recorder(hook)
        ramp = build_ramp(state, 90, recorder)
        assert ramp.rpm_bias == 2
        ramp.run()
        # the foreign trim replaced the at rest bias, and the ramp ran on to its target
        assert trimmed and ramp.rpm_bias == trimmed[0] != 2
        assert ramp.abort_reason is None
        assert recorder.speeds[-1] == 90
        assert recorder.rpms[-1] == biased_rpm(90, ramp.rpm_bias)

    #
    # generations and engine capabilities
    #
    def test_tmcc1_ramps_by_one_and_emits_no_rpm_or_effort(self):
        state = RampEngineState(is_legacy=False, is_rpm=False, speed=0)
        ramp, recorder = run_ramp(state, 40)
        assert set(recorder.commands) == {TMCC1EngineCommandEnum.ABSOLUTE_SPEED}
        # clamped to the TMCC1 ceiling, one step at a time
        assert recorder.speeds[-1] == 31
        assert recorder.speeds[:3] == [1, 2, 3]
        assert ramp.rpm_max_speed is None

    def test_tmcc1_max_speed_never_reaches_the_rpm_map(self):
        state = RampEngineState(is_legacy=False, is_rpm=False, speed=0, max_speed=20)
        ramp, recorder = run_ramp(state, 31)
        assert ramp.rpm_max_speed is None
        assert ramp.rpm_bias == 0
        assert recorder.speeds[-1] == 20

    def test_non_rpm_engine_emits_effort_but_no_rpm(self):
        state = RampEngineState(is_rpm=False, speed=0)
        ramp, recorder = run_ramp(state, 60)
        assert recorder.rpms == []
        assert recorder.labors
        assert ramp.rpm_bias == 0

    #
    # linger
    #
    def test_linger_absorbs_a_retarget_into_the_same_thread(self):
        state = RampEngineState(speed=0)
        recorder = Recorder()
        ramp = SpeedRamp(state, 3, sender=recorder, linger=DEFAULT_RAMP_LINGER, delay_scale=0.0)
        settled = []

        def hook(rec: Recorder, _count: int) -> None:
            if rec.speeds == [3] and not settled:
                settled.append(True)
                ramp.retarget(9)

        recorder.hook = hook
        ramp.run()
        assert recorder.speeds[-1] == 9
        assert state.is_ramping is False
