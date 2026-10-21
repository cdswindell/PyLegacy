import socket
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event, RLock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.comm.comm_buffer import CommBuffer, CommBufferProxy, CommBufferSingleton
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import PdiCommand
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from src.pytrain.protocol.sequence import ramp_peer
from src.pytrain.protocol.sequence.ramp_peer import (
    CLAIM_REFRESH,
    RampClaim,
    RampPeer,
    advertised_host,
    publish_claim,
)
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm

from .test_speed_ramp import RampEngineState, Recorder, build_ramp

pytestmark = pytest.mark.usefixtures("ramp_target_update")


class PeerRamp:
    def __init__(self, peer, *, address=3180, scope=CommandScope.ENGINE):
        self._peer = peer
        self.scope = scope
        self.tmcc_id = address
        self.state = SimpleNamespace(ramp_claim=None, update=lambda command: acknowledge(peer, self, command))
        self.claim = None
        self.is_active = True
        self.reason = None

    def abort(self, reason):
        self.is_active = False
        self.reason = reason


@pytest.fixture
def peers():
    instances = []

    def create(publisher: Callable[[CommandReq], None] = lambda command: None):
        instances.append(RampPeer("127.0.0.1", publisher=publisher))
        return instances[-1]

    yield create
    for instance in instances:
        instance.close()


def acknowledge(peer, ramp, command):
    claim = RampClaim.from_request(command)
    if command.command == TMCC2EngineCommandEnumEx.RAMP_CLAIM:
        current = ramp.state.ramp_claim
        accepted = current in (None, claim) or claim.priority < current.priority
        if accepted:
            ramp.state.ramp_claim = claim
        peer.claim_received(ramp, claim, accepted=accepted)
    elif ramp.state.ramp_claim == claim:
        ramp.state.ramp_claim = None


def claim_publisher(announcements: Queue, releases: Queue | None = None) -> Callable[[CommandReq], None]:
    """Record claim traffic without delivering an ownership echo."""

    def publish(command):
        if command.command == TMCC2EngineCommandEnumEx.RAMP_CLAIM:
            announcements.put(command)
        elif releases is not None:
            releases.put(command)

    return publish


# The peer is deliberately driven by a minimal ramp double rather than a worker thread.
# noinspection PyTypeChecker
def test_first_claim_needs_only_normal_broadcast_and_no_sockets(peers, monkeypatch):
    monkeypatch.setattr(socket, "socket", Mock(side_effect=AssertionError("No listener")))
    monkeypatch.setattr(socket, "create_connection", Mock(side_effect=AssertionError("No peer connection")))
    peer = peers()
    ramp = PeerRamp(peer)
    published = []

    def publish(command):
        published.append(command)
        acknowledge(peer, ramp, command)

    peer._publisher = publish
    peer.acquire(ramp)
    assert ramp.is_active
    assert ramp.state.ramp_claim == ramp.claim
    assert len(published) == 1
    assert (published[0].host, published[0].port) == (peer.host, peer.port)
    assert 1 <= published[0].claim_id <= 65535
    assert not hasattr(peer, "_server")
    assert not hasattr(peer, "_listener")
    assert not hasattr(peer, "request_history")


# Minimal ramp doubles isolate ownership from worker execution.
# noinspection PyTypeChecker
def test_known_owner_rejects_new_ramp_without_contacting_or_canceling_it(peers):
    old_peer = peers()
    old = PeerRamp(old_peer)
    old_peer._publisher = lambda command: acknowledge(old_peer, old, command)
    old_peer.acquire(old)
    new_peer = peers()
    new = PeerRamp(new_peer)
    new.state.ramp_claim = old.claim
    published = []
    new_peer._publisher = published.append
    with pytest.raises(ValueError, match="already owned"):
        new_peer.acquire(new)
    assert old.is_active
    assert old.state.ramp_claim == old.claim
    assert published == []
    assert new.claim is None


