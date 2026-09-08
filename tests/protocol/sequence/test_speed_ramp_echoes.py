from time import time

import pytest

from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from src.pytrain.protocol.sequence import speed_ramp
from src.pytrain.protocol.sequence.speed_ramp import (
    CLAIMED_HISTORY,
    ECHO_TTL,
    MAX_RPM_BIAS,
    SPEED_FAMILIES,
    TMCC1_ECHO_TOLERANCE,
    EchoFamily,
    EchoLedger,
    EchoOutcome,
    PendingEcho,
    echo_family,
)
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum,
    reset_speed_to_rpm_cache,
    tmcc2_speed_to_rpm,
)

from ...test_base import TestBase
from .test_speed_ramp import RampEngineState, Recorder, build_ramp

# the reordered stream CommandDispatcher.run documents: the Base 3 echoes each speed
# almost instantly, and the LCS Ser2 re-echoes it a few seconds later, out of order
SER2_REPLAY = [10, 20, 30, 10, 40, 30, 40]


def req(command, data: int, address: int = 12, scope: CommandScope = CommandScope.ENGINE) -> CommandReq:
    return CommandReq.build(command, address, data, scope)


# noinspection PyMethodMayBeStatic
class TestEchoLedger(TestBase):
    def test_a_recorded_value_is_claimed(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 10)
        assert ledger.pending[EchoFamily.SPEED] == (10,)
        assert ledger.claim(EchoFamily.SPEED, 10) is True
        assert ledger.pending[EchoFamily.SPEED] == ()
        assert ledger.claimed[EchoFamily.SPEED] == (10,)

    def test_an_unrecorded_value_is_not_claimed(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 10)
        assert ledger.claim(EchoFamily.SPEED, 77) is False
        assert ledger.pending[EchoFamily.SPEED] == (10,)

    def test_a_none_value_is_never_recorded_or_claimed(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, None)
        assert ledger.pending[EchoFamily.SPEED] == ()
        assert ledger.claim(EchoFamily.SPEED, None) is False

    def test_skipped_echoes_are_retired_rather_than_forgotten(self):
        ledger = EchoLedger()
        for speed in (10, 20, 30, 40):
            ledger.record(EchoFamily.SPEED, speed)
        assert ledger.claim(EchoFamily.SPEED, 40) is True
        assert ledger.pending[EchoFamily.SPEED] == ()
        # the three the match overtook are still this ramp's own commands, not another
        # controller's, so they move to the claimed history instead of vanishing
        assert ledger.claimed[EchoFamily.SPEED] == (10, 20, 30, 40)

    def test_an_overtaken_step_is_still_ours_when_its_echo_lands(self):
        # the reported defect: 34 was claimed while 32 was still traveling back, which
        # dropped 32 from the ledger, and the ramp then aborted on its own reflection
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 32)
        ledger.record(EchoFamily.SPEED, 34)
        assert ledger.claim(EchoFamily.SPEED, 34) is True
        assert ledger.claim(EchoFamily.SPEED, 32) is True

    def test_a_retired_entry_still_expires_with_the_lag_budget(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 32)
        ledger.record(EchoFamily.SPEED, 34)
        assert ledger.claim(EchoFamily.SPEED, 34) is True
        # being retired is not a fresh lease: past the budget an echo is a deviation,
        # whether it was overtaken or simply never came back
        ledger.purge(ttl=0.0)
        assert ledger.claimed[EchoFamily.SPEED] == ()
        assert ledger.claim(EchoFamily.SPEED, 32) is False

    def test_a_retired_entry_expires_from_behind_a_younger_claim(self, monkeypatch):
        # retiring puts entries in the ring out of timestamp order, so expiry filters the
        # ring rather than popping its head, which a younger entry in front would block
        clock = [100.0]
        monkeypatch.setattr(speed_ramp, "time", lambda: clock[0])
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 10)
        ledger.record(EchoFamily.SPEED, 20)
        clock[0] = 103.0
        assert ledger.claim(EchoFamily.SPEED, 10) is True
        ledger.record(EchoFamily.SPEED, 30)
        clock[0] = 104.0
        # 30's echo overtakes 20's, retiring 20 with the age it was sent at: 100, which
        # is older than the 10 claimed at 103 and already sitting in front of it
        assert ledger.claim(EchoFamily.SPEED, 30) is True
        assert ledger.claimed[EchoFamily.SPEED] == (10, 20, 30)
        clock[0] = 100.0 + ECHO_TTL + 1.5
        ledger.purge()
        assert ledger.claimed[EchoFamily.SPEED] == (10, 30)

    def test_a_target_echo_leaves_the_steps_in_flight_alone(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 34)
        ledger.record(EchoFamily.TARGET, 49)
        assert ledger.claim(EchoFamily.TARGET, 49) is True
        # a TARGET_SPEED is noop, so it is handed back in process and always overtakes a
        # step still on its way to the Base 3; its own queue is what stops it consuming
        # or retiring one
        assert ledger.pending[EchoFamily.SPEED] == (34,)
        assert ledger.claimed[EchoFamily.SPEED] == ()
        assert ledger.claim(EchoFamily.SPEED, 34) is True

    def test_echoes_arriving_in_order_are_claimed_one_at_a_time(self):
        ledger = EchoLedger()
        for speed in (10, 20, 30):
            ledger.record(EchoFamily.SPEED, speed)
        assert ledger.claim(EchoFamily.SPEED, 10) is True
        assert ledger.pending[EchoFamily.SPEED] == (20, 30)
        assert ledger.claim(EchoFamily.SPEED, 20) is True
        assert ledger.pending[EchoFamily.SPEED] == (30,)

    def test_re_echo_of_a_claimed_value_is_accepted_without_consuming(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 30)
        ledger.record(EchoFamily.SPEED, 40)
        assert ledger.claim(EchoFamily.SPEED, 30) is True
        assert ledger.claim(EchoFamily.SPEED, 30) is True
        # the second sighting came out of the claimed ring, so 40 is still pending
        assert ledger.pending[EchoFamily.SPEED] == (40,)

    def test_the_documented_ser2_replay_is_entirely_ours(self):
        ledger = EchoLedger()
        for speed in (10, 20, 30, 40):
            ledger.record(EchoFamily.SPEED, speed)
        for speed in SER2_REPLAY:
            assert ledger.claim(EchoFamily.SPEED, speed) is True, speed

    def test_families_are_independent(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 4)
        ledger.record(EchoFamily.RPM, 4)
        assert ledger.claim(EchoFamily.EFFORT, 4) is False
        assert ledger.claim(EchoFamily.RPM, 4) is True
        assert ledger.pending[EchoFamily.SPEED] == (4,)
        assert ledger.pending[EchoFamily.RPM] == ()

    def test_tolerance_matches_a_value_shifted_by_one(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 20)
        assert ledger.claim(EchoFamily.SPEED, 21) is False
        assert ledger.claim(EchoFamily.SPEED, 21, tolerance=TMCC1_ECHO_TOLERANCE) is True

    def test_tolerance_applies_to_the_claimed_ring_too(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 20)
        assert ledger.claim(EchoFamily.SPEED, 20, tolerance=1) is True
        assert ledger.claim(EchoFamily.SPEED, 19, tolerance=1) is True

    def test_an_echo_arriving_past_the_ttl_is_a_deviation(self):
        ledger = EchoLedger(ttl=0.0)
        ledger.record(EchoFamily.SPEED, 10)
        assert ledger.claim(EchoFamily.SPEED, 10) is False
        assert ledger.pending[EchoFamily.SPEED] == ()

    def test_purge_drops_stale_pending_and_claimed_entries(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 10)
        assert ledger.claim(EchoFamily.SPEED, 10) is True
        ledger.record(EchoFamily.SPEED, 20)
        ledger.purge(ttl=0.0)
        assert ledger.pending[EchoFamily.SPEED] == ()
        assert ledger.claimed[EchoFamily.SPEED] == ()

    def test_an_echo_inside_the_ttl_survives_a_purge(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 10)
        ledger.purge()
        assert ledger.pending[EchoFamily.SPEED] == (10,)
        assert ECHO_TTL >= 5.0

    def test_the_claimed_ring_is_bounded(self):
        ledger = EchoLedger()
        for speed in range(CLAIMED_HISTORY + 10):
            ledger.record(EchoFamily.SPEED, speed)
            assert ledger.claim(EchoFamily.SPEED, speed) is True
        assert len(ledger.claimed[EchoFamily.SPEED]) == CLAIMED_HISTORY

    def test_pending_echo_carries_its_timestamp(self):
        entry = PendingEcho(40, time())
        assert entry.data == 40
        assert entry.sent_at <= time()


