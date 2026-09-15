#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

"""Exclusive ramp claims carried only by the existing state-update transport."""

from __future__ import annotations

import atexit
import ipaddress
import logging
import os
import secrets
import socket
from dataclasses import dataclass, field
from threading import Event, RLock, Thread
from time import monotonic
from typing import TYPE_CHECKING, Callable

from ..constants import CommandScope
from ..multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from ..multibyte.ramp_command_req import RampCommandReq

if TYPE_CHECKING:
    from .speed_ramp import SpeedRamp

log = logging.getLogger(__name__)

CLAIM_REFRESH = 5.0
CLAIM_TTL = 15.0
CLAIM_TIMEOUT = 0.75


@dataclass(frozen=True)
class RampClaim:
    scope: CommandScope
    address: int
    host: str
    port: int
    claim_id: int

    @classmethod
    def from_request(cls, command: RampCommandReq) -> RampClaim:
        return cls(command.scope, command.address, command.host, command.port, command.claim_id)

    def request(self, *, release: bool = False) -> RampCommandReq:
        command = TMCC2EngineCommandEnumEx.RAMP_RELEASE if release else TMCC2EngineCommandEnumEx.RAMP_CLAIM
        return RampCommandReq.for_endpoint(command, self.address, self.host, self.port, self.claim_id, self.scope)


def advertised_host() -> str:
    """Use the registered client's source address, then the route to the Base/local LAN."""
    from ...comm.comm_buffer import CommBuffer

    override = os.environ.get("PYTRAIN_RAMP_HOST")
    if override:
        return str(ipaddress.IPv4Address(override))
    buffer = CommBuffer.get()
    if CommBuffer.is_client():
        try:
            # Despite its name, server_ip() returns the local end of the client socket.
            return str(ipaddress.IPv4Address(buffer.server_ip()))
        except (AttributeError, ValueError):
            pass
    try:
        destination = str(ipaddress.IPv4Address(buffer.base3_address))
    except (AttributeError, ValueError):
        destination = "192.0.2.1"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        # Route selection only: no packet, listening socket, or peer connection.
        probe.connect((destination, 9))
        return probe.getsockname()[0]


def publish_claim(command: RampCommandReq) -> None:
    from ...comm.comm_buffer import CommBuffer

    # The existing state-only path bypasses both Base 3 and SER2 writes on server/client.
    CommBuffer.get().update_state(command)


@dataclass
class _Session:
    ramp: SpeedRamp
    claim: RampClaim
    seen: bool = False
    retired: bool = False
    refreshed: float = field(default_factory=monotonic)
    ready: Event = field(default_factory=Event)
    error: str | None = None


class RampPeer:
    """Publish and release local claims; never contact or cancel a remote ramp."""

    _instance: RampPeer | None = None
    _instance_lock = RLock()

    @classmethod
    def build(cls) -> RampPeer:
        with cls._instance_lock:
            if cls._instance is None or cls._instance._closed.is_set():
                cls._instance = cls(advertised_host())
                atexit.register(cls._instance.close)
            return cls._instance

    def __init__(self, host: str, *, port: int = 0, publisher: Callable = publish_claim):
        self.host = host
        # Preserve the wire layout. The former port is now an opaque process nonce;
        # no port is bound and no cancellation service exists at this address.
        self.port = port or secrets.randbelow(65535) + 1
        self._publisher = publisher
        self._lock = RLock()
        self._ramps: dict[SpeedRamp, _Session] = {}
        self._next_id = secrets.randbelow(65535) + 1
        self._closed = Event()
        self._work = Event()
        self._worker = Thread(target=self._run, name="PyTrain Ramp Claims", daemon=True)
        self._worker.start()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        with self._lock:
            sessions = list(self._ramps.values())
        for session in sessions:
            session.ramp.abort("ramp claim service shutdown")
            self.release(session.ramp)
        self._work.set()
        self._worker.join(timeout=1)

    def acquire(self, ramp: SpeedRamp) -> None:
        if self._closed.is_set():
            raise OSError("Ramp claim service is closed")
        previous = getattr(ramp.state, "ramp_claim", None)
        if previous is not None:
            raise ValueError(f"Ramp already owned by {previous.host} for {ramp.scope.title} {ramp.tmcc_id}")
        with self._lock:
            if any(
                not session.retired and (session.claim.scope, session.claim.address) == (ramp.scope, ramp.tmcc_id)
                for session in self._ramps.values()
            ):
                raise ValueError(f"Ramp already owned locally for {ramp.scope.title} {ramp.tmcc_id}")
            claim = RampClaim(ramp.scope, ramp.tmcc_id, self.host, self.port, self._next_id)
            self._next_id = self._next_id % 65535 + 1
            session = self._ramps[ramp] = _Session(ramp, claim)
            ramp.claim = claim
        try:
            self._publisher(claim.request())
            deadline = monotonic() + CLAIM_TIMEOUT
            while not session.ready.is_set():
                if not ramp.is_active or self._closed.is_set():
                    raise OSError("Ramp was canceled while claiming ownership")
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError("Ramp claim was not confirmed by the server")
                session.ready.wait(min(remaining, 0.02))
            if session.error is not None:
                raise ValueError(session.error)
            if session.retired or not ramp.is_active:
                raise OSError("Ramp was canceled while claiming ownership")
        except Exception:
            self.release(ramp)
            raise

    def claim_received(self, ramp: SpeedRamp, claim: RampClaim, *, accepted: bool = True) -> None:
        """Only synthetic announcements reach here, in server/broadcast order."""
        with self._lock:
            session = self._ramps.get(ramp)
            if session is None or session.retired:
                return
            if claim == session.claim and accepted:
                session.seen = True
                session.ready.set()
                return
            if (claim == session.claim and not accepted) or (claim != session.claim and accepted):
                session.error = f"Ramp already owned by another controller for {claim.scope.title} {claim.address}"
                session.ready.set()
            else:
                return
        # Never stop the incumbent in response to a rejected competing claim.
        ramp.abort(session.error)

    def release(self, ramp: SpeedRamp) -> None:
        """Schedule a matching release without blocking the command dispatch thread."""
        with self._lock:
            session = self._ramps.get(ramp)
            if session is not None:
                session.retired = True
                session.ready.set()
        self._work.set()

    def _release_claim(self, session: _Session) -> None:
        self._publisher(session.claim.request(release=True))
        with self._lock:
            if self._ramps.get(session.ramp) is session:
                del self._ramps[session.ramp]

    def _run(self) -> None:
        while True:
            self._work.wait(0.1)
            self._work.clear()
            self._maintain()
            if self._closed.is_set():
                return

    def _maintain(self) -> None:
        now = monotonic()
        with self._lock:
            sessions = list(self._ramps.values())
        for session in sessions:
            try:
                if session.retired:
                    self._release_claim(session)
                elif session.seen and now - session.refreshed >= CLAIM_REFRESH:
                    self._publisher(session.claim.request())
                    session.refreshed = now
            except (OSError, ValueError) as exc:
                log.warning("Ramp claim publication failed: %s", exc)
