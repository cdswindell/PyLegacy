import socket
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event, RLock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.comm.comm_buffer import CommBuffer, CommBufferProxy, CommBufferSingleton
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


class PeerRamp:
    def __init__(self, peer, *, address=3180, scope=CommandScope.ENGINE):
        self._peer = peer
        self.scope = scope
        self.tmcc_id = address
        self.state = SimpleNamespace(ramp_claim=None)
        self.claim = None
        self.is_active = True
        self.reason = None

    def abort(self, reason):
        self.is_active = False
        self.reason = reason


@pytest.fixture
def peers():
    instances = []

    def create(publisher=lambda command: None):
        instance = RampPeer("127.0.0.1", publisher=publisher)
        instances.append(instance)
        return instance

    yield create
    for instance in instances:
        instance.close()


def acknowledge(peer, ramp, command):
    claim = RampClaim.from_request(command)
    if command.command == TMCC2EngineCommandEnumEx.RAMP_CLAIM:
        accepted = ramp.state.ramp_claim in (None, claim)
        if accepted:
            ramp.state.ramp_claim = claim
        peer.claim_received(ramp, claim, accepted=accepted)
    elif ramp.state.ramp_claim == claim:
        ramp.state.ramp_claim = None


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
    assert peer._ramps[ramp].seen
    assert len(published) == 1
    command = published[0]
    assert (command.host, command.port) == (peer.host, peer.port)
    assert 1 <= command.claim_id <= 65535
    assert not hasattr(peer, "_server")
    assert not hasattr(peer, "_listener")
    assert not hasattr(peer, "request_history")


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


@pytest.mark.parametrize("reverse", [False, True])
def test_simultaneous_claims_accept_first_in_broadcast_order(peers, reverse):
    published = Queue()

    def publish(command):
        if command.command == TMCC2EngineCommandEnumEx.RAMP_CLAIM:
            published.put(command)

    first_peer, second_peer = peers(publish), peers(publish)
    first, second = PeerRamp(first_peer), PeerRamp(second_peer)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_result = pool.submit(first_peer.acquire, first)
        first_command = published.get(timeout=1)
        second_result = pool.submit(second_peer.acquire, second)
        second_command = published.get(timeout=1)
        assert not first_result.done()
        assert not second_result.done()
        commands = (second_command, first_command) if reverse else (first_command, second_command)
        for command in commands:
            acknowledge(first_peer, first, command)
            acknowledge(second_peer, second, command)
        winner, loser = (second, first) if reverse else (first, second)
        winner_result, loser_result = (second_result, first_result) if reverse else (first_result, second_result)
        winner_result.result(timeout=1)
        with pytest.raises(ValueError, match="already owned"):
            loser_result.result(timeout=1)
    assert winner.is_active
    assert not loser.is_active
    assert first.state.ramp_claim == second.state.ramp_claim == winner.claim


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


def test_cancellation_during_claim_wait_never_succeeds(peers):
    published = Queue()
    peer = peers(published.put)
    ramp = PeerRamp(peer)
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(peer.acquire, ramp)
        published.get(timeout=1)
        ramp.abort("HALT")
        with pytest.raises(OSError, match="canceled"):
            result.result(timeout=1)
    assert ramp.reason == "HALT"


def test_missing_own_announcement_fails_closed(peers, monkeypatch):
    monkeypatch.setattr(ramp_peer, "CLAIM_TIMEOUT", 0.02)
    peer = peers()
    ramp = PeerRamp(peer)
    with pytest.raises(TimeoutError, match="not confirmed"):
        peer.acquire(ramp)
    assert not peer._ramps.get(ramp) or peer._ramps[ramp].retired


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
    monkeypatch.setattr(ramp_peer, "monotonic", lambda: session.refreshed + CLAIM_REFRESH)
    peer._maintain()
    assert published[0].as_bytes == published[1].as_bytes
    assert ramp.is_active
    peer.release(ramp)
    peer.release(ramp)
    assert released.wait(1)
    assert ramp.state.ramp_claim is None
    assert sum(command.command == TMCC2EngineCommandEnumEx.RAMP_RELEASE for command in published) == 1


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
    CommBufferSingleton.update_state(SimpleNamespace(), command)
    dispatcher.offer.assert_called_once_with(command)


def test_client_state_publication_wraps_claim_in_existing_state_request():
    from src.pytrain.comm.enqueue_proxy_requests import SENDING_STATE_REQUEST

    command = RampClaim(CommandScope.TRAIN, 7, "127.0.0.1", 50000, 20).request()
    client = SimpleNamespace(enqueue_command=Mock())
    CommBufferProxy.update_state(client, command)
    client.enqueue_command.assert_called_once_with(SENDING_STATE_REQUEST + command.as_bytes)


@pytest.fixture
def engine_states(monkeypatch):
    from src.pytrain.db.component_state_store import ComponentStateStore
    from src.pytrain.db.engine_state import EngineState
    from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE

    monkeypatch.setattr(CommBuffer, "is_server", lambda: False)
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", lambda: False)

    def create(scope, address):
        state = EngineState(scope)
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
    assert "already owned" in new.abort_reason
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


def test_real_ramp_emits_only_after_claim_confirmation_and_releases_on_completion(peers, engine_states):
    from src.pytrain.protocol.sequence.speed_ramp import SpeedRamp

    state = engine_states(CommandScope.ENGINE, 7)
    announcement = Queue()
    first_step, released = Event(), Event()

    def publish(command):
        if command.command == TMCC2EngineCommandEnumEx.RAMP_CLAIM:
            announcement.put(command)
        else:
            state.update(command)
            released.set()

    peer = peers(publish)
    ramp = SpeedRamp(state, 63, sender=lambda *args: first_step.set(), peer=peer, delay_scale=0, linger=0)
    state._ramp = ramp
    ramp.start()
    try:
        command = announcement.get(timeout=1)
        assert not first_step.is_set()
        state.update(command)
        assert first_step.wait(1)
        ramp.join(timeout=1)
        assert not ramp.is_alive()
        assert ramp.commanded_speed == 63
        assert released.wait(1)
        assert state.ramp_claim is None
    finally:
        ramp.abort("test complete")
        ramp.join(timeout=1)
