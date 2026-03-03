#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
#

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Any, TYPE_CHECKING

from .base_req import BaseReq  # adjust import if needed
from ..utils.singleton import singleton  # adjust import to your actual location

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..db.engine_state import EngineState, TrainState

    StateT = EngineState | TrainState
else:
    StateT = Any


@dataclass
class _Bucket:
    pending: bool = False
    first_request_t: Optional[float] = None
    last_request_t: Optional[float] = None
    latest_state: Optional[StateT] = None

    # For cleanup / aging
    last_activity_t: float = 0.0


@singleton
class Base3DbRefreshManager:
    """
    Singleton, fire-and-forget debounced Base 3 DB refresh manager with PER (scope, tmcc_id) buckets.

    Keying: f"{state.scope}:{state.tmcc_id}"

    Additions implemented:
      1) Idle bucket cleanup (prevents unbounded growth)
      3) flush(state): forces an immediate update for that key (no debounce wait)

    Notes:
      - One daemon thread total; never one per request.
      - Does NOT wait for Base 3 response; existing server plumbing processes it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # plumbing
        self._send_request: Optional[Callable[[Any], None]] = None

        # debounce tuning
        self._debounce_s: float = 0.35
        self._max_delay_s: float = 1.5

        # bucket cleanup tuning
        self._bucket_ttl_s: float = 10.0 * 60.0  # prune buckets idle for 10 minutes
        self._cleanup_interval_s: float = 60.0  # run pruning about once a minute
        self._next_cleanup_t: float = time.monotonic() + self._cleanup_interval_s

        # buckets keyed by "scope:tmcc_id"
        self._buckets: dict[str, _Bucket] = {}

    # ----------------------------
    # Configuration
    # ----------------------------

    @classmethod
    def configure(
        cls,
        *,
        send_request: Callable[[Any], None],
        debounce_s: float = 0.35,
        max_delay_s: float = 1.5,
        bucket_ttl_s: float = 10.0 * 60.0,
        cleanup_interval_s: float = 60.0,
    ) -> None:
        """
        Configure the singleton. Safe to call multiple times; last call wins.
        """
        inst = cls()
        with inst._lock:
            inst._send_request = send_request
            inst._debounce_s = float(debounce_s)
            inst._max_delay_s = float(max_delay_s)
            inst._bucket_ttl_s = float(bucket_ttl_s)
            inst._cleanup_interval_s = float(cleanup_interval_s)
            inst._next_cleanup_t = time.monotonic() + inst._cleanup_interval_s

    # ----------------------------
    # Public API
    # ----------------------------

    @classmethod
    def request_refresh(
        cls,
        state: StateT,
        *,
        send_request: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """
        Fire-and-forget request for Base 3 DB refresh, debounced per (scope, tmcc_id).
        """
        inst = cls()

        # Allow first caller to provide plumbing inline.
        if send_request is not None:
            with inst._lock:
                inst._send_request = send_request

        inst._ensure_started()
        inst._enqueue(state)
        # `reason` intentionally unused (reserved for future logging/diagnostics)

    @classmethod
    def flush(
        cls,
        state: StateT,
        *,
        send_request: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """
        Force an immediate update for this specific (scope, tmcc_id) key.
        Still fire-and-forget; does not wait for Base 3 response.
        """
        inst = cls()

        if send_request is not None:
            with inst._lock:
                inst._send_request = send_request

        inst._ensure_started()
        inst._force_ready(state)
        # `reason` reserved for future logging
        inst._wakeup.set()

    # ----------------------------
    # Internal
    # ----------------------------

    @staticmethod
    def _key(state: StateT) -> str:
        # As requested: Scope:TMCC_ID
        return f"{state.scope}:{state.tmcc_id}"

    def _ensure_started(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="Base3DbRefreshManager",
                daemon=True,  # ✅ daemon thread
            )
            self._thread.start()

    def _enqueue(self, state: StateT) -> None:
        now = time.monotonic()
        key = self._key(state)

        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(last_activity_t=now)
                self._buckets[key] = b

            b.latest_state = state
            b.last_activity_t = now

            if not b.pending:
                b.pending = True
                b.first_request_t = now
            b.last_request_t = now

        self._wakeup.set()

    def _force_ready(self, state: StateT) -> None:
        """
        Mark the bucket for `state` as ready to send immediately.
        """
        now = time.monotonic()
        key = self._key(state)

        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket(last_activity_t=now)
                self._buckets[key] = b

            b.latest_state = state
            b.last_activity_t = now

            # Make it eligible for immediate update on next loop
            b.pending = True
            b.first_request_t = now
            b.last_request_t = now - (self._debounce_s + 1.0)

    def _cleanup_buckets_locked(self, now: float) -> None:
        """
        Remove buckets that have been idle beyond TTL and are not pending.
        Must be called with self._lock held.
        """
        if self._bucket_ttl_s <= 0:
            return

        cutoff = now - self._bucket_ttl_s
        dead_keys = [key for key, b in self._buckets.items() if (not b.pending) and (b.last_activity_t <= cutoff)]
        for key in dead_keys:
            self._buckets.pop(key, None)

        self._next_cleanup_t = now + self._cleanup_interval_s

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wakeup.wait(timeout=0.25)
            self._wakeup.clear()

            if self._stop.is_set():
                break

            ready: list[StateT] = []
            next_wake_in: Optional[float] = None
            now = time.monotonic()

            with self._lock:
                # Periodic pruning
                if self._cleanup_interval_s > 0 and now >= self._next_cleanup_t:
                    self._cleanup_buckets_locked(now)

                send_request = self._send_request
                if send_request is None:
                    continue

                for b in self._buckets.values():
                    if not b.pending or b.latest_state is None:
                        continue

                    first_t = b.first_request_t or now
                    last_t = b.last_request_t or now
                    quiet_for = now - last_t
                    age = now - first_t

                    should_send = (quiet_for >= self._debounce_s) or (0 < self._max_delay_s <= age)

                    if should_send:
                        ready.append(b.latest_state)
                        b.pending = False
                        b.first_request_t = None
                        b.last_request_t = None
                        b.last_activity_t = now
                    else:
                        by_quiet = self._debounce_s - quiet_for
                        by_max = (self._max_delay_s - age) if self._max_delay_s > 0 else by_quiet
                        candidate = max(0.01, min(by_quiet, by_max))
                        if next_wake_in is None or candidate < next_wake_in:
                            next_wake_in = candidate

            # Send outside lock (fire-and-forget)
            if ready:
                for state in ready:
                    try:
                        req = BaseReq.create_base_query_request(state)
                        req.send()
                    except Exception as e:
                        log.error(e)
                        pass
                continue

            if next_wake_in is not None:
                self._wakeup.wait(timeout=next_wake_in)
                self._wakeup.clear()

    def stop(self) -> None:
        """Optional explicit stop (daemon thread doesn’t require it)."""
        self._stop.set()
        self._wakeup.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2.0)
