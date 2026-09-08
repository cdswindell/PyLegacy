import pytest

from src.pytrain.protocol.sequence.ramped_speed_req import labor_delta as req_labor_delta
from src.pytrain.protocol.sequence.speed_ramp import (
    BASE_STEP_DELAY,
    LEGACY_SPEED_MAX,
    MAX_RPM,
    MAX_RPM_BIAS,
    TMCC1_SPEED_MAX,
    UNSET_MAX_SPEED,
    RampStep,
    biased_rpm,
    effective_target,
    labor_delta,
    next_step,
    ramp_delay,
    ramp_increment,
    rpm_bias_for,
    rpm_max_speed,
    speed_ceiling,
)
from src.pytrain.protocol.tmcc2.tmcc2_constants import (
    RPM_MAP_TOP,
    TMCC2_SPEED_TO_RPM,
    reset_speed_to_rpm_cache,
    speed_to_rpm_bands,
    speed_to_rpm_map,
    tmcc2_speed_to_rpm,
)

from ...test_base import TestBase

SCALED_MAX_SPEED = 100


def map_boundaries(max_speed: int = None) -> list[int]:
    """Recover a map's own band lower bounds, so no boundary is ever hard-coded."""
    boundaries = []
    prior = None
    for speed in range(0, RPM_MAP_TOP):
        rpm = tmcc2_speed_to_rpm(speed, max_speed)
        if rpm != prior:
            boundaries.append(speed)
            prior = rpm
    return boundaries


def band_probes(max_speed: int = None) -> list[int]:
    """A speed just below, at, and just above each of a map's band boundaries."""
    probes = set()
    for lo in map_boundaries(max_speed):
        for speed in (lo - 1, lo, lo + 1):
            if 0 <= speed < RPM_MAP_TOP:
                probes.add(speed)
    return sorted(probes)


class FakeEngineState:
    """
    A stand-in for EngineState exposing only what the ramp geometry reads. `speed_max`
    mirrors EngineState.speed_max so the ceiling matrix is exercised against the real
    max_speed / speed_limit resolution rather than a hand-picked number.
    """

    def __init__(
        self,
        *,
        is_legacy: bool = True,
        is_rpm: bool = True,
        speed: int = 0,
        rpm: int = 0,
        labor: int = 12,
        momentum: int = 0,
        max_speed: int = UNSET_MAX_SPEED,
        speed_limit: int = UNSET_MAX_SPEED,
        speed_max: int = None,
    ) -> None:
        self.is_legacy = is_legacy
        self.is_rpm = is_rpm
        self.speed = speed
        self.rpm = rpm
        self.labor = labor
        self.momentum = momentum
        self.max_speed = max_speed
        self.speed_limit = speed_limit
        self._speed_max = speed_max

    @property
    def speed_max(self) -> int | None:
        if self._speed_max is not None:
            return self._speed_max
        max_speed, speed_limit = self.max_speed, self.speed_limit
        if max_speed and max_speed != 255 and speed_limit and speed_limit != 255:
            ms = min(max_speed, speed_limit)
        elif speed_limit and speed_limit != 255:
            ms = speed_limit
        elif max_speed and max_speed != 255:
            ms = max_speed
        else:
            ms = LEGACY_SPEED_MAX if self.is_legacy is True else TMCC1_SPEED_MAX
        if self.is_legacy is False and ms > TMCC1_SPEED_MAX:
            ms = TMCC1_SPEED_MAX
        return ms


class NoCeilingEngineState(FakeEngineState):
    """An engine whose comp_data has not arrived, so speed_max is None."""

    @property
    def speed_max(self) -> int | None:
        return None


def legacy(**kwargs) -> FakeEngineState:
    return FakeEngineState(is_legacy=True, **kwargs)


def tmcc1(**kwargs) -> FakeEngineState:
    kwargs.setdefault("is_rpm", False)
    return FakeEngineState(is_legacy=False, **kwargs)