# Minimal ramp doubles let the test control claim delivery independently of workers.
# noinspection PyTypeChecker
@pytest.mark.parametrize("reverse", [False, True])
def test_simultaneous_claims_accept_first_in_broadcast_order(peers, monkeypatch, reverse):
    """Creation timestamps now decide the winner, regardless of broadcast order."""
    clock = [1_800_000_000_000_000_000]
    # Patch the module's imported clock, not the process-wide time function.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(ramp_peer, "time_ns", lambda: clock[0])
    published = Queue()

    publish = claim_publisher(published)

    first_peer, second_peer = peers(publish), peers(publish)
    first, second = PeerRamp(first_peer), PeerRamp(second_peer)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_result = pool.submit(first_peer.acquire, first)
        first_command = published.get(timeout=1)
        first_result.result(timeout=1)
        clock[0] += 1_000_000
        second_result = pool.submit(second_peer.acquire, second)
        second_command = published.get(timeout=1)
        second_result.result(timeout=1)
        assert first.is_active and second.is_active
        commands = (second_command, first_command) if reverse else (first_command, second_command)
        for command in commands:
            acknowledge(first_peer, first, command)
            acknowledge(second_peer, second, command)
    assert first.is_active
    assert not second.is_active
    assert first.state.ramp_claim == second.state.ramp_claim == first.claim
    assert first.claim.timestamp_ms + 1 == second.claim.timestamp_ms


# Minimal ramp doubles are required to hold acquisition independently of worker startup.
# noinspection PyTypeChecker
def test_second_local_claim_cannot_bypass_pending_first_claim(peers):
    published = Queue()
    peer = peers(published.put)
    first, second = PeerRamp(peer), PeerRamp(peer)
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(peer.acquire, first)
        command = published.get(timeout=1)
        with pytest.raises(ValueError, match="already owned locally"):
            peer.acquire(second)
        acknowledge(peer, first, command)
        result.result(timeout=1)
    assert first.is_active
    assert second.claim is None


# The minimal ramp double isolates cancellation while the publisher is blocked.
# noinspection PyTypeChecker
def test_cancellation_during_claim_wait_never_succeeds(peers):
    published = Queue()
    proceed = Event()

    def publish(command):
        published.put(command)
        assert proceed.wait(1)

    peer = peers(publish)
    ramp = PeerRamp(peer)
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(peer.acquire, ramp)
        published.get(timeout=1)
        ramp.abort("HALT")
        proceed.set()
        with pytest.raises(OSError, match="canceled"):
            result.result(timeout=1)
    assert ramp.reason == "HALT"


# Inspect the peer's session for the minimal ramp double without starting a worker.
# noinspection PyTypeChecker
def test_missing_own_announcement_fails_closed(peers):
    # Claim echoes are optional: acquisition must return before one is delivered.
    peer = peers()
    ramp = PeerRamp(peer)
    peer.acquire(ramp)
    assert ramp.is_active
    assert not peer._ramps[ramp].retired
    assert ramp.state.ramp_claim == ramp.claim


# A minimal ramp double isolates the peer's refresh and release lifecycle.
# noinspection PyTypeChecker
def test_release_is_nonblocking_and_claim_refresh_is_not_a_handoff(peers, monkeypatch):
    peer = peers()
    ramp = PeerRamp(peer)
    released = Event()
    published = []

    def publish(command):
        published.append(command)
        acknowledge(peer, ramp, command)
        if command.command == TMCC2EngineCommandEnumEx.RAMP_RELEASE:
            released.set()

    peer._publisher = publish
    peer.acquire(ramp)
    session = peer._ramps[ramp]
    # Patch the module's imported clock to force the refresh deadline.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(ramp_peer, "monotonic", lambda: session.refreshed + CLAIM_REFRESH)
    peer._maintain()
    assert published[0].as_bytes == published[1].as_bytes
    assert ramp.is_active
    peer.release(ramp)
    peer.release(ramp)
    assert released.wait(1)
    assert ramp.state.ramp_claim is None
    assert sum(command.command == TMCC2EngineCommandEnumEx.RAMP_RELEASE for command in published) == 1


