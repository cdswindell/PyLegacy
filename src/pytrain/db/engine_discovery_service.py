#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Coordinate discovery requests for engine addresses not yet in the Base 3 roster."""

from __future__ import annotations

from threading import RLock
from typing import Callable

from ..comm.command_observer import CommandObserver
from ..db.component_state_store import ComponentStateStore
from ..pdi.ble_req import BleReq
from ..pdi.constants import PdiCommand
from ..pdi.pdi_listener import PdiListener
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


class EngineDiscoveryService:
    """Detect unknown engines; record fetching is a separate implementation phase."""

    def __init__(self, on_discovery: Callable[[int], None]) -> None:
        self._on_discovery = on_discovery
        self._pending: set[int] = set()
        self._lock = RLock()
        self._started = False

    @staticmethod
    def _exists(tmcc_id: int) -> bool:
        if not ComponentStateStore.is_built():
            return False
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        return bool(state and not state.is_deleted and state.comp_data is not None)

    def request_discovery(self, tmcc_id: int) -> bool:
        """Return True only for the first request for an unknown engine."""
        if not 1 <= tmcc_id <= 9999:
            return False
        with self._lock:
            if self._exists(tmcc_id) or tmcc_id in self._pending:
                return False
            self._pending.add(tmcc_id)
        try:
            self._on_discovery(tmcc_id)
        except Exception:
            self.complete(tmcc_id)
            raise
        return True

    def complete(self, tmcc_id: int) -> None:
        """Release a discovery slot after success, failure, or timeout."""
        with self._lock:
            self._pending.discard(tmcc_id)

    def on_command(self, command: CommandReq) -> None:
        if (
            command.command
            in {
                TMCC1EngineCommandEnum.SET_ADDRESS,
                TMCC2EngineCommandEnum.SET_ADDRESS,
            }
            and command.scope == CommandScope.ENGINE
        ):
            self.request_discovery(command.address)

    def __call__(self, notification: BleReq) -> None:
        if isinstance(notification, BleReq) and notification.is_programming:
            self.request_discovery(notification.tmcc_id)

    def start(self) -> None:
        if self._started:
            return
        CommandObserver.register(TMCC1EngineCommandEnum.SET_ADDRESS, self.on_command)
        CommandObserver.register(TMCC2EngineCommandEnum.SET_ADDRESS, self.on_command)
        try:
            PdiListener.listen_for(self, PdiCommand.BLE_RX)
        except Exception:
            CommandObserver.unregister(TMCC1EngineCommandEnum.SET_ADDRESS, self.on_command)
            CommandObserver.unregister(TMCC2EngineCommandEnum.SET_ADDRESS, self.on_command)
            raise
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        CommandObserver.unregister(TMCC1EngineCommandEnum.SET_ADDRESS, self.on_command)
        CommandObserver.unregister(TMCC2EngineCommandEnum.SET_ADDRESS, self.on_command)
        PdiListener.get().unsubscribe(self, PdiCommand.BLE_RX)
        self._started = False