# noinspection PyMethodMayBeStatic
class TestEchoFamily(TestBase):
    @pytest.mark.parametrize(
        "command, family",
        [
            (TMCC1EngineCommandEnum.ABSOLUTE_SPEED, EchoFamily.SPEED),
            (TMCC1EngineCommandEnum.TARGET_SPEED, EchoFamily.TARGET),
            (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, EchoFamily.SPEED),
            (TMCC2EngineCommandEnumEx.TARGET_SPEED, EchoFamily.TARGET),
            (TMCC2EngineCommandEnum.DIESEL_RPM, EchoFamily.RPM),
            (TMCC2EngineCommandEnum.ENGINE_LABOR, EchoFamily.EFFORT),
            (TMCC2EngineCommandEnum.ENGINE_LABOR_DEFAULT, EchoFamily.EFFORT),
        ],
    )
    def test_commands_map_to_their_family(self, command, family):
        assert echo_family(command) is family

    def test_an_unarbitrated_command_has_no_family(self):
        assert echo_family(TMCC2EngineCommandEnum.MOMENTUM) is None

    def test_both_speed_carrying_families_are_throttle_commands(self):
        # a deviation in either aborts the ramp; a trim in the other two never does
        assert SPEED_FAMILIES == {EchoFamily.SPEED, EchoFamily.TARGET}


