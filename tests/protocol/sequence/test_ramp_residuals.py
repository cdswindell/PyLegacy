from threading import Event, Thread, current_thread
from unittest.mock import Mock

import pytest

from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.sequence import speed_ramp
from src.pytrain.protocol.sequence.speed_ramp import EchoOutcome, RampStep
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

from .test_speed_ramp import RampEngineState, Recorder, build_ramp


def test_claim_is_public_and_initialized_before_acquisition():
    ramp = build_ramp(RampEngineState(), 12, Recorder())
    assert ramp.claim is None


def test_start_returns_before_claim_acknowledgment_without_emitting():
    recorder = Recorder()
    acquiring, acknowledge, returned = Event(), Event(), Event()
    peer = Mock()

    def acquire(ramp):
        assert current_thread() is ramp
        acquiring.set()
        assert acknowledge.wait(2)

    peer.acquire.side_effect = acquire
    ramp = build_ramp(RampEngineState(speed=60, labor=20, rpm=5), 12, recorder, peer=peer)
    failures = []

    def start():
        try:
            ramp.start()
        except Exception as exc:
            failures.append(exc)
        finally:
            returned.set()

    caller = Thread(target=start)
    caller.start()
    try:
        assert acquiring.wait(2)
        assert returned.wait(0.2), "start must not wait for broadcast acknowledgment"
        assert ramp.is_active is True
        assert ramp._claim_pending is True
        assert recorder.sent == []
    finally:
        acknowledge.set()
        caller.join(2)
        if ramp.ident is not None:
            ramp.join(2)
    assert not failures
    assert recorder.speeds[-1] == 12
    assert ramp._claim_pending is False
    assert ramp.is_active is False
    peer.release.assert_called_once_with(ramp)


def test_race_rejection_aborts_worker_without_speed_or_component_transmissions(caplog):
    recorder = Recorder()
    peer = Mock()
    peer.acquire.side_effect = ValueError("Ramp already owned by another process")
    ramp = build_ramp(RampEngineState(speed=60, labor=20, rpm=5), 12, recorder, peer=peer)
    ramp.start()
    ramp.join(2)
    assert recorder.sent == []
    assert ramp.is_alive() is False
    assert "already owned" in ramp.abort_reason
    assert "already owned" in caplog.text
    assert ramp._is_running is False
    assert ramp._claim_pending is False
    assert ramp.state.is_ramping is False
    peer.release.assert_called_once_with(ramp)


def test_pending_claim_ignores_ordinary_reports_without_replaying_them():
    recorder = Recorder()

    class Peer:
        def acquire(self, ramp):
            assert ramp._claim_pending is True
            assert recorder.sent == []
            for value in (30, 20, 37):
                assert ramp.on_state_command(report(value)) is True
            assert ramp.on_state_command(report(5, command=TMCC2EngineCommandEnum.DIESEL_RPM)) is True
            assert ramp.rpm_bias == 0
            ramp.claim = object()

        def release(self, ramp):
            assert ramp._claim_pending is False

    ramp = build_ramp(RampEngineState(rpm=0), 12, recorder, peer=Peer())
    ramp.run()
    assert ramp._claim_pending is False
    assert ramp.abort_reason is None
    assert recorder.speeds == [3, 6, 9, 12]
    assert ramp.arbitrate(report(37)) is EchoOutcome.FOREIGN


@pytest.mark.parametrize("protocol", [TMCC1EngineCommandEnum, TMCC2EngineCommandEnum])
def test_every_direction_overrides_pending_claim_and_repeat_suppression(protocol):
    ramp = build_ramp(RampEngineState(), 12, Recorder())
    ramp._claim_pending = True
    directions = {name for name in protocol.__members__ if "DIRECTION" in name}
    assert {"FORWARD_DIRECTION", "REVERSE_DIRECTION"} <= directions
    for name in directions:
        request = CommandReq.build(protocol[name], 12)
        for _ in range(3):
            assert speed_ramp.is_ramp_override(request), name
            assert ramp.on_state_command(request) is False, name


@pytest.mark.parametrize("protocol", [TMCC1EngineCommandEnum, TMCC2EngineCommandEnum])
@pytest.mark.parametrize("data", [0, 5])
def test_numeric_safety_overrides_pending_claim_on_every_repeat(protocol, data):
    ramp = build_ramp(RampEngineState(), 93, Recorder())
    ramp._claim_pending = True
    request = CommandReq.build(protocol.NUMERIC, 12, data)
    for _ in range(3):
        assert speed_ramp.is_ramp_override(request) is True
        assert ramp.arbitrate(request) is EchoOutcome.FOREIGN
        assert ramp.on_state_command(request) is False