# Inspect retirement of a minimal ramp double after a publisher failure.
# noinspection PyTypeChecker
def test_publication_failure_releases_candidate_without_fallback(peers):
    peer = peers(Mock(side_effect=OSError("unavailable")))
    ramp = PeerRamp(peer)
    with pytest.raises(OSError, match="unavailable"):
        peer.acquire(ramp)
    assert peer._ramps[ramp].retired


def test_claim_publication_uses_existing_state_api_only(monkeypatch):
    buffer = Mock()
    monkeypatch.setattr(CommBuffer, "get", lambda: buffer)
    command = RampClaim(CommandScope.ENGINE, 3180, "127.0.0.1", 50000, 20).request()
    publish_claim(command)
    buffer.update_state.assert_called_once_with(command)
    buffer.enqueue_command.assert_not_called()


def test_client_source_address_is_used_without_discovery(monkeypatch):
    monkeypatch.delenv("PYTRAIN_RAMP_HOST", raising=False)
    client = object.__new__(CommBufferProxy)
    client._ephemeral_port = ("192.168.4.55", 54321)
    client._base3_address = None
    monkeypatch.setattr(CommBuffer, "_instance", client)
    monkeypatch.setattr(socket, "socket", Mock(side_effect=AssertionError("No discovery")))
    assert advertised_host() == "192.168.4.55"


def test_manual_address_override_requires_no_transport(monkeypatch):
    monkeypatch.setenv("PYTRAIN_RAMP_HOST", "192.168.4.12")
    monkeypatch.setattr(CommBuffer, "get", Mock(side_effect=AssertionError("No discovery")))
    assert advertised_host() == "192.168.4.12"


def test_server_state_publication_never_enters_hardware_buffers(monkeypatch):
    from src.pytrain.comm.command_listener import CommandDispatcher

    command = RampClaim(CommandScope.ENGINE, 7, "127.0.0.1", 50000, 20).request()
    dispatcher = Mock()
    monkeypatch.setattr(CommandDispatcher, "get", lambda: dispatcher)
    # A transport-free receiver proves this method uses only the dispatcher.
    # noinspection PyTypeChecker
    CommBufferSingleton.update_state(SimpleNamespace(), command)
    dispatcher.offer.assert_called_once_with(command)


def test_client_state_publication_wraps_claim_in_existing_state_request():
    from src.pytrain.comm.enqueue_proxy_requests import SENDING_STATE_REQUEST

    command = RampClaim(CommandScope.TRAIN, 7, "127.0.0.1", 50000, 20).request()
    client = SimpleNamespace(enqueue_command=Mock())
    # Supply only the enqueue interface so this test cannot start a real client.
    # noinspection PyTypeChecker
    CommBufferProxy.update_state(client, command)
    client.enqueue_command.assert_called_once_with(SENDING_STATE_REQUEST + command.as_bytes)


