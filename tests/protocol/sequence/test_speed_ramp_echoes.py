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

    def test_a_step_echo_out_of_sequence_is_not_ours(self):
        # Missing reports can be skipped, but a later report cannot go backward.
        ledger = EchoLedger()
        for speed in (10, 20, 30, 40):
            ledger.record(EchoFamily.SPEED, speed)
        assert ledger.claim(EchoFamily.SPEED, 40) is True
        assert ledger.claim(EchoFamily.SPEED, 30) is False
        assert ledger.pending[EchoFamily.SPEED] == ()
        assert ledger.claimed[EchoFamily.SPEED] == (40,)

    def test_step_echoes_are_claimed_strictly_in_send_order(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 32)
        ledger.record(EchoFamily.SPEED, 34)
        assert ledger.claim(EchoFamily.SPEED, 34) is True
        assert ledger.claim(EchoFamily.SPEED, 32) is False
        assert ledger.claim(EchoFamily.SPEED, 34) is True

    @pytest.mark.parametrize("speeds", [(10, 20, 30, 40, 50), (50, 40, 30, 20, 10)])
    def test_delayed_speed_reports_can_skip_steps_but_not_go_backward(self, monkeypatch, speeds):
        clock = [100.0]
        monkeypatch.setattr(speed_ramp, "time", lambda: clock[0])
        ledger = EchoLedger()
        for speed in speeds:
            ledger.record(EchoFamily.SPEED, speed)
            clock[0] += ECHO_TTL / 20
        clock[0] = 100.0 + ECHO_TTL * 0.8
        assert ledger.claim(EchoFamily.SPEED, speeds[1]) is True
        assert ledger.claim(EchoFamily.SPEED, speeds[1]) is True
        assert ledger.claim(EchoFamily.SPEED, speeds[3]) is True
        assert ledger.pending[EchoFamily.SPEED] == (speeds[4],)
        assert ledger.claim(EchoFamily.SPEED, speeds[2]) is False
        assert ledger.claim(EchoFamily.SPEED, speeds[3] + 1) is False
        assert ledger.claim(EchoFamily.SPEED, speeds[4]) is True
        clock[0] += ECHO_TTL
        assert ledger.claim(EchoFamily.SPEED, speeds[4]) is False

    def test_speed_reports_follow_send_order_across_a_reversal(self):
        ledger = EchoLedger()
        for speed in (10, 20, 30, 20, 10):
            ledger.record(EchoFamily.SPEED, speed)
        for speed in (20, 30, 20, 10):
            assert ledger.claim(EchoFamily.SPEED, speed) is True
        assert ledger.claim(EchoFamily.SPEED, 20) is False

    @pytest.mark.parametrize("family", [EchoFamily.RPM, EchoFamily.EFFORT])
    def test_sound_and_effort_still_require_the_next_pending_echo(self, family):
        ledger = EchoLedger()
        ledger.record(family, 3)
        ledger.record(family, 4)
        assert ledger.claim(family, 4) is False
        assert ledger.pending[family] == (3, 4)

    def test_only_the_value_just_matched_is_still_claimable(self):
        # the Lionel ecosystem sends a command two or three times; a repeat is not out of
        # sequence, because nothing newer has been seen since. A value from further back
        # is: this is the band a foreign speed used to hide in
        ledger = EchoLedger()
        for speed in (10, 20, 30):
            ledger.record(EchoFamily.SPEED, speed)
        for speed in (10, 20, 30):
            assert ledger.claim(EchoFamily.SPEED, speed) is True
        assert ledger.claim(EchoFamily.SPEED, 30) is True
        assert ledger.claim(EchoFamily.SPEED, 10) is False
        assert ledger.claim(EchoFamily.SPEED, 20) is False

    def test_the_value_just_matched_expires_with_the_lag_budget(self):
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 32)
        assert ledger.claim(EchoFamily.SPEED, 32) is True
        assert ledger.claim(EchoFamily.SPEED, 32) is True
        # a match is not a fresh lease: past the budget the value is a deviation again
        ledger.purge(ttl=0.0)
        assert ledger.claimed[EchoFamily.SPEED] == ()
        assert ledger.claim(EchoFamily.SPEED, 32) is False

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

    def test_the_documented_ser2_replay_cannot_reach_a_ledger(self):
        # this stream only exists on a layout listening to both a Base 3 and a Ser2, and
        # there ComponentStateStore drops ABSOLUTE_SPEED outright - it is declared
        # filtered - so a ramp never sees it. Tolerating it here would mean tolerating
        # any speed the ramp had swept through, which is where a foreign one hid
        ledger = EchoLedger()
        for speed in (10, 20, 30, 40):
            ledger.record(EchoFamily.SPEED, speed)
        claimed = [ledger.claim(EchoFamily.SPEED, speed) for speed in SER2_REPLAY]
        # 10, 20 and 30 are the echoes it was waiting for; the second 10 is not, and
        # neither is the second 30, once 40 has been seen
        assert claimed == [True, True, True, False, True, False, True]

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

    def test_an_echo_inside_the_ttl_survives_a_purge(self, monkeypatch):
        clock = [0.0]
        monkeypatch.setattr(speed_ramp, "time", lambda: clock[0])
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 10)
        clock[0] = ECHO_TTL * 0.99
        ledger.purge()
        assert ledger.pending[EchoFamily.SPEED] == (10,)
        assert ledger.claim(EchoFamily.SPEED, 10) is True

    @pytest.mark.parametrize("claimed", [False, True])
    @pytest.mark.parametrize("age", [1.0, 1.01])
    def test_echoes_expire_at_the_configured_ttl(self, monkeypatch, claimed, age):
        clock = [0.0]
        monkeypatch.setattr(speed_ramp, "time", lambda: clock[0])
        ledger = EchoLedger()
        ledger.record(EchoFamily.SPEED, 10)
        if claimed:
            clock[0] = ECHO_TTL * 0.5
            assert ledger.claim(EchoFamily.SPEED, 10) is True
        clock[0] = ECHO_TTL * age
        assert ledger.claim(EchoFamily.SPEED, 10) is False
        assert ledger.pending[EchoFamily.SPEED] == ()
        assert ledger.claimed[EchoFamily.SPEED] == ()

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
            (TMCC1EngineCommandEnum.TARGET_SPEED, None),
            (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, EchoFamily.SPEED),
            (TMCC2EngineCommandEnumEx.TARGET_SPEED, None),
            (TMCC2EngineCommandEnum.DIESEL_RPM, EchoFamily.RPM),
            (TMCC2EngineCommandEnum.ENGINE_LABOR, EchoFamily.EFFORT),
            (TMCC2EngineCommandEnum.ENGINE_LABOR_DEFAULT, EchoFamily.EFFORT),
        ],
    )
    def test_commands_map_to_their_family(self, command, family):
        assert echo_family(command) is family

    def test_an_unarbitrated_command_has_no_family(self):
        assert echo_family(TMCC2EngineCommandEnum.MOMENTUM) is None


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
    @pytest.mark.parametrize("leading_rx", [False, True])
    @pytest.mark.parametrize(
        "command,values",
        [
            (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, (12, 15, 18)),
            (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, (30, 27, 24)),
            (TMCC2EngineCommandEnum.ABSOLUTE_SPEED, (12, 15, 12)),
            (TMCC1EngineCommandEnum.ABSOLUTE_SPEED, (12, 15, 18)),
            (TMCC2EngineCommandEnum.DIESEL_RPM, (1, 2, 3)),
            (TMCC2EngineCommandEnum.ENGINE_LABOR, (15, 14, 13)),
        ],
    )
    def test_feedback_streams_advance_independently(self, monkeypatch, leading_rx, command, values):
        clock = [100.0]
        monkeypatch.setattr(speed_ramp, "time", lambda: clock[0])
        _, _, ramp = self.ramp()

        def receive(value, is_rx):
            request = CommandReq.from_bytes(req(command, value).as_bytes, from_tmcc_rx=is_rx)
            assert ramp.arbitrate(request) is EchoOutcome.MINE

        ramp._send(command, values[0])
        receive(values[0], leading_rx)
        receive(values[0], not leading_rx)
        for value in values[1:]:
            clock[0] += ECHO_TTL / 8
            ramp._send(command, value)
            receive(value, leading_rx)
        for value in values[1:]:
            receive(value, not leading_rx)
        receive(values[-1], leading_rx)
        receive(values[-1], not leading_rx)

    @pytest.mark.parametrize("is_rx", [False, True])
    @pytest.mark.parametrize("foreign", ["backward", "unsent", "expired"])
    def test_each_feedback_stream_still_rejects_foreign_speeds(self, monkeypatch, is_rx, foreign):
        clock = [100.0]
        monkeypatch.setattr(speed_ramp, "time", lambda: clock[0])
        _, _, ramp = self.ramp()
        command = TMCC2EngineCommandEnum.ABSOLUTE_SPEED
        for value in (12, 15, 18):
            ramp._send(command, value)
            request = CommandReq.from_bytes(req(command, value).as_bytes, from_tmcc_rx=is_rx)
            assert ramp.arbitrate(request) is EchoOutcome.MINE

        # The other stream still has all three sends pending; it cannot rescue a failed claim.
        value = 15 if foreign == "backward" else 17
        if foreign == "expired":
            clock[0] += ECHO_TTL
            value = 18
        request = CommandReq.from_bytes(req(command, value).as_bytes, from_tmcc_rx=is_rx)
        assert ramp.arbitrate(request) is EchoOutcome.FOREIGN
        assert ramp.on_state_command(request) is False

    def test_local_retargets_neither_send_commands_nor_change_echo_history(self):
        _, recorder, ramp = self.ramp()
        ramp.echo_ledger.record(EchoFamily.SPEED, 34)
        pending = ramp.echo_ledger.pending
        for target in (22, 37, 52, 67, 70):
            ramp.retarget(target)
            assert ramp.requested_speed == target
            assert ramp.echo_ledger.pending == pending
        assert recorder.speeds == recorder.rpms == recorder.labors == []
        assert ramp.echo_ledger.pending[EchoFamily.SPEED] == (34,)
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 34)) is True

    def test_a_retarget_mid_flight_does_not_orphan_the_step_in_flight(self):
        # The slider retargets while earlier speed steps are still on their way back.
        state = RampEngineState(speed=0)
        outcomes: list[bool] = []

        def hook(rec: Recorder, _count: int) -> None:
            if len(rec.speeds) == 3 and ramp.requested_speed == 120:
                first, overtaken = rec.speeds[0], rec.speeds[1]
                outcomes.append(ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, first)))
                ramp.retarget(49)
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

    def test_an_accounted_for_step_leaves_the_queue(self):
        # the ledger is consulted before the commanded speed for exactly this reason: an
        # echo consumes its entry, so the queue drains instead of accumulating every
        # speed the ramp has swept through - the band a foreign speed used to hide in
        _, recorder, ramp = self.ramp()
        ramp.run()
        for speed in recorder.speeds:
            assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, speed)) is True
        assert ramp.echo_ledger.pending[EchoFamily.SPEED] == ()

    def test_a_speed_the_ramp_swept_through_earlier_is_foreign(self):
        # the reported takeover: this ramp commanded 30 on its way up and was sitting at
        # 44 when another controller sent ABSOLUTE_SPEED 30. Every step's echo had been
        # accounted for by then, so a second sighting of 30 is out of sequence
        state = RampEngineState(speed=0, momentum=0)
        recorder = Recorder()
        ramp = build_ramp(state, 126, recorder)
        for speed in range(2, 46, 2):
            ramp.echo_ledger.record(EchoFamily.SPEED, speed)
            ramp._commanded_speed = speed
            assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, speed)) is True
        assert ramp.arbitrate(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 30)) is EchoOutcome.FOREIGN
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 30)) is False

    def test_a_step_is_recorded_before_it_is_sent(self):
        state = RampEngineState()
        pending: list[tuple] = []
        recorder = Recorder()
        ramp = build_ramp(state, 40, recorder)
        recorder.hook = lambda rec, count: pending.append(ramp.echo_ledger.pending[EchoFamily.SPEED])
        ramp.run()
        # the first send already had its value in the ledger
        assert recorder.speeds[0] in pending[0]

    def test_the_reordered_ser2_stream_reads_as_a_takeover(self):
        # a ramp cannot be shown this stream: ABSOLUTE_SPEED is declared filtered, and the
        # one configuration that produces the replay - a Base 3 and a Ser2 together - is
        # exactly the one where ComponentStateStore drops filtered commands before they
        # reach engine state. Recognizing a repeat from further back would mean
        # recognizing every speed the ramp had swept through
        state = RampEngineState(speed=0, momentum=0)
        recorder = Recorder()
        ramp = build_ramp(state, 40, recorder)
        for speed in (10, 20, 30, 40):
            ramp.echo_ledger.record(EchoFamily.SPEED, speed)
        outcomes = [ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, s)) for s in SER2_REPLAY]
        assert outcomes == [True, True, True, False, True, False, True]

    def test_the_commanded_speed_is_always_ours(self):
        state, recorder, ramp = self.ramp()
        ramp.run()
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, ramp.commanded_speed)) is True
        # Even the current speed must have been sent inside the lag budget.
        ramp.echo_ledger.purge(ttl=0.0)
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, ramp.commanded_speed)) is False

    def test_an_initial_speed_that_was_never_sent_is_foreign(self):
        _, _, ramp = self.ramp(speed=12)
        assert ramp.on_state_command(req(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 12)) is False

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

    @pytest.mark.parametrize("command", [TMCC1EngineCommandEnum.TARGET_SPEED, TMCC2EngineCommandEnumEx.TARGET_SPEED])
    def test_retired_targets_do_not_arbitrate_or_change_local_intent(self, command):
        _, _, ramp = self.ramp()
        assert ramp.on_state_command(req(command, 17)) is True
        assert ramp.requested_speed == 40

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