@pytest.mark.parametrize("protocol", [TMCC1EngineCommandEnum, TMCC2EngineCommandEnum])
def test_named_safety_aliases_override_pending_claim_on_every_repeat(protocol):
    names = {
        "STOP_IMMEDIATE",
        "SPEED_STOP_HOLD",
        "RESET",
        "RESET_ONLY",
        "SHUTDOWN_IMMEDIATE",
        "SHUTDOWN_DELAYED",
        "SHUTDOWN_DELAYED_NOP",
        "EMERGENCY_STOP",
    }
    ramp = build_ramp(RampEngineState(), 93, Recorder())
    ramp._claim_pending = True
    tested = []
    for name in names & protocol.__members__.keys():
        request = CommandReq.build(protocol[name], 12)
        for _ in range(3):
            assert speed_ramp.is_ramp_override(request), name
            assert ramp.arbitrate(request) is EchoOutcome.FOREIGN, name
            assert ramp.on_state_command(request) is False, name
        tested.append(name)
    assert {"RESET", "SHUTDOWN_IMMEDIATE"} <= set(tested)


def test_remote_registry_guard_precedes_retarget_and_construction(monkeypatch):
    state = RampEngineState()
    state.is_remote_ramping = True
    registry = speed_ramp.RampRegistry()
    owner = Mock(is_active=True)
    registry._ramps[registry.key_for(state)] = owner
    construction = Mock(side_effect=AssertionError("must reject before construction"))
    monkeypatch.setattr(speed_ramp, "SpeedRamp", construction)
    with pytest.raises(ValueError, match="another process"):
        registry.ramp_to(state, 90)
    owner.retarget.assert_not_called()
    construction.assert_not_called()
    registry._ramps.clear()
    with pytest.raises(ValueError, match="another process"):
        registry.ramp_to(state, 90)
    construction.assert_not_called()


def test_mock_remote_flag_does_not_reject_local_retarget():
    state = RampEngineState()
    state.is_remote_ramping = Mock()
    registry = speed_ramp.RampRegistry()
    owner = Mock(is_active=True)
    registry._ramps[registry.key_for(state)] = owner
    assert registry.ramp_to(state, 90) is owner
    owner.retarget.assert_called_once_with(90, dialog=False)


def test_registry_retargets_pending_worker_without_reacquiring_or_blocking():
    state = RampEngineState()
    recorder = Recorder()
    registry = speed_ramp.RampRegistry()
    acquiring, acknowledge = Event(), Event()
    peer = Mock()

    def acquire(ramp):
        assert current_thread() is ramp
        assert registry.get(state) is ramp
        acquiring.set()
        assert acknowledge.wait(2)

    peer.acquire.side_effect = acquire
    ramp = registry.ramp_to(state, 12, sender=recorder, peer=peer, delay_scale=0)
    try:
        assert acquiring.wait(2)
        assert registry.ramp_to(state, 18, dialog=True) is ramp
        assert ramp.requested_speed == 18
        assert ramp.dialog is True
        assert recorder.sent == []
    finally:
        acknowledge.set()
        ramp.join(2)
    assert ramp.is_active is False
    assert recorder.speeds[-1] == 18
    peer.acquire.assert_called_once_with(ramp)
    peer.release.assert_called_once_with(ramp)


def test_safety_abort_while_acquiring_stops_without_waiting_or_late_speeds():
    recorder = Recorder()
    acquiring, acknowledge = Event(), Event()
    peer = Mock()

    def acquire(ramp):
        acquiring.set()
        assert acknowledge.wait(2)

    peer.acquire.side_effect = acquire
    ramp = build_ramp(RampEngineState(), 12, recorder, peer=peer)
    ramp.start()
    try:
        assert acquiring.wait(2)
        assert ramp.on_state_command(report(0)) is False
        ramp.abort("STOP_IMMEDIATE", hard_stop=True, yield_speed=0)
        assert ramp.is_active is False
        assert ramp.state.is_ramping is False
        assert recorder.speeds == []
        assert all(
            command == TMCC2EngineCommandEnum.ENGINE_LABOR and data == 12 for command, _, data, _ in recorder.sent
        )
    finally:
        acknowledge.set()
        ramp.join(2)
    assert ramp._claim_pending is False
    assert ramp._claim_acquired is False
    assert ramp.abort_reason == "STOP_IMMEDIATE"
    assert recorder.speeds == recorder.rpms == []
    peer.release.assert_called_once_with(ramp)


def report(data, *, is_rx=False, command=TMCC2EngineCommandEnum.ABSOLUTE_SPEED):
    request = CommandReq.build(command, 12, data)
    return CommandReq.from_bytes(request.as_bytes, from_tmcc_rx=is_rx)


def test_ordinary_takeover_is_completely_silent():
    recorder = Recorder()
    ramp = build_ramp(RampEngineState(), 120, recorder)
    ramp._send_step(RampStep(9, 20, 3, 0.2))
    before = list(recorder.sent)
    ramp.abort("untagged throttle takeover", target_speed=30, yield_speed=30)
    ramp._send_step(RampStep(12, 21, 4, 0.2))
    assert recorder.sent == before
    assert ramp.commanded_speed == 9


@pytest.mark.parametrize("is_rx", [False, True])
def test_zero_is_foreign_even_when_it_was_sent(is_rx):
    ramp = build_ramp(RampEngineState(), 120, Recorder())
    ramp._send(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, 0)
    for _ in range(3):
        assert ramp.arbitrate(report(0, is_rx=is_rx)) is EchoOutcome.FOREIGN


