"""Deliver scope-wide state changes through one waiting thread per Qt bridge."""

from __future__ import annotations

from threading import Lock, Thread
from typing import Iterable

from PySide6.QtCore import QObject, Qt, Signal, Slot

from pytrain.db.state_changes import StateChangeHub, state_changes
from pytrain.protocol.constants import CommandScope


class QtStateChangeBridge(QObject):
    """Keep identifiers coalesced until Qt drains a single queued wakeup."""

    changesReady = Signal(object)
    wakeRequested = Signal()

    def __init__(
        self,
        scopes: Iterable[CommandScope],
        parent: QObject | None = None,
        *,
        hub: StateChangeHub = state_changes,
    ) -> None:
        super().__init__(parent)
        self._closed = False
        self._delivery_lock = Lock()
        self._hub = hub
        self._subscription = hub.subscribe(scopes)
        self.wakeRequested.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self._thread = Thread(target=self._receive, daemon=True, name="PyCab state changes")
        self._thread.start()

    def _receive(self) -> None:
        while self._subscription.wait():
            with self._delivery_lock:
                if self._closed:
                    return
                self.wakeRequested.emit()

    @Slot()
    def _deliver(self) -> None:
        if not self._closed:
            changes = self._subscription.drain()
            if changes:
                self.changesReady.emit(changes)

    def receiveRecordChange(self, command) -> None:
        """Treat CREATE broadcasts as hints; completed updates publish again."""
        if not self._closed:
            scope = getattr(command, "scope", None)
            address = getattr(command, "tmcc_id", None)
            if scope is not None:
                self._hub.publish(scope, address)

    def close(self) -> None:
        """Discard pending deliveries and wake the receiver without joining Qt."""
        with self._delivery_lock:
            self._closed = True
            self._subscription.close()
