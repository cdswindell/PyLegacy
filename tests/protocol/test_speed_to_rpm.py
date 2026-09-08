import pytest

from src.pytrain.protocol.tmcc2.tmcc2_constants import (
    RPM_CALIBRATION_SPEED,
    RPM_MAP_TOP,
    RPM_SCALE_THRESHOLD,
    TMCC2_SPEED_TO_RPM,
    reset_speed_to_rpm_cache,
    speed_to_rpm_bands,
    speed_to_rpm_map,
    tmcc2_speed_to_rpm,
)

from ..test_base import TestBase

SCALED_MAX_SPEEDS = [8, 15, 31, 50, 75, 100, 120, 150, 194]


# noinspection PyMethodMayBeStatic
class TestSpeedToRpm(TestBase):
    def teardown_method(self, test_method):
        reset_speed_to_rpm_cache()
        super().teardown_method(test_method)

    def test_bands_recovered_from_base_table(self):
        bands = speed_to_rpm_bands()
        assert len(bands) >= 2
        assert bands[0][0] == 0
        # bands are strictly increasing in speed, and their rpm is what the table says
        for i, (lo, rpm) in enumerate(bands):
            assert TMCC2_SPEED_TO_RPM[lo] == rpm
            if i:
                assert lo > bands[i - 1][0]

    @pytest.mark.parametrize("max_speed", [None, 0, 255, RPM_SCALE_THRESHOLD, RPM_CALIBRATION_SPEED, 250])
    def test_identity_at_or_above_threshold(self, max_speed):
        assert speed_to_rpm_map(max_speed) is TMCC2_SPEED_TO_RPM
        for speed in range(0, RPM_MAP_TOP):
            assert tmcc2_speed_to_rpm(speed, max_speed) == TMCC2_SPEED_TO_RPM[speed]

    def test_default_argument_matches_base_table(self):
        for speed in range(0, RPM_MAP_TOP):
            assert tmcc2_speed_to_rpm(speed) == TMCC2_SPEED_TO_RPM[speed]

    @pytest.mark.parametrize("max_speed", SCALED_MAX_SPEEDS)
    def test_scaled_map_is_distinct_and_cached(self, max_speed):
        scaled = speed_to_rpm_map(max_speed)
        assert scaled is not TMCC2_SPEED_TO_RPM
        assert speed_to_rpm_map(max_speed) is scaled

    @pytest.mark.parametrize("max_speed", SCALED_MAX_SPEEDS)
    def test_scaled_bands_strictly_increasing_and_non_empty(self, max_speed):
        scaled = speed_to_rpm_map(max_speed)
        rpms = [scaled[speed] for speed in range(0, RPM_MAP_TOP)]
        # every rpm in the base table appears, in order, exactly once as a band
        base_rpms = [rpm for _, rpm in speed_to_rpm_bands()]
        seen = [rpm for i, rpm in enumerate(rpms) if i == 0 or rpms[i - 1] != rpm]
        assert seen == base_rpms

    @pytest.mark.parametrize("max_speed", SCALED_MAX_SPEEDS)
    def test_rpm_monotonic_in_speed(self, max_speed):
        scaled = speed_to_rpm_map(max_speed)
        prior = scaled[0]
        for speed in range(0, RPM_MAP_TOP):
            rpm = scaled[speed]
            assert rpm >= prior
            prior = rpm

    @pytest.mark.parametrize("max_speed", SCALED_MAX_SPEEDS)
    def test_notch_zero_at_a_stop(self, max_speed):
        assert tmcc2_speed_to_rpm(0, max_speed) == TMCC2_SPEED_TO_RPM[0]

    @pytest.mark.parametrize("max_speed", SCALED_MAX_SPEEDS)
    def test_top_notch_reached_at_max_speed(self, max_speed):
        top_rpm = speed_to_rpm_bands()[-1][1]
        assert tmcc2_speed_to_rpm(max_speed, max_speed) == top_rpm

    def test_scaled_curve_climbs_faster_than_base_curve(self):
        # a slow engine reaches the top notch at its own ceiling, where the base table does not
        top_rpm = speed_to_rpm_bands()[-1][1]
        for max_speed in [50, 75, 100, 120, 150]:
            assert TMCC2_SPEED_TO_RPM[max_speed] < top_rpm
            assert tmcc2_speed_to_rpm(max_speed, max_speed) == top_rpm

    @pytest.mark.parametrize("max_speed", SCALED_MAX_SPEEDS)
    def test_boundaries_within_one_of_proportional_ideal(self, max_speed):
        base_bands = speed_to_rpm_bands()
        scaled = speed_to_rpm_map(max_speed)
        # recover the scaled map's own band lower bounds
        scaled_los = []
        prior = None
        for speed in range(0, RPM_MAP_TOP):
            rpm = scaled[speed]
            if rpm != prior:
                scaled_los.append(speed)
                prior = rpm
        assert len(scaled_los) == len(base_bands)
        scale = max_speed / RPM_CALIBRATION_SPEED
        for i, (base_lo, _) in enumerate(base_bands):
            ideal = round(base_lo * scale)
            assert abs(scaled_los[i] - ideal) <= 1

    @pytest.mark.parametrize("max_speed", SCALED_MAX_SPEEDS + [None, 0, 255, 199])
    def test_full_coverage_no_key_error(self, max_speed):
        for speed in range(0, RPM_MAP_TOP):
            assert isinstance(tmcc2_speed_to_rpm(speed, max_speed), int)

    @pytest.mark.parametrize("max_speed", SCALED_MAX_SPEEDS)
    def test_speed_above_ceiling_resolves_to_top_notch(self, max_speed):
        top_rpm = speed_to_rpm_bands()[-1][1]
        assert tmcc2_speed_to_rpm(RPM_MAP_TOP - 1, max_speed) == top_rpm

    def test_absurdly_low_ceiling_still_well_formed(self):
        band_count = len(speed_to_rpm_bands())
        for max_speed in range(1, band_count + 2):
            scaled = speed_to_rpm_map(max_speed)
            rpms = [scaled[speed] for speed in range(0, RPM_MAP_TOP)]
            assert sorted(rpms) == rpms
            assert len(set(rpms)) == band_count

    def test_reset_cache_rebuilds_map(self):
        before = speed_to_rpm_map(100)
        reset_speed_to_rpm_cache()
        after = speed_to_rpm_map(100)
        assert after is not before
        for speed in range(0, RPM_MAP_TOP):
            assert after[speed] == before[speed]

    def test_edited_base_table_reshapes_every_scaled_map(self, monkeypatch):
        from range_key_dict import RangeKeyDict

        from src.pytrain.protocol.tmcc2 import tmcc2_constants

        # a two band table: rpm 0 below 100, rpm 7 at and above it
        edited = RangeKeyDict({(0, 100): 0, (100, RPM_MAP_TOP): 7})
        monkeypatch.setattr(tmcc2_constants, "TMCC2_SPEED_TO_RPM", edited)
        reset_speed_to_rpm_cache()
        assert tmcc2_constants.speed_to_rpm_bands() == ((0, 0), (100, 7))
        # the base curve
        assert tmcc2_constants.tmcc2_speed_to_rpm(99) == 0
        assert tmcc2_constants.tmcc2_speed_to_rpm(100) == 7
        # and every scaled curve
        for max_speed in SCALED_MAX_SPEEDS:
            scale = max_speed / RPM_CALIBRATION_SPEED
            boundary = round(100 * scale)
            assert tmcc2_constants.tmcc2_speed_to_rpm(boundary - 1, max_speed) == 0
            assert tmcc2_constants.tmcc2_speed_to_rpm(boundary, max_speed) == 7