# noinspection PyMethodMayBeStatic
class TestRampArbitration(TestBase):
    def teardown_method(self, test_method):
        reset_speed_to_rpm_cache()
        super().teardown_method(test_method)

    def ramp(self, **kwargs):
        state = RampEngineState(**kwargs)
        recorder = Recorder()
        return state, recorder, build_ramp(state, 40, recorder)

    #
    # the ramp's own reflection
    #
    def test_the_facade_target_speed_echo_is_ours(self):
        _, _, ramp = self.ramp()
        assert ramp.on_state_command(req(TMCC2EngineCommandEnumEx.TARGET_SPEED, 40)) is True

    def test_a_retarget_records_its_own_target(self):
        _, _, ramp = self.ramp()
        ramp.retarget(80)
        assert 80 in ramp.echo_ledger.pending[EchoFamily.TARGET]
        assert ramp.on_state_command(req(TMCC2EngineCommandEnumEx.TARGET_SPEED, 80)) is True

    def test_a_target_echo_does_not_consume_a_pending_step(self):
        _, _, ramp = self.ramp()
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        ramp.retarget(49)
        assert ramp.on_state_command(req(TMCC2EngineCommandEnumEx.TARGET_SPEED, 49)) is True
        assert ramp.echo_ledger.pending[EchoFamily.SPEED] == (34,)
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 34)) is True

    def test_a_retarget_mid_flight_does_not_orphan_the_step_in_flight(self):
        # the reported defect, in the order the log shows it: a step goes out, the slider
        # retargets, the loop wakes and sends the next step, the in process TARGET_SPEED
        # echo lands, and only then does the previous step's echo come back from the
        # Base 3. Every one of those is this ramp's own work.
        state = RampEngineState(speed=0)
        outcomes: list[bool] = []

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 3 and ramp.requested_speed == 120:
                overtaken = rec.speeds[-2]
                ramp.retarget(49)
                outcomes.append(ramp.on_state_command(req(TMCC2EngineCommandEnumEx.TARGET_SPEED, 49)))
                outcomes.append(ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, overtaken)))

        recorder = Recorder(hook)
        ramp = build_ramp(state, 120, recorder)
        ramp.run()
        assert outcomes == [True, True]
        assert ramp.abort_reason is None
        # and the ramp carried on to the target the slider asked for
        assert recorder.speeds[-1] == 49
        assert ramp.commanded_speed == 49

    def test_every_step_the_ramp_sent_is_claimed(self):
        state, recorder, ramp = self.ramp()
        ramp.run()
        for speed in recorder.speeds:
            assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, speed)) is True
        for rpm in recorder.rpms:
            assert ramp.on_state_command(req(TMCC2EngineCommandEnum.DIESEL_RPM, rpm)) is True
        for labor in recorder.labors:
            assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ENGINE_LABOR, labor)) is True
        assert state.is_ramping is False

    def test_a_step_is_recorded_before_it_is_sent(self):
        state = RampEngineState()
        pending: list[tuple] = []
        recorder = Recorder()
        ramp = build_ramp(state, 40, recorder)
        recorder.hook = lambda rec, count: pending.append(ramp.echo_ledger.pending[EchoFamily.SPEED])
        ramp.run()
        # the first send already had its value in the ledger
        assert recorder.speeds[0] in pending[0]

    def test_the_reordered_ser2_stream_never_aborts_a_ramp(self):
        state = RampEngineState(speed=0, momentum=0)
        recorder = Recorder()
        ramp = build_ramp(state, 40, recorder)
        for speed in (10, 20, 30, 40):
            ramp.echo_ledger.record(EchoFamily.SPEED, speed)
        for speed in SER2_REPLAY:
            assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, speed)) is True, speed

    def test_the_commanded_speed_is_always_ours(self):
        state, recorder, ramp = self.ramp()
        ramp.run()
        # the ledger has been drained by hand, so only the commanded fallback is left
        ramp.echo_ledger.purge(ttl=0.0)
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, ramp.commanded_speed)) is True

    def test_an_echo_past_the_ttl_looks_foreign(self):
        state, recorder, ramp = self.ramp()
        ramp.echo_ledger.record(EchoFamily.SPEED, 17)
        ramp.echo_ledger.purge(ttl=0.0)
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 17)) is False

    #
    # TMCC1 tolerance
    #
    def test_tmcc1_claims_an_echo_shifted_by_one(self):
        state = RampEngineState(is_legacy=False, max_speed=31)
        recorder = Recorder()
        ramp = build_ramp(state, 20, recorder)
        assert ramp.speed_echo_tolerance == TMCC1_ECHO_TOLERANCE
        ramp.echo_ledger.record(EchoFamily.SPEED, 14)
        assert ramp.on_state_command(req(TMCC1EngineCommandEnum.ABSOLUTE_SPEED, 15)) is True

    def test_legacy_has_no_speed_tolerance(self):
        _, _, ramp = self.ramp()
        assert ramp.speed_echo_tolerance == 0
        ramp.echo_ledger.record(EchoFamily.SPEED, 14)
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 15)) is False

    #
    # foreign commands
    #
    def test_a_foreign_absolute_speed_is_foreign(self):
        _, _, ramp = self.ramp()
        assert ramp.arbitrate(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 177)) is EchoOutcome.FOREIGN
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 177)) is False

    def test_a_foreign_target_speed_is_foreign(self):
        _, _, ramp = self.ramp()
        assert ramp.on_state_command(req(TMCC2EngineCommandEnumEx.TARGET_SPEED, 177)) is False

    def test_a_foreign_rpm_is_absorbed_not_fatal(self):
        state, recorder, ramp = self.ramp()
        assert ramp.arbitrate(req(TMCC2EngineCommandEnum.DIESEL_RPM, 4)) is EchoOutcome.ABSORB
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.DIESEL_RPM, 4)) is True
        bias = 4 - tmcc2_speed_to_rpm(ramp.commanded_speed, ramp.rpm_max_speed)
        assert ramp.rpm_bias == max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, bias))

    def test_a_foreign_labor_re_baselines_the_effort_restore(self):
        _, _, ramp = self.ramp()
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ENGINE_LABOR, 19)) is True
        assert ramp.init_labor == 19

    def test_an_unarbitrated_command_leaves_the_ramp_alone(self):
        _, _, ramp = self.ramp()
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.MOMENTUM, 6)) is True