def test_ordinary_abort_during_send_prevents_trailing_components():
    entered, resume = Event(), Event()
    recorder = Recorder()
    ramp = build_ramp(RampEngineState(), 93, recorder)

    def send(*_):
        entered.set()
        assert resume.wait(2)

    recorder.hook = send
    worker = Thread(target=ramp._send_step, args=(RampStep(3, 20, 1, 0.2),))
    worker.start()
    try:
        assert entered.wait(2)
        ramp.abort("untagged throttle takeover", target_speed=30, yield_speed=30)
        assert ramp._is_running is False
        assert ramp.state.target_speed == 30
    finally:
        resume.set()
        worker.join(2)
    assert worker.is_alive() is False
    assert recorder.speeds == [3]
    assert recorder.rpms == recorder.labors == []


def test_peer_release_preserves_replacement_flags_and_database_target():
    state = RampEngineState()
    old = build_ramp(state, 120, Recorder())
    new = build_ramp(state, 93, Recorder())
    state.ramp = new
    state.is_ramping = True
    state.target_speed = 30
    old.abort("ordinary")
    old.run()
    assert state.ramp is new
    assert state.is_ramping is True
    assert state.target_speed == 30


@pytest.mark.parametrize("error", [None, OSError("unreachable"), ValueError("bad claim"), TimeoutError("late")])
def test_peer_acquisition_precedes_emission_and_always_releases(error):
    recorder = Recorder()
    events = []

    class Peer:
        def acquire(self, ramp):
            assert recorder.sent == []
            events.append("acquire")
            if error is not None:
                raise error

        def release(self, ramp):
            events.append("release")

    ramp = build_ramp(RampEngineState(), 12, recorder, peer=Peer())
    ramp.run()
    assert events == ["acquire", "release"]
    assert ramp._is_running is False
    assert ramp._claim_pending is False
    assert ramp.state.is_ramping is False
    if error is None:
        assert recorder.speeds[-1] == 12
        assert ramp.abort_reason is None
    else:
        assert str(error) in ramp.abort_reason
        assert recorder.sent == []


@pytest.mark.parametrize("error", [OSError("no endpoint"), ValueError("bad address"), ImportError("unavailable"), None])
def test_default_peer_setup_is_lazy_and_fails_closed(monkeypatch, error):
    recorder = Recorder()
    built = []

    def build():
        built.append(True)
        if error is not None:
            raise error
        return None

    monkeypatch.setattr(speed_ramp, "default_sender", recorder)
    monkeypatch.setattr("src.pytrain.protocol.sequence.ramp_peer.RampPeer.build", build)
    ramp = speed_ramp.SpeedRamp(RampEngineState(), 12, linger=0, delay_scale=0)
    assert built == []
    ramp.run()
    assert built == [True]
    assert recorder.sent == []
    assert "peer acquisition failed" in ramp.abort_reason
    assert ramp._is_running is False
    assert ramp._claim_pending is False
    assert ramp.state.is_ramping is False


def test_peer_release_error_cannot_leave_running_flags_set(caplog):
    recorder = Recorder()

    class Peer:
        def acquire(self, ramp):
            ramp.abort("rejected")

        def release(self, ramp):
            raise OSError("release failed")

    ramp = build_ramp(RampEngineState(), 12, recorder, peer=Peer())
    ramp.run()
    assert recorder.sent == []
    assert ramp.abort_reason == "rejected"
    assert "release failed" in caplog.text
    assert ramp._is_running is False
    assert ramp._claim_pending is False
    assert ramp.state.is_ramping is False


def test_completed_claim_releases_without_linger_and_only_once(monkeypatch):
    recorder = Recorder()
    peer = Mock()
    ramp = build_ramp(RampEngineState(), 12, recorder, peer=peer, linger=10)
    linger = Mock(side_effect=AssertionError("an owned ramp must release at completion"))
    monkeypatch.setattr(ramp, "_linger_for_retarget", linger)
    ramp.run()
    assert recorder.speeds[-1] == 12
    assert ramp.is_active is False
    assert ramp.state.is_ramping is False
    linger.assert_not_called()
    ramp.abort("already complete")
    peer.acquire.assert_called_once_with(ramp)
    peer.release.assert_called_once_with(ramp)


def test_retarget_during_settle_keeps_claim_and_restores_ramping_flag(monkeypatch):
    recorder = Recorder()
    state = RampEngineState()
    peer = Mock()
    ramp = build_ramp(state, 12, recorder, peer=peer)
    settle = ramp._settle

    def retarget_after_settle():
        settle()
        if ramp.requested_speed == 12:
            ramp.retarget(18)

    def observe(*_):
        if ramp.commanded_speed > 12:
            assert state.is_ramping is True

    monkeypatch.setattr(ramp, "_settle", retarget_after_settle)
    recorder.hook = observe
    ramp.run()
    assert recorder.speeds[-1] == 18
    assert ramp.abort_reason is None
    assert state.is_ramping is False
    peer.acquire.assert_called_once_with(ramp)
    peer.release.assert_called_once_with(ramp)
