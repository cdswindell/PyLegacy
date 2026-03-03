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
from typing import Any, Optional, TYPE_CHECKING

from .base_req import BaseReq
from ..utils.singleton import singleton

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..db.engine_state import EngineState, TrainState

    StateT = EngineState | TrainState
else:
    StateT = Any


@dataclass
class _Bucket:
    pending: bool = False
    first_t: float = 0.0
    last_t: float = 0.0
    last_activity_t: float = 0.0
    latest_state: Optional[StateT] = None


# noinspection PyChainedComparisons
@singleton
class Base3DbRefreshManager:
    """
    Debounced, fire-and-forget Base 3 DB query sender.

    Call Base3DbRefreshManager.request_refresh(state) freely; calls are debounced
    independently per key = f"{state.scope}:{state.tmcc_id}".

    When a bucket becomes ready, we do:
        BaseReq.create_base_query_request(state).send()

    One daemon worker thread total.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Debounce behavior
        self._debounce_s: float = 0.35
        self._max_delay_s: float = 1.5

        # Cleanup to prevent unbounded growth
        self._bucket_ttl_s: float = 10.0 * 60.0  # prune idle buckets after 10 min
        self._cleanup_interval_s: float = 60.0  # prune about once per minute
        self._next_cleanup_t: float = time.monotonic() + self._cleanup_interval_s

        self._buckets: dict[str, _Bucket] = {}

    # ---- public API ----

    @classmethod
    def request_refresh(cls, state: StateT) -> None:
        inst = cls()
        inst._ensure_started()
        if state is not None:
            inst._enqueue(state)
            print(f"Refresh request: {state.scope}:{state.tmcc_id}")

    @classmethod
    def flush(cls, state: StateT) -> None:
        """Force immediate send for this key (no debounce wait)."""
        inst = cls()
        inst._ensure_started()
        inst._force_ready(state)
        inst._wake.set()

    # ---- internal ----

    @staticmethod
    def _key(state: StateT) -> str:
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
                b = _Bucket()
                self._buckets[key] = b

            b.latest_state = state
            b.last_activity_t = now

            if not b.pending:
                b.pending = True
                b.first_t = now
            b.last_t = now

        self._wake.set()

    def _force_ready(self, state: StateT) -> None:
        now = time.monotonic()
        key = self._key(state)

        with self._lock:
            b = self._buckets.get(key)
            if b is None:
                b = _Bucket()
                self._buckets[key] = b

            b.latest_state = state
            b.last_activity_t = now

            b.pending = True
            b.first_t = now
            # make it "quiet long enough" immediately
            b.last_t = now - (self._debounce_s + 0.001)

    def _cleanup_locked(self, now: float) -> None:
        if self._bucket_ttl_s <= 0:
            self._next_cleanup_t = now + self._cleanup_interval_s
            return

        cutoff = now - self._bucket_ttl_s
        dead = [k for k, b in self._buckets.items() if (not b.pending) and (b.last_activity_t <= cutoff)]
        for k in dead:
            self._buckets.pop(k, None)

        self._next_cleanup_t = now + self._cleanup_interval_s

    def _run(self) -> None:
        while not self._stop.is_set():
            # Wake periodically even without events to ensure max_delay + cleanup work
            self._wake.wait(timeout=0.25)
            self._wake.clear()

            if self._stop.is_set():
                break

            now = time.monotonic()
            to_send: list[StateT] = []
            next_sleep: Optional[float] = None

            with self._lock:
                # cleanup
                if self._cleanup_interval_s > 0 and now >= self._next_cleanup_t:
                    self._cleanup_locked(now)

                for b in self._buckets.values():
                    if not b.pending or b.latest_state is None:
                        continue

                    quiet_for = now - b.last_t
                    age = now - b.first_t

                    should_send = quiet_for >= self._debounce_s or (self._max_delay_s > 0 and age >= self._max_delay_s)

                    if should_send:
                        to_send.append(b.latest_state)
                        b.pending = False
                    else:
                        # compute the earliest time we should re-check
                        by_quiet = self._debounce_s - quiet_for
                        by_max = (self._max_delay_s - age) if self._max_delay_s > 0 else by_quiet
                        candidate = max(0.01, min(by_quiet, by_max))
                        if next_sleep is None or candidate < next_sleep:
                            next_sleep = candidate

            # send outside lock
            if to_send:
                for state in to_send:
                    try:
                        if state is not None:
                            BaseReq.create_base_query_request(state).send()
                            log.debug(f"Update requested: {state.scope}:{state.tmcc_id}")
                    except Exception as e:
                        log.exception(f"Base3DbRefreshManager: failed to send base query request: {e}")
                continue

            if next_sleep is not None:
                # Sleep until the earliest bucket is due (or until new activity arrives),
                # then re-evaluate with a fresh time.monotonic().
                self._wake.wait(timeout=next_sleep)
                self._wake.clear()
                continue

    def stop(self) -> None:
        """Optional; daemon thread means you don't need this for shutdown."""
        self._stop.set()
        self._wake.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=2.0)