@pytest.fixture
def engine_states(monkeypatch):
    from src.pytrain.db.component_state_store import ComponentStateStore
    from src.pytrain.db.engine_state import EngineState, TrainState
    from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE

    monkeypatch.setattr(CommBuffer, "is_server", lambda: False)
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", lambda: False)

    def create(scope, address):
        state = TrainState(scope) if scope == CommandScope.TRAIN else EngineState(scope)
        state.initialize(scope, address)
        state._address = address
        state._empty = False
        state._is_legacy = True
        state.comp_data._control_type = LEGACY_CONTROL_TYPE
        state.comp_data.speed = state.comp_data.target_speed = 60
        return state

    return create


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("address", [7, 3180])
def test_real_owner_keeps_destination_and_competitor_emits_nothing(peers, engine_states, monkeypatch, scope, address):
    from src.pytrain.protocol.sequence.speed_ramp import RampStep, SpeedRamp

    states = [engine_states(scope, address) for _ in range(2)]
    bus_lock = RLock()
    released = Event()

    def publish(command):
        with bus_lock:
            for replica in states:
                replica.update(CommandReq.from_bytes(command.as_bytes))
        if command.command == TMCC2EngineCommandEnumEx.RAMP_RELEASE:
            released.set()

    old_peer, new_peer = peers(publish), peers(publish)
    old_sent, new_sent = [], []
    old = SpeedRamp(states[0], 100, sender=lambda *args: old_sent.append(args), peer=old_peer)
    states[0]._ramp = old
    # Override the inherited Thread method to drive this worker synchronously.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(old, "is_alive", lambda: True)
    old_peer.acquire(old)
    old._send_step(RampStep(63, None, None, 0.2))
    assert states[0].is_remote_ramping is False
    assert states[1].is_remote_ramping is True
    new = SpeedRamp(states[1], 20, sender=lambda *args: new_sent.append(args), peer=new_peer)
    states[1]._ramp = new
    new.start()
    new.join(timeout=1)
    assert not new.is_alive()
    reason = new.abort_reason
    assert reason is not None
    assert "already owned" in reason
    assert old.is_active
    assert old.requested_speed == 100
    assert new_sent == []
    assert states[1].ramp_claim == old.claim
    for speed in range(66, 101, 3):
        old._send_step(RampStep(min(speed, 100), None, None, 0.2))
    old._send_step(RampStep(100, None, None, 0.2))
    old_peer.release(old)
    assert released.wait(1)
    assert all(state.ramp_claim is None and not state.is_remote_ramping for state in states)


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize(
    "speed, target, first_command",
    [
        (0, 12, TMCC2EngineCommandEnum.ABSOLUTE_SPEED),
        (120, 20, TMCC2EngineCommandEnum.ENGINE_LABOR),
        (45, 45, TMCC2EngineCommandEnum.ABSOLUTE_SPEED),
    ],
)
def test_startup_target_follows_claim_and_precedes_every_component(
    pdi_send, ramp_target_update, scope, speed, target, first_command
):
    events = []
    peer = Mock()
    peer.acquire.side_effect = lambda _ramp: events.append("claim")
    peer.release.side_effect = lambda _ramp: events.append("release")
    pdi_send.side_effect = lambda _request, **_kwargs: events.append("target")
    # This records submission, not completion of asynchronous database transport.
    ramp_target_update.side_effect = lambda *_args, **_kwargs: events.append("database request")
    state = RampEngineState(scope=scope, speed=speed, rpm=tmcc2_speed_to_rpm(speed))
    recorder = Recorder(lambda _rec, _count: events.append("component"))
    ramp = build_ramp(state, target, recorder, peer=peer)

    ramp.run()

    assert events == ["claim", "target", "database request", *(["component"] * len(recorder.sent)), "release"]
    ramp_target_update.assert_called_once_with("RAMP_TARGET_SPEED", target, state, refresh=False)
    assert recorder.commands[0] == first_command
    assert recorder.speeds[-1] == target
    peer.acquire.assert_called_once_with(ramp)
    peer.release.assert_called_once_with(ramp)
    pdi_send.assert_called_once()
    request = pdi_send.call_args.args[0]
    assert pdi_send.call_args.kwargs == {"delay": 0}
    assert isinstance(request, BaseReq)
    # Outbound requests carry the address in record_no and the scope in the command.
    assert request.record_no == state.tmcc_id
    assert request.pdi_command == (
        PdiCommand.UPDATE_TRAIN_SPEED if scope == CommandScope.TRAIN else PdiCommand.UPDATE_ENGINE_SPEED
    )
    assert request.target_speed == target
    assert request.speed is None
    # Check the current unmarked short-address emission, not the separate incoming parser.
    # These addresses, targets, and checksums do not require byte stuffing.
    command_byte = 0x2B if scope == CommandScope.TRAIN else 0x2A
    payload = bytes([command_byte, state.tmcc_id, target])
    assert request.as_bytes == b"\xd1" + payload + bytes([-sum(payload) & 0xFF]) + b"\xdf"


@pytest.mark.parametrize("canceled", [False, True])
def test_failed_or_canceled_acquisition_never_announces_target(pdi_send, ramp_target_update, canceled):
    peer = Mock()
    if canceled:
        peer.acquire.side_effect = lambda worker: worker.abort("canceled during acquisition")
    else:
        peer.acquire.side_effect = OSError("claim unavailable")
    recorder = Recorder()
    state = RampEngineState()
    ramp = build_ramp(state, 60, recorder, peer=peer)

    ramp.run()

    assert ramp.abort_reason == (
        "canceled during acquisition" if canceled else "peer acquisition failed: claim unavailable"
    )
    assert state.is_ramping is False
    assert recorder.sent == []
    peer.release.assert_called_once_with(ramp)
    pdi_send.assert_not_called()
    ramp_target_update.assert_not_called()