# noinspection PyMethodMayBeStatic
class TestSpeedRampGeometry(TestBase):
    def teardown_method(self, test_method):
        reset_speed_to_rpm_cache()
        super().teardown_method(test_method)

    #
    # labor_delta is shared, not duplicated
    #
    def test_labor_delta_is_the_shared_curve(self):
        assert labor_delta is req_labor_delta

    #
    # increment
    #
    @pytest.mark.parametrize(
        "momentum, expected",
        [(0, 3), (1, 3), (2, 3), (3, 3), (4, 2), (5, 2), (6, 1), (7, 1)],
    )
    def test_legacy_increment_by_momentum_band(self, momentum, expected):
        assert ramp_increment(legacy(momentum=momentum), True) == expected

    @pytest.mark.parametrize("momentum", [None, 0, 3, 4, 6, 7])
    def test_tmcc1_increment_is_always_one(self, momentum):
        assert ramp_increment(tmcc1(momentum=momentum), False) == 1

    def test_legacy_increment_with_no_momentum(self):
        assert ramp_increment(legacy(momentum=None), True) == 3

    #
    # step delay
    #
    @pytest.mark.parametrize("momentum", [0, 1, 2, 3, 4, 5, 6, 7])
    def test_legacy_delay_by_momentum(self, momentum):
        assert ramp_delay(legacy(momentum=momentum), True) == pytest.approx(BASE_STEP_DELAY + momentum * 0.010)

    @pytest.mark.parametrize("momentum", [0, 1, 2, 3, 4, 5, 6, 7])
    def test_tmcc1_delay_by_momentum(self, momentum):
        assert ramp_delay(tmcc1(momentum=momentum), False) == pytest.approx(BASE_STEP_DELAY + momentum * 0.1)

    @pytest.mark.parametrize("is_legacy", [True, False])
    def test_delay_falls_back_when_momentum_unknown(self, is_legacy):
        state = FakeEngineState(is_legacy=is_legacy, momentum=None)
        assert ramp_delay(state, is_legacy) == pytest.approx(BASE_STEP_DELAY)

    def test_delay_is_monotonic_in_momentum(self):
        delays = [ramp_delay(legacy(momentum=m), True) for m in range(0, 8)]
        assert delays == sorted(delays)
        assert delays[0] < delays[-1]

    #
    # the live ceiling
    #
    def test_ceiling_neither_limit_legacy(self):
        assert speed_ceiling(legacy()) == LEGACY_SPEED_MAX

    def test_ceiling_neither_limit_tmcc1(self):
        assert speed_ceiling(tmcc1()) == TMCC1_SPEED_MAX

    def test_ceiling_speed_limit_only(self):
        assert speed_ceiling(legacy(speed_limit=40)) == 40

    def test_ceiling_max_speed_only(self):
        assert speed_ceiling(legacy(max_speed=100)) == 100

    def test_ceiling_both_limits_takes_the_lower(self):
        assert speed_ceiling(legacy(max_speed=100, speed_limit=40)) == 40
        assert speed_ceiling(legacy(max_speed=40, speed_limit=100)) == 40

    @pytest.mark.parametrize("is_legacy, expected", [(True, LEGACY_SPEED_MAX), (False, TMCC1_SPEED_MAX)])
    def test_ceiling_speed_max_none_falls_back_by_generation(self, is_legacy, expected):
        # a missing comp_data makes speed_max None; the ramp treats that as no ceiling
        state = NoCeilingEngineState(is_legacy=is_legacy)
        assert state.speed_max is None
        assert speed_ceiling(state) == expected
        assert effective_target(199, state) == expected

    @pytest.mark.parametrize("is_legacy, expected", [(True, LEGACY_SPEED_MAX), (False, TMCC1_SPEED_MAX)])
    def test_ceiling_unset_speed_max_falls_back_by_generation(self, is_legacy, expected):
        state = FakeEngineState(is_legacy=is_legacy, speed_max=UNSET_MAX_SPEED)
        assert speed_ceiling(state) == expected

    def test_effective_target_clamps_to_the_live_ceiling(self):
        state = legacy(speed_limit=40)
        assert effective_target(120, state) == 40
        # the requested target is not rewritten: raise the limit and the ramp resumes
        state.speed_limit = 180
        assert effective_target(120, state) == 120
        # and clearing it entirely
        state.speed_limit = UNSET_MAX_SPEED
        assert effective_target(120, state) == 120

    def test_effective_target_below_the_ceiling_is_untouched(self):
        assert effective_target(60, legacy(max_speed=100)) == 60

    def test_effective_target_never_negative(self):
        assert effective_target(-5, legacy()) == 0

    def test_effective_target_none_requested(self):
        assert effective_target(None, legacy()) is None

    def test_tmcc1_effective_target_capped_at_31(self):
        assert effective_target(199, tmcc1()) == TMCC1_SPEED_MAX

    #
    # rpm_max_speed: the generation guard
    #
    def test_rpm_max_speed_is_none_for_tmcc1(self):
        # a TMCC1 max_speed is on the 0-31 scale and must never reach the RPM map
        assert rpm_max_speed(tmcc1(max_speed=31)) is None
        assert rpm_max_speed(tmcc1(max_speed=16)) is None

    def test_rpm_max_speed_is_the_roster_ceiling_for_legacy(self):
        assert rpm_max_speed(legacy(max_speed=SCALED_MAX_SPEED)) == SCALED_MAX_SPEED

    @pytest.mark.parametrize("max_speed", [None, 0, UNSET_MAX_SPEED])
    def test_rpm_max_speed_unknown_uses_base_table(self, max_speed):
        assert rpm_max_speed(legacy(max_speed=max_speed)) is None

    def test_rpm_max_speed_ignores_speed_limit(self):
        # a speed limit changes where the ramp stops, not where the notches fall
        state = legacy(max_speed=UNSET_MAX_SPEED, speed_limit=SCALED_MAX_SPEED)
        assert rpm_max_speed(state) is None
        assert speed_ceiling(state) == SCALED_MAX_SPEED

    #
    # biased_rpm: always through tmcc2_constants
    #
    @pytest.mark.parametrize("speed", band_probes())
    def test_biased_rpm_zero_bias_is_the_base_table(self, speed):
        assert biased_rpm(speed, 0) == TMCC2_SPEED_TO_RPM[speed]

    @pytest.mark.parametrize("speed", band_probes())
    @pytest.mark.parametrize("bias", [-MAX_RPM_BIAS, -1, 0, 1, MAX_RPM_BIAS])
    def test_biased_rpm_is_table_plus_bias_clamped(self, speed, bias):
        expected = max(0, min(MAX_RPM, TMCC2_SPEED_TO_RPM[speed] + bias))
        assert biased_rpm(speed, bias) == expected

    @pytest.mark.parametrize("speed", band_probes(SCALED_MAX_SPEED))
    @pytest.mark.parametrize("bias", [-1, 0, 1])
    def test_biased_rpm_on_a_scaled_map(self, speed, bias):
        scaled = speed_to_rpm_map(SCALED_MAX_SPEED)
        expected = max(0, min(MAX_RPM, scaled[speed] + bias))
        assert biased_rpm(speed, bias, SCALED_MAX_SPEED) == expected

    def test_biased_rpm_clamped_to_the_notch_range(self):
        top_speed = map_boundaries()[-1]
        assert biased_rpm(top_speed, MAX_RPM_BIAS) == MAX_RPM
        assert biased_rpm(0, -MAX_RPM_BIAS) == 0

    def test_scaled_map_reaches_the_top_notch_where_the_base_does_not(self):
        top_rpm = speed_to_rpm_bands()[-1][1]
        assert biased_rpm(SCALED_MAX_SPEED, 0, SCALED_MAX_SPEED) == top_rpm
        assert biased_rpm(SCALED_MAX_SPEED, 0, None) < top_rpm

    #
    # rpm_bias_for
    #
    def test_bias_zero_for_non_rpm_engine(self):
        assert rpm_bias_for(legacy(is_rpm=False, speed=30, rpm=3)) == 0

    def test_bias_zero_when_speed_unknown(self):
        # comp_data has not arrived: there is no baseline to compare against
        assert rpm_bias_for(legacy(speed=None, rpm=3)) == 0

    @pytest.mark.parametrize("rpm", list(range(MAX_RPM + 1)))
    def test_bias_at_rest_is_the_reported_rpm(self, rpm):
        # at a standstill there is no curve value to subtract: the trim is the bias
        expected = max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, rpm))
        assert rpm_bias_for(legacy(speed=0, rpm=rpm)) == expected

    def test_bias_zero_at_rest_when_rpm_unknown(self):
        assert rpm_bias_for(legacy(speed=0, rpm=None)) == 0

    @pytest.mark.parametrize("rpm", list(range(MAX_RPM + 1)))
    def test_bias_at_rest_on_a_scaled_map(self, rpm):
        # the standstill rule does not consult the map, and the two agree at rest
        state = legacy(speed=0, rpm=rpm, max_speed=SCALED_MAX_SPEED)
        expected = max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, rpm))
        assert rpm_bias_for(state) == expected
        assert tmcc2_speed_to_rpm(0, SCALED_MAX_SPEED) == 0

    def test_bias_matches_the_documented_example(self):
        # an engine at speed 30 reporting rpm 3 where the table says 2 carries +1
        assert TMCC2_SPEED_TO_RPM[30] == 2
        assert rpm_bias_for(legacy(speed=30, rpm=3)) == 1

    @pytest.mark.parametrize("speed", [s for s in band_probes() if s > 0])
    @pytest.mark.parametrize("offset", [-3, -2, -1, 0, 1, 2, 3])
    def test_bias_derived_from_the_base_table_and_clamped(self, speed, offset):
        table_rpm = tmcc2_speed_to_rpm(speed)
        rpm = max(0, min(MAX_RPM, table_rpm + offset))
        expected = max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, rpm - table_rpm))
        assert rpm_bias_for(legacy(speed=speed, rpm=rpm)) == expected

    @pytest.mark.parametrize("speed", [s for s in band_probes(SCALED_MAX_SPEED) if 0 < s <= SCALED_MAX_SPEED])
    @pytest.mark.parametrize("offset", [-1, 0, 1])
    def test_bias_derived_from_the_engines_own_scaled_map(self, speed, offset):
        state = legacy(speed=speed, max_speed=SCALED_MAX_SPEED)
        table_rpm = tmcc2_speed_to_rpm(speed, SCALED_MAX_SPEED)
        state.rpm = max(0, min(MAX_RPM, table_rpm + offset))
        expected = max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, state.rpm - table_rpm))
        assert rpm_bias_for(state) == expected

    def test_bias_and_emission_use_the_same_map(self):
        # a scaled engine whose reported rpm matches its own curve carries no bias
        speed = 50
        state = legacy(speed=speed, max_speed=SCALED_MAX_SPEED)
        state.rpm = tmcc2_speed_to_rpm(speed, SCALED_MAX_SPEED)
        assert rpm_bias_for(state) == 0
        assert biased_rpm(speed, rpm_bias_for(state), rpm_max_speed(state)) == state.rpm

    def test_bias_held_to_the_notch_range(self):
        # the only clamp left is the notch range itself
        assert MAX_RPM_BIAS == MAX_RPM
        state = legacy(speed=map_boundaries()[-1], rpm=0)
        assert rpm_bias_for(state) == -tmcc2_speed_to_rpm(map_boundaries()[-1])
        state = legacy(speed=0, rpm=MAX_RPM)
        assert rpm_bias_for(state) == MAX_RPM

    def test_a_deliberate_trim_is_not_reduced(self):
        # a stopped engine trimmed to rpm 4 keeps all four notches, not the old two
        assert rpm_bias_for(legacy(speed=0, rpm=4)) == 4

    def test_negative_extreme_floors_the_emitted_rpm(self):
        # an engine at speed 120 reporting rpm 0 now carries the full negative bias
        state = legacy(speed=120, rpm=0)
        bias = rpm_bias_for(state)
        assert bias == -tmcc2_speed_to_rpm(120)
        assert bias < 0
        for speed in band_probes():
            assert biased_rpm(speed, bias) >= 0

    def test_bias_zero_for_tmcc1(self):
        assert rpm_bias_for(tmcc1(speed=20, rpm=3)) == 0

    #
    # next_step
    #
    def test_next_step_none_at_the_target(self):
        assert next_step(60, 60, legacy(), 12, 0) is None

    def test_next_step_none_when_the_ceiling_already_holds_us(self):
        assert next_step(40, 120, legacy(speed_limit=40), 12, 0) is None

    def test_next_step_accelerates_by_the_increment(self):
        state = legacy(momentum=0)
        step = next_step(0, 60, state, 12, 0)
        assert isinstance(step, RampStep)
        assert step.speed == ramp_increment(state, True)
        assert step.delay == pytest.approx(ramp_delay(state, True))

    def test_next_step_does_not_overshoot_the_target(self):
        assert next_step(59, 60, legacy(momentum=0), 12, 0).speed == 60

    def test_next_step_decelerates(self):
        state = legacy(momentum=0)
        step = next_step(60, 0, state, 12, 0)
        assert step.speed == 60 - ramp_increment(state, True)

    def test_next_step_does_not_undershoot_the_target(self):
        assert next_step(1, 0, legacy(momentum=0), 12, 0).speed == 0

    def test_next_step_reads_momentum_live(self):
        state = legacy(momentum=0)
        assert next_step(0, 120, state, 12, 0).speed == 3
        state.momentum = 4
        assert next_step(0, 120, state, 12, 0).speed == 2
        state.momentum = 6
        step = next_step(0, 120, state, 12, 0)
        assert step.speed == 1
        assert step.delay == pytest.approx(ramp_delay(state, True))

    def test_next_step_clamps_to_the_live_ceiling(self):
        state = legacy(momentum=0, speed_limit=40)
        assert next_step(39, 120, state, 12, 0).speed == 40

    def test_a_ceiling_below_the_commanded_speed_reverses_the_ramp(self):
        state = legacy(momentum=0, speed_limit=20)
        step = next_step(80, 120, state, 12, 0)
        assert step.speed == 80 - ramp_increment(state, True)
        assert step.speed > 20

    def test_next_step_labor_follows_the_shared_curve(self):
        state = legacy(momentum=0)
        step = next_step(0, 60, state, 12, 0)
        assert step.labor == labor_delta(step.speed, 60, 12)

    def test_next_step_rpm_follows_the_table_plus_bias(self):
        state = legacy(momentum=0)
        step = next_step(0, 120, state, 12, 1)
        assert step.rpm == biased_rpm(step.speed, 1, None)

    def test_next_step_rpm_follows_the_engines_own_scaled_map(self):
        state = legacy(momentum=0, max_speed=SCALED_MAX_SPEED)
        commanded = SCALED_MAX_SPEED - 3
        step = next_step(commanded, SCALED_MAX_SPEED, state, 12, 0)
        assert step.rpm == biased_rpm(step.speed, 0, SCALED_MAX_SPEED)
        assert step.rpm == speed_to_rpm_bands()[-1][1]

    def test_a_speed_limit_does_not_move_the_notches(self):
        # max_speed unset, limit of 100: the ceiling changed, the voice did not
        state = legacy(momentum=0, speed_limit=SCALED_MAX_SPEED)
        step = next_step(SCALED_MAX_SPEED - 3, 199, state, 12, 0)
        assert step.speed == SCALED_MAX_SPEED
        assert step.rpm == TMCC2_SPEED_TO_RPM[step.speed]

    def test_next_step_rpm_none_on_deceleration(self):
        # rpm is dropped once, up front, not step by step
        assert next_step(120, 0, legacy(momentum=0), 12, 0).rpm is None

    def test_next_step_rpm_none_for_non_rpm_engine(self):
        step = next_step(0, 60, legacy(is_rpm=False, momentum=0), 12, 0)
        assert step.rpm is None
        assert step.labor is not None

    def test_next_step_tmcc1_emits_neither_rpm_nor_labor(self):
        state = tmcc1(momentum=0)
        step = next_step(0, 20, state, 12, 0)
        assert step.speed == 1
        assert step.rpm is None
        assert step.labor is None

    def test_tmcc1_ramp_stays_within_its_own_range(self):
        state = tmcc1(momentum=0)
        commanded = 0
        while True:
            step = next_step(commanded, 199, state, 12, 0)
            if step is None:
                break
            assert 0 <= step.speed <= TMCC1_SPEED_MAX
            commanded = step.speed
        assert commanded == TMCC1_SPEED_MAX

    @pytest.mark.parametrize("momentum", [0, 4, 6])
    def test_legacy_ramp_is_strictly_monotonic_and_lands_on_target(self, momentum):
        state = legacy(momentum=momentum)
        commanded, speeds = 0, []
        while True:
            step = next_step(commanded, 60, state, 12, 0)
            if step is None:
                break
            assert step.speed > commanded
            speeds.append(step.speed)
            commanded = step.speed
        assert speeds[-1] == 60
        assert speeds == sorted(set(speeds))
