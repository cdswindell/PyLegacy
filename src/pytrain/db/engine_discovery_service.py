#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Discover newly programmed engines using Base 3 database records."""

from __future__ import annotations

import logging
from collections import deque
from threading import RLock, Timer
from typing import Callable

from ..db.comp_data import CompData
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..pdi.base_req import BaseReq
from ..pdi.ble_req import BleReq
from ..pdi.constants import D4Action, PdiCommand
from ..pdi.d4_req import D4Req
from ..pdi.pdi_listener import PdiListener
from ..pdi.pdi_req import PdiReq
from ..protocol.constants import CommandScope

log = logging.getLogger(__name__)


class EngineDiscoveryService:
    """Discover 2D engines by memory query and 4D engines by roster traversal."""

    def __init__(self, on_discovery: Callable[[int], None]) -> None:
        self._on_discovery = on_discovery
        self._pending: set[int] = set()
        self._queue: deque[int] = deque()
        self._active: int | None = None
        self._record: int | None = None
        self._visited: set[int] = set()
        self._timeout: Timer | None = None
        self._watcher: StateWatcher | None = None
        self._found_record: int | None = None
        self._found_raw: bytes | None = None
        self._lock = RLock()
        self._started = False

    @staticmethod
    def _exists(tmcc_id: int) -> bool:
        if not ComponentStateStore.is_built():
            return False
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        return bool(
            state
            and not state.is_deleted
            and state.is_comp_data_record
            and (tmcc_id < 100 or (state.record_no is not None and state.record_no != 0xFFFF))
        )

    def request_discovery(self, tmcc_id: int) -> bool:
        """Queue discovery for an unknown engine."""
        if not 1 <= tmcc_id <= 9999:
            log.info("Engine discovery rejected invalid TMCC ID %s", tmcc_id)
            return False
        with self._lock:
            if self._exists(tmcc_id):
                log.info("Engine %s discovery skipped: database record already exists", tmcc_id)
                return False
            if tmcc_id in self._pending:
                log.info("Engine %s discovery skipped: request already pending", tmcc_id)
                return False
            self._pending.add(tmcc_id)
            self._queue.append(tmcc_id)
        try:
            self._on_discovery(tmcc_id)
        except Exception:
            self.complete(tmcc_id)
            raise
        self._begin_next()
        return True

    def _arm_timeout(self) -> None:
        if self._timeout is not None:
            self._timeout.cancel()
        timer = Timer(10.0, self._timed_out, args=(self._active, self._record))
        timer.daemon = True
        self._timeout = timer
        timer.start()

    def _timed_out(self, tmcc_id: int | None, record_no: int | None) -> None:
        with self._lock:
            if tmcc_id != self._active or record_no != self._record:
                return
        log.warning("Engine %s discovery timed out at record %s", tmcc_id, record_no)
        if tmcc_id is not None:
            self.complete(tmcc_id)

    def _begin_next(self) -> None:
        with self._lock:
            if not self._started:
                log.info("Engine discovery queued; service not started")
                return
            if self._active is not None:
                log.debug("Engine discovery waiting for active engine %s", self._active)
                return
            while self._queue:
                candidate = self._queue.popleft()
                if candidate in self._pending and not self._exists(candidate):
                    self._active = candidate
                    self._record = None
                    self._found_record = None
                    self._found_raw = None
                    self._visited.clear()
                    self._arm_timeout()
                    break
                log.info(
                    "Engine %s discovery skipped before dispatch: record already exists or no longer pending",
                    candidate,
                )
                self._pending.discard(candidate)
            else:
                return
        if candidate < 100:
            log.info("Engine %s discovery sending BASE_MEMORY query", candidate)
            with self._lock:
                self._found_record = 0xFFFF  # 2D records have no D4 record number.
                state = ComponentStateStore.get_state(CommandScope.ENGINE, candidate)
                self._watcher = StateWatcher(state, lambda: self._verify_found(candidate))
            PdiListener.enqueue_command(BaseReq(candidate, PdiCommand.BASE_MEMORY, scope=CommandScope.ENGINE))
        else:
            log.info("Engine %s discovery sending D4 FIRST_REC", candidate)
            PdiListener.enqueue_command(D4Req(0, PdiCommand.D4_ENGINE, D4Action.FIRST_REC))

    def complete(self, tmcc_id: int) -> None:
        """Release the discovery slot, including after failure or timeout."""
        with self._lock:
            self._pending.discard(tmcc_id)
            if self._active == tmcc_id:
                if self._timeout is not None:
                    self._timeout.cancel()
                    self._timeout = None
                watcher = self._watcher
                self._watcher = None
                if watcher is not None:
                    watcher.shutdown()
                self._active = None
                self._found_record = None
                self._found_raw = None
                self._record = None
                self._visited.clear()
        self._begin_next()

    def _on_d4(self, response: D4Req) -> None:
        if response.pdi_command != PdiCommand.D4_ENGINE:
            return
        with self._lock:
            target = self._active
            if target is None:
                return
            if response.action == D4Action.FIRST_REC:
                if self._record is not None:
                    return
            elif response.action == D4Action.NEXT_REC:
                if self._record is None or response.record_no != self._record:
                    return
                if not response.is_comp_data_record or response.comp_data is None:
                    log.warning("Incomplete NEXT_REC response for record %s", self._record)
                    self.complete(target)
                    return
                if response.tmcc_id == target:
                    self._found_record = response.record_no
                    self._found_raw = response._data_bytes
                    # Subscribe before the dispatcher applies this record, so the
                    # state notification can confirm successful population.
                    state = ComponentStateStore.get_state(CommandScope.ENGINE, target)
                    self._watcher = StateWatcher(state, lambda: self._verify_found(target))
                    self._verify_found(target)  # Covers a record already populated.
                    return
            else:
                return
            next_record = response.next_record_no
            if next_record is None or next_record == 0xFFFF or next_record in self._visited:
                log.info("Engine %s not found in Base 3 D4 roster", target)
                self.complete(target)
                return
            self._visited.add(next_record)
            self._record = next_record
            self._arm_timeout()
        PdiListener.enqueue_command(
            D4Req(
                next_record,
                PdiCommand.D4_ENGINE,
                D4Action.NEXT_REC,
                data_length=PdiReq.scope_record_length(CommandScope.ENGINE),
            )
        )

    @staticmethod
    def _is_discovery_complete(state, tmcc_id: int, record_no: int | None) -> bool:
        if state is None or state.is_deleted or state.tmcc_id != tmcc_id:
            return False
        if not state.is_comp_data_record or state.comp_data is None:
            return False
        if tmcc_id >= 100:
            if state.record_no is None or state.record_no == 0xFFFF:
                return False
            if record_no is not None and state.record_no != record_no:
                return False
            if not state.is_d4 or not state.is_legacy:
                return False
        elif not state.comp_data.is_active():
            return False
        return True

    @staticmethod
    def _correct_default_momentum(state, raw: bytes | None = None) -> None:
        """Replace uninitialized Base 3 momentum bytes after discovery."""
        comp_data = state.comp_data
        raw = raw if raw is not None else comp_data.as_bytes()
        if raw[0x18] != 0xFF or raw[0x17] != 0xFF:
            return
        requests = []
        for field, value in (("momentum", 0), ("momentum_setting", 0x63)):
            request = CompData.generate_update_req(field, value, state=state)
            if request is None:
                log.warning("Engine %s momentum correction could not update %s", state.tmcc_id, field)
                return
            requests.append(request)
        for request in requests:
            PdiListener.enqueue_command(request)
        PdiListener.enqueue_command(BaseReq.create_base_query_request(state))
        log.info("Engine %s queued momentum correction and database refresh", state.tmcc_id)

    def _verify_found(self, tmcc_id: int) -> None:
        with self._lock:
            if self._active != tmcc_id or self._found_record is None:
                return
            state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
            expected_record = self._found_record if tmcc_id >= 100 else None
            if not self._is_discovery_complete(state, tmcc_id, expected_record):
                return
            self._correct_default_momentum(state, self._found_raw)
            log.info("Engine %s discovered in Base 3 database", tmcc_id)
            self.complete(tmcc_id)

    def __call__(self, notification: PdiReq) -> None:
        if isinstance(notification, BleReq):
            log.info(
                "Engine discovery received BLE notification: TMCC ID %s, programming=%s",
                notification.tmcc_id,
                notification.is_programming,
            )
            if notification.is_programming:
                self.request_discovery(notification.tmcc_id)
        elif isinstance(notification, D4Req):
            self._on_d4(notification)

    def start(self) -> None:
        if self._started:
            return
        # Like StartupState, subscribe to all PDI responses so FIRST_REC
        # can be received even though it has no engine TMCC ID.
        PdiListener.get().subscribe_any(self)
        self._started = True
        log.info("Engine discovery subscribed to PDI broadcasts")
        self._begin_next()

    def stop(self) -> None:
        if not self._started:
            return
        PdiListener.get().unsubscribe_any(self)
        log.info("Engine discovery unsubscribed from PDI broadcasts")
        with self._lock:
            if self._timeout is not None:
                self._timeout.cancel()
                self._timeout = None
            if self._watcher is not None:
                self._watcher.shutdown()
                self._watcher = None
            self._found_record = None
            self._found_raw = None
            self._started = False
            self._active = None
            self._record = None
            self._pending.clear()
            self._queue.clear()
            self._visited.clear()