def test_target_send_failure_releases_claim_without_component_commands(pdi_send, ramp_target_update):
    peer = Mock()
    recorder = Recorder()
    state = RampEngineState()
    ramp = build_ramp(state, 60, recorder, peer=peer)
    pdi_send.side_effect = OSError("target send failed")

    with pytest.raises(OSError, match="target send failed"):
        ramp.run()

    assert state.is_ramping is False
    assert ramp.is_active is False
    assert recorder.sent == []
    peer.release.assert_called_once_with(ramp)
    ramp_target_update.assert_not_called()


def test_database_update_failure_releases_claim_without_component_commands(pdi_send, ramp_target_update):
    peer = Mock()
    recorder = Recorder()
    state = RampEngineState()
    ramp = build_ramp(state, 60, recorder, peer=peer)
    ramp_target_update.side_effect = OSError("database update failed")

    with pytest.raises(OSError, match="database update failed"):
        ramp.run()

    pdi_send.assert_called_once()
    ramp_target_update.assert_called_once_with("RAMP_TARGET_SPEED", 60, state, refresh=False)
    assert state.is_ramping is False
    assert ramp.is_active is False
    assert recorder.sent == []
    peer.release.assert_called_once_with(ramp)


def test_real_ramp_emits_only_after_claim_confirmation_and_releases_on_completion(
    peers, engine_states, pdi_send, ramp_target_update
):
    from src.pytrain.protocol.sequence.speed_ramp import SpeedRamp

    state = engine_states(CommandScope.ENGINE, 7)
    announcement = Queue()
    first_step, released = Event(), Event()
    events = []
    pdi_send.side_effect = lambda _request, **_kwargs: events.append("target")

    def publish(command):
        if command.command == TMCC2EngineCommandEnumEx.RAMP_CLAIM:
            events.append("claim")
            announcement.put(command)
        else:
            state.update(command)
            events.append("release")
            released.set()

    def send_component(*_args):
        events.append("component")
        first_step.set()

    peer = peers(publish)
    ramp = SpeedRamp(state, 63, sender=send_component, peer=peer, delay_scale=0, linger=0)
    state._ramp = ramp
    ramp.start()
    try:
        assert first_step.wait(1)
        ramp.join(timeout=1)
        assert not ramp.is_alive()
        assert ramp.commanded_speed == 63
        assert released.wait(1)
        assert state.ramp_claim is None
        assert events[:3] == ["claim", "target", "component"]
        assert events[-1] == "release"
        pdi_send.assert_called_once()
        assert pdi_send.call_args.args[0].target_speed == 63
        ramp_target_update.assert_called_once_with("RAMP_TARGET_SPEED", 63, state, refresh=False)
        # Completion does not depend on an echo, and a late echo cannot relock it.
        state.update(announcement.get(timeout=1))
        assert state.ramp_claim is None
    finally:
        ramp.abort("test complete")
        ramp.join(timeout=1)


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
@pytest.mark.parametrize("address", [7, 3180])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("same_millisecond", [False, True])
def test_timestamp_race_converges_without_startup_echo(
    peers, engine_states, monkeypatch, scope, address, reverse, same_millisecond
):
    from src.pytrain.protocol.sequence.speed_ramp import RampStep, SpeedRamp

    clock = [1_800_000_000_000_000_000]
    # Patch the module's imported clock to choose a deterministic claim winner.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(ramp_peer, "time_ns", lambda: clock[0])
    states = [engine_states(scope, address) for _ in range(3)]
    announcements, releases = Queue(), Queue()

    publish = claim_publisher(announcements, releases)

    first_peer, second_peer = peers(publish), peers(publish)
    first_peer.port, second_peer.port = 40000, 40001
    first_sent, second_sent = [], []
    first = SpeedRamp(states[0], 100, sender=lambda *args: first_sent.append(args), peer=first_peer)
    second = SpeedRamp(states[1], 0, sender=lambda *args: second_sent.append(args), peer=second_peer)
    for state, ramp in zip(states, (first, second)):
        state._ramp = ramp
        # Override the inherited Thread method while explicitly stepping both workers.
        # noinspection PyUnresolvedReferences
        monkeypatch.setattr(ramp, "is_alive", lambda: True)
    first._acquire_claim()
    if not same_millisecond:
        clock[0] += 1_000_000
    second._acquire_claim()
    first_command, second_command = announcements.get(timeout=1), announcements.get(timeout=1)
    assert first.is_active and second.is_active
    assert not states[0].is_remote_ramping and not states[1].is_remote_ramping
    first._send_step(RampStep(63, None, None, 0.2))
    second._send_step(RampStep(57, None, None, 0.2))
    assert first_sent and second_sent  # Neither requester waited for an echo.

    commands = (second_command, first_command) if reverse else (first_command, second_command)
    for replica in states:
        for command in commands:
            replica.update(CommandReq.from_bytes(command.as_bytes))
    assert first.is_active
    assert not second.is_active
    reason = second.abort_reason
    assert reason is not None
    assert "earlier request" in reason
    assert all(state.ramp_claim == first.claim for state in states)
    assert not states[0].is_remote_ramping
    assert states[1].is_remote_ramping and states[2].is_remote_ramping
    assert first.requested_speed == 100

    # A losing release or late echo must neither clear nor resurrect ownership.
    losing_release = releases.get(timeout=1)
    assert RampClaim.from_request(losing_release) == second.claim
    for replica in states:
        replica.update(losing_release)
        replica.update(second_command)
        replica.update(first_command)
        assert replica.ramp_claim == first.claim
    count = len(second_sent)
    second._send_step(RampStep(54, 10, 1, 0.2))
    assert len(second_sent) == count == 1  # Silent cancellation: no speed/effort replay.
    first._send_step(RampStep(66, None, None, 0.2))
    assert [entry[2] for entry in first_sent] == [63, 66]


