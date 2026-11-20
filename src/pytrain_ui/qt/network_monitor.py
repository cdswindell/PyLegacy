"""Sample local Wi-Fi information without blocking the Qt event loop."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from pathlib import Path
from socket import AF_INET
from threading import Event, Thread

import psutil
from PySide6.QtCore import QObject, Property, Qt, QTimer, Signal, Slot

from pytrain.utils.ip_tools import get_local_ipv4
from pytrain.utils.wifi_info import WiFiInfo, WiFiSnapshot

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NetworkReading:
    wifi: WiFiSnapshot = field(default_factory=WiFiSnapshot)
    address: str | None = None
    ethernet: bool = False

    def as_map(self) -> dict:
        wifi = self.wifi
        quality = wifi.quality
        if quality is None:
            quality = WiFiInfo.dbm_to_quality(wifi.signal_dbm)
        if quality is not None:
            quality = max(0, min(100, quality))
        connected = wifi.connected
        connection = "Wi-Fi" if connected else "Ethernet" if self.ethernet else "Network"
        if not connected and wifi.interface and not self.ethernet:
            connection = "Wi-Fi disconnected"
        signal = "Signal unavailable"
        bars = 0
        color = "#9aafc2"
        level = -1
        if connected and quality is not None:
            level = quality
            signal = f"{quality}% · {WiFiInfo.quality_label(quality)}"
            bars = min(4, (quality + 24) // 25)
            if quality >= 60:
                color = "#36cb85"
            elif quality >= 20:
                color = "#e9ad43"
            else:
                color = "#ff656d"
        return {
            "connection": connection,
            "ssid": (wifi.ssid or "") if connected else "",
            "address": self.address or "Unavailable",
            "quality": level,
            "signal": signal,
            "bars": bars,
            "color": color,
            "wireless": connected or (bool(wifi.interface) and not self.ethernet),
        }


def read_network(wifi: WiFiInfo) -> NetworkReading:
    """Use the existing Wi-Fi helper and the local routing-table address."""
    snapshot = wifi.query()
    address = get_local_ipv4()
    ethernet = False
    if not snapshot.connected and address:
        # Confirm a physical wired Linux interface; do not guess from a missing SSID.
        for interface, entries in psutil.net_if_addrs().items():
            if any(entry.family == AF_INET and entry.address == address for entry in entries):
                device = Path("/sys/class/net") / interface
                ethernet = (device / "device").exists() and not (device / "wireless").exists()
                break
    return NetworkReading(snapshot, address, ethernet)


def start_query(work: Callable[[], None]) -> None:
    Thread(target=work, name="PyCab Wi-Fi query", daemon=True).start()


class NetworkMonitor(QObject):
    """Share one query across visible Admin panels, ignoring stale completions."""

    changed = Signal()
    sampleReady = Signal(int, object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        query: Callable[[], NetworkReading] | None = None,
        submit: Callable[[Callable[[], None]], None] = start_query,
    ) -> None:
        super().__init__(parent)
        wifi = WiFiInfo()
        self._query = query if query is not None else lambda: read_network(wifi)
        self._submit = submit
        self._owners: set[object] = set()
        self._closed = Event()
        self._pending = False
        self._generation = 0
        self._reading = NetworkReading().as_map()
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self.refresh)
        self.sampleReady.connect(self._apply, Qt.ConnectionType.QueuedConnection)

    @Property("QVariantMap", notify=changed)
    def reading(self) -> dict:
        return dict(self._reading)

    def set_active(self, owner: object, active: bool) -> None:
        if self._closed.is_set():
            return
        if active:
            first = not self._owners
            self._owners.add(owner)
            if first:
                self._timer.start()
                self.refresh()
        else:
            self._owners.discard(owner)
            if not self._owners:
                self._timer.stop()
                self._generation += 1

    @Slot()
    def refresh(self) -> None:
        if self._closed.is_set() or not self._owners or self._pending:
            return
        self._pending = True
        generation = self._generation

        def work() -> None:
            try:
                reading = self._query()
            except Exception as exc:
                log.debug("Local network information unavailable: %s", exc)
                reading = NetworkReading()
            if not self._closed.is_set():
                try:
                    self.sampleReady.emit(generation, reading)
                except RuntimeError:
                    # The Qt owner may already be destroyed during application shutdown.
                    log.debug("Discarding Wi-Fi result after Qt shutdown")

        try:
            self._submit(work)
        except Exception:
            self._pending = False
            log.warning("Unable to start local network query", exc_info=True)

    @Slot(int, object)
    def _apply(self, generation: int, reading: NetworkReading) -> None:
        self._pending = False
        if self._closed.is_set() or not self._owners:
            return
        if generation != self._generation:
            self.refresh()
            return
        updated = reading.as_map()
        if updated != self._reading:
            self._reading = updated
            self.changed.emit()

    def close(self) -> None:
        """Stop scheduling without waiting on an external command or worker."""
        self._closed.set()
        self._timer.stop()
        self._owners.clear()
