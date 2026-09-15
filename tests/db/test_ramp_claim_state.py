from types import SimpleNamespace

import pytest

from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.db import engine_state
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_state import EngineState
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope, TMCC_CONTROL_TYPE
from src.pytrain.protocol.multibyte.ramp_command_req import RampCommandReq
from src.pytrain.protocol.sequence.ramp_peer import CLAIM_TTL, RampClaim
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum as TMCC1, TMCC1HaltCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as TMCC2


@pytest.fixture
def state(monkeypatch):
    monkeypatch.setattr(CommBuffer, "is_server", lambda: False)
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", lambda: False)
    state = EngineState(CommandScope.ENGINE)
    state.initialize(CommandScope.ENGINE, 7)
    state._address = 7
    state._empty = False
    state.comp_data._control_type = TMCC_CONTROL_TYPE
    state.comp_data.speed = state.comp_data.target_speed = 20
    state._is_legacy = False
    return state


def claim(identifier=1):
    return RampClaim(CommandScope.ENGINE, 7, "127.0.0.1", 50000, identifier)


def test_first_claim_wins_until_matching_release(state):
    state.update(claim(1).request())
    state.update(claim(2).request())
    assert state.ramp_claim == claim(1)
    state.update(claim(2).request(release=True))
    assert state.ramp_claim == claim(1)
    state.update(claim(1).request(release=True))
    state.update(claim(3).request())
    assert state.ramp_claim == claim(3)


def test_remote_claim_blocks_ramp_start_without_replacing_owner(state):
    state.update(claim().request())
    assert state.is_remote_ramping is True
    with pytest.raises(ValueError, match="already owned"):
        state.ramp_to(0)
    assert state.ramp is None
    assert state.ramp_claim == claim()


def test_claim_is_metadata_not_remote_ramp_or_speed_change(state):
    before = state.speed, state.target_speed, state.is_legacy
    state.update(claim().request())
    assert state.ramp_claim == claim()
    assert state.ramp is None
    assert not state.is_ramping
    assert (state.speed, state.target_speed, state.is_legacy) == before


def test_local_claim_keeps_own_throttle_enabled(state):
    state.update(claim().request())
    state._ramp = SimpleNamespace(claim=claim(), is_active=True)
    assert state.is_remote_ramping is False
    state._ramp.claim = claim(2)
    assert state.is_remote_ramping is True
    state._ramp.claim = claim()
    state._ramp.is_active = False
    assert state.is_remote_ramping is True


def test_delayed_release_and_refresh_cannot_erase_new_owner(state):
    state.update(claim(1).request())
    state.update(claim(1).request(release=True))
    state.update(claim(2).request())
    state.update(claim(1).request(release=True))
    state.update(claim(1).request())
    assert state.ramp_claim == claim(2)


def test_rejected_claim_cannot_reappear_after_owner_completes(state):
    state.update(claim(1).request())
    state.update(claim(2).request())
    state.update(claim(1).request(release=True))
    state.update(claim(2).request())
    assert state.ramp_claim is None
    assert state.is_remote_ramping is False


def test_release_before_announcement_does_not_create_abandoned_owner(state):
    state.update(claim().request(release=True))
    state.update(claim().request())
    assert state.ramp_claim is None


def test_matching_release_unlocks_without_residual_endpoint(state):
    state.update(claim().request())
    assert state.is_remote_ramping is True
    state.changed.clear()
    state.update(claim().request(release=True))
    assert state.ramp_claim is None
    assert state.is_remote_ramping is False
    assert state.changed.is_set()
    assert not hasattr(state, "recent_ramp_claim")


def test_local_ramp_lifecycle_notifies_watchers_without_speed_updates(state):
    for running in (True, False):
        state.changed.clear()
        state.is_ramping = running
        assert state.changed.is_set()