def test_unconfirmed_claim_refreshes_locally_and_keeps_original_timestamp(peers, engine_states, monkeypatch):
    from src.pytrain.db import engine_state
    from src.pytrain.protocol.sequence.speed_ramp import SpeedRamp

    clock = [100.0]
    # Both modules import their clocks; keep state expiration and peer refresh synchronized.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(engine_state, "monotonic", lambda: clock[0])
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(ramp_peer, "monotonic", lambda: clock[0])
    published = []
    peer = peers(published.append)
    state = engine_states(CommandScope.ENGINE, 7)
    ramp = SpeedRamp(state, 100, sender=lambda *args: None, peer=peer)
    state._ramp = ramp
    # Override the inherited Thread method without starting a real ramp loop.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(ramp, "is_alive", lambda: True)
    peer.acquire(ramp)
    peer._ramps[ramp].refreshed = clock[0]
    for _ in range(4):
        clock[0] += CLAIM_REFRESH
        peer._maintain()
        assert state.ramp_claim == ramp.claim
        assert not state.is_remote_ramping
    assert len(published) >= 5
    assert all(command.as_bytes == published[0].as_bytes for command in published)


def test_own_echo_does_not_cancel_or_rebase_local_destination(peers, engine_states, monkeypatch):
    from src.pytrain.protocol.sequence.speed_ramp import SpeedRamp

    peer = peers()
    state = engine_states(CommandScope.ENGINE, 3180)
    ramp = SpeedRamp(state, 100, sender=lambda *args: None, peer=peer)
    state._ramp = ramp
    # Override the inherited Thread method to test echoes without background sends.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(ramp, "is_alive", lambda: True)
    peer.acquire(ramp)
    original = ramp.claim
    ramp.retarget(80)
    for _ in range(3):
        state.update(CommandReq.from_bytes(original.request().as_bytes))
        assert ramp.is_active
        assert ramp.claim == original
        assert ramp.requested_speed == 80
        assert not state.is_remote_ramping