def test_lease_refresh_and_expiration_are_bounded(state, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(engine_state, "monotonic", lambda: clock[0])
    state.update(claim().request())
    clock[0] += CLAIM_TTL / 2
    state.update(claim().request())
    clock[0] += CLAIM_TTL / 2
    assert state.ramp_claim == claim()
    clock[0] += CLAIM_TTL / 2
    assert state.ramp_claim is None
    assert state.is_remote_ramping is False
    state.update(claim(2).request())
    assert state.ramp_claim == claim(2)


@pytest.mark.parametrize("released", [False, True])
def test_current_state_sync_contains_only_active_claim(state, released):
    state.update(claim().request())
    if released:
        state.update(claim().request(release=True))
    packets = state.as_bytes()
    claims = []
    for packet in packets:
        if packet[0] in (0xF8, 0xF9):
            command = CommandReq.from_bytes(packet)
            if isinstance(command, RampCommandReq):
                claims.append(command)
    assert [request.as_bytes for request in claims] == ([] if released else [claim().request().as_bytes])
    replica = EngineState(CommandScope.ENGINE)
    replica.initialize(CommandScope.ENGINE, 7)
    replica._address = 7
    replica._empty = False
    for request in claims:
        replica.update(request)
    assert replica.ramp_claim == (None if released else claim())
    assert replica.is_remote_ramping is not released
    assert replica.ramp is None


@pytest.mark.parametrize("pending", [False, True])
@pytest.mark.parametrize(
    "command, data",
    [
        (TMCC1HaltCommandEnum.HALT, 0),
        (TMCC2.SYSTEM_HALT, 0),
        (TMCC1.RESET_ONLY, 0),
        (TMCC2.SHUTDOWN_DELAYED, 0),
        (TMCC2.SHUTDOWN_DELAYED_NOP, 0),
    ]
    + [
        (command, 0)
        for family in (TMCC1, TMCC2)
        for command in (
            family.ABSOLUTE_SPEED,
            family.EMERGENCY_STOP,
            family.STOP_IMMEDIATE,
            family.SPEED_STOP_HOLD,
            family.RESET,
            family.SHUTDOWN_IMMEDIATE,
            family.FORWARD_DIRECTION,
            family.REVERSE_DIRECTION,
            family.TOGGLE_DIRECTION,
        )
    ]
    + [(family.NUMERIC, value) for family in (TMCC1, TMCC2) for value in (0, 5)],
)
def test_safety_overrides_claims_and_duplicate_suppression(state, monkeypatch, pending, command, data):
    from src.pytrain.protocol.sequence.speed_ramp import EchoFamily, SpeedRamp

    request = CommandReq.build(command, 7, data)
    for identifier in (1, 2):
        if command.name in {"FORWARD_DIRECTION", "REVERSE_DIRECTION"}:
            # Each iteration changes direction; repeating the existing direction is not an override.
            family = type(command)
            state._direction = (
                family.REVERSE_DIRECTION if command.name == "FORWARD_DIRECTION" else family.FORWARD_DIRECTION
            )
        state.update(claim(identifier).request())
        ramp = SpeedRamp(state, 100, sender=lambda *args: None)
        monkeypatch.setattr(ramp, "is_alive", lambda: True)
        ramp.claim = claim(identifier)
        ramp._claim_pending = pending
        state._ramp = ramp
        state.is_ramping = True
        ramp.echo_ledger.record(EchoFamily.SPEED, 0)
        state.update(request)
        assert not ramp.is_active
        assert not state.is_ramping
        assert state.ramp is None
        assert state.ramp_claim is None
        assert state.speed == state.target_speed == 0


def test_nonowner_speed_updates_never_create_peer_service(state, monkeypatch):
    from src.pytrain.protocol.sequence.ramp_peer import RampPeer

    def unexpected():
        raise AssertionError("Nonowners do not participate in ramp coordination")

    monkeypatch.setattr(RampPeer, "build", unexpected)
    state.update(claim().request())
    state.update(CommandReq.build(TMCC1.ABSOLUTE_SPEED, 7, 5))
    assert state.speed == state.target_speed == 5
    assert state.ramp is None
    assert state.ramp_claim == claim()


def test_foreign_claim_cannot_stop_local_owner_or_change_database(state, monkeypatch):
    from src.pytrain.protocol.sequence.ramp_peer import RampPeer
    from src.pytrain.protocol.sequence.speed_ramp import SpeedRamp

    sent = []
    peer = RampPeer("127.0.0.1", publisher=state.update)
    ramp = SpeedRamp(state, 30, sender=lambda *args: sent.append(args), peer=peer)
    state._ramp = ramp
    monkeypatch.setattr(ramp, "is_alive", lambda: True)
    try:
        peer.acquire(ramp)
        ramp._commanded_speed = 25
        before = state.speed, state.target_speed
        state.update(claim(99).request())
        assert ramp.is_active
        assert state.ramp_claim == ramp.claim
        assert state.is_remote_ramping is False
        assert (state.speed, state.target_speed) == before
        assert sent == []
    finally:
        peer.close()
