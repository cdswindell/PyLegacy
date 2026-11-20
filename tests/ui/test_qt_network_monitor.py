"""Verify network readings and background refresh without network hardware."""

from collections.abc import Callable
import os
from pathlib import Path
from socket import AF_INET
import subprocess
import sys
from threading import Event, get_ident
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, Qt, QTimer

from pytrain.utils.wifi_info import WiFiSnapshot
from pytrain_ui.qt import network_monitor as module
from pytrain_ui.qt.admin_controller import AdminController
from pytrain_ui.qt.network_monitor import NetworkMonitor, NetworkReading


@pytest.fixture
def app():
    return QCoreApplication.instance() or QCoreApplication([])


class PendingQueries:
    def __init__(self) -> None:
        self.jobs: list[Callable[[], None]] = []

    def submit(self, work: Callable[[], None]) -> None:
        self.jobs.append(work)

    def finish(self, app: QCoreApplication) -> None:
        self.jobs.pop(0)()
        app.processEvents()


def wifi_reading(quality: int | None = 78) -> NetworkReading:
    return NetworkReading(
        WiFiSnapshot(interface="wlan0", ssid="Layout", connected=True, quality=quality), "192.168.1.5"
    )


@pytest.mark.parametrize(
    "quality,bars,label,color",
    [
        (100, 4, "Excellent", "#36cb85"),
        (78, 4, "Very Good", "#36cb85"),
        (40, 2, "Good", "#e9ad43"),
        (20, 1, "Fair", "#e9ad43"),
        (0, 0, "Poor", "#ff656d"),
    ],
)
def test_signal_percentage_bars_and_description_agree(quality, bars, label, color):
    reading = wifi_reading(quality).as_map()
    assert reading["ssid"] == "Layout"
    assert reading["address"] == "192.168.1.5"
    assert reading["connection"] == "Wi-Fi"
    assert reading["signal"] == f"{quality}% · {label}"
    assert reading["bars"] == bars
    assert reading["color"] == color


def test_missing_signal_is_not_zero_and_rssi_uses_existing_conversion():
    unknown = wifi_reading(None).as_map()
    assert unknown["quality"] == -1
    assert unknown["signal"] == "Signal unavailable"
    assert unknown["color"] == "#9aafc2"
    rssi = NetworkReading(WiFiSnapshot(connected=True, signal_dbm=-75)).as_map()
    assert rssi["quality"] == 38


def test_disconnected_ethernet_and_unknown_readings_do_not_retain_wifi_signal():
    disconnected = NetworkReading(WiFiSnapshot(interface="wlan0", quality=90, ssid="Old layout")).as_map()
    assert disconnected["connection"] == "Wi-Fi disconnected"
    assert disconnected["ssid"] == ""
    assert disconnected["quality"] == -1
    wired = NetworkReading(address="10.0.0.2", ethernet=True).as_map()
    assert wired["connection"] == "Ethernet"
    assert not wired["wireless"]
    assert wired["signal"] == "Wired"
    assert wired["bars"] == 0
    unknown = NetworkReading().as_map()
    assert unknown["connection"] == "Network"
    assert unknown["address"] == "Unavailable"


def test_sampling_reuses_wifi_helper_and_only_confirms_physical_wired_interfaces(monkeypatch, tmp_path):
    monkeypatch.setattr(module.platform, "system", lambda: "Linux")
    helper = Mock()
    helper.query.return_value = WiFiSnapshot()
    monkeypatch.setitem(vars(module), "get_local_ipv4", lambda: "10.0.0.2")
    monkeypatch.setitem(vars(module), "Path", lambda _: tmp_path)
    monkeypatch.setattr(
        module.psutil, "net_if_addrs", lambda: {"eth0": [SimpleNamespace(family=AF_INET, address="10.0.0.2")]}
    )
    assert not module.read_network(helper).ethernet
    (tmp_path / "eth0" / "device").mkdir(parents=True)
    wired = module.read_network(helper)
    assert wired.ethernet
    assert wired.as_map()["ssid"] == "eth0"
    (tmp_path / "eth0" / "wireless").mkdir()
    assert not module.read_network(helper).ethernet
    helper.query.return_value = wifi_reading().wifi
    result = module.read_network(helper)
    assert result.wifi.ssid == "Layout"
    assert not result.ethernet
    assert helper.query.call_count == 4


@pytest.mark.parametrize("wifi_connected", [False, True])
def test_routed_ethernet_takes_precedence_over_wifi(monkeypatch, wifi_connected):
    helper = Mock()
    helper.query.return_value = WiFiSnapshot(connected=wifi_connected, ssid="Layout", quality=90)
    monkeypatch.setattr(module, "get_local_ipv4", lambda: "10.0.0.2")
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        module.psutil, "net_if_addrs", lambda: {"en7": [SimpleNamespace(family=AF_INET, address="10.0.0.2")]}
    )
    run = Mock(
        return_value=SimpleNamespace(
            returncode=0, stdout=("Hardware Port: Wi-Fi\nDevice: en0\n\nHardware Port: USB Ethernet\nDevice: en7\n")
        )
    )
    monkeypatch.setattr(module.subprocess, "run", run)
    reading = module.read_network(helper).as_map()
    assert reading["connection"] == "Ethernet"
    assert reading["signal"] == "Wired"
    assert reading["ssid"] == "USB Ethernet (en7)"
    assert not reading["wireless"]
    assert reading["quality"] == -1


@pytest.mark.parametrize("failure", [OSError("Unavailable"), subprocess.TimeoutExpired("networksetup", 3)])
def test_unavailable_hardware_information_does_not_guess_a_wired_connection(monkeypatch, failure):
    monkeypatch.setattr(module.subprocess, "run", Mock(side_effect=failure))
    assert module.macos_wired_port("en7") is None


def test_macos_wireless_port_is_not_reported_as_wired(monkeypatch):
    monkeypatch.setattr(
        module.subprocess,
        "run",
        Mock(return_value=SimpleNamespace(returncode=0, stdout="Hardware Port: Wi-Fi\nDevice: en0\n")),
    )
    assert module.macos_wired_port("en0") is None


def test_visible_panels_share_one_query_and_stop_refreshing_when_hidden(app):
    pending = PendingQueries()
    query = Mock(return_value=wifi_reading())
    monitor = NetworkMonitor(query=query, submit=pending.submit)
    left, right = object(), object()
    timer = monitor.findChild(QTimer)
    assert timer is not None
    assert timer.interval() == 5000
    try:
        monitor.refresh()
        assert not pending.jobs
        assert not timer.isActive()
        monitor.set_active(left, True)
        monitor.set_active(right, True)
        assert timer.isActive()
        monitor.set_active(left, True)
        monitor.refresh()
        assert len(pending.jobs) == 1
        assert not query.called
        pending.finish(app)
        assert monitor.reading["quality"] == 78
        monitor.set_active(left, False)
        monitor.refresh()
        assert len(pending.jobs) == 1
        pending.finish(app)
        monitor.set_active(right, False)
        assert not timer.isActive()
        monitor.refresh()
        assert not pending.jobs
        assert query.call_count == 2
    finally:
        monitor.close()


def test_stale_completion_cannot_replace_reopened_panel_reading(app):
    pending = PendingQueries()
    query = Mock(side_effect=[wifi_reading(20), wifi_reading(100)])
    monitor = NetworkMonitor(query=query, submit=pending.submit)
    owner = object()
    try:
        monitor.set_active(owner, True)
        monitor.set_active(owner, False)
        monitor.set_active(owner, True)
        pending.finish(app)
        assert monitor.reading["quality"] == -1
        assert len(pending.jobs) == 1
        pending.finish(app)
        assert monitor.reading["quality"] == 100
    finally:
        monitor.close()


def test_query_failure_clears_previous_reading_and_refresh_can_recover(app):
    pending = PendingQueries()
    query = Mock(side_effect=[wifi_reading(), OSError("No permission"), wifi_reading(40)])
    monitor = NetworkMonitor(query=query, submit=pending.submit)
    try:
        monitor.set_active(object(), True)
        pending.finish(app)
        assert monitor.reading["quality"] == 78
        monitor.refresh()
        pending.finish(app)
        assert monitor.reading["signal"] == "Signal unavailable"
        monitor.refresh()
        pending.finish(app)
        assert monitor.reading["quality"] == 40
    finally:
        monitor.close()


def test_background_results_are_applied_only_on_the_qt_owner_thread(app):
    completed = Event()
    owner_thread = get_ident()
    query_threads = []
    changed_threads = []

    def query() -> NetworkReading:
        query_threads.append(get_ident())
        return wifi_reading()

    monitor = NetworkMonitor(query=query)
    monitor.sampleReady.connect(lambda *_: completed.set(), Qt.ConnectionType.DirectConnection)
    monitor.changed.connect(lambda: changed_threads.append(get_ident()))
    try:
        monitor.set_active(object(), True)
        assert completed.wait(2)
        assert query_threads[0] != owner_thread
        assert monitor.reading["quality"] == -1
        app.processEvents()
        assert monitor.reading["quality"] == 78
        assert changed_threads == [owner_thread]
    finally:
        monitor.close()


def test_closing_does_not_wait_for_blocked_query_or_publish_its_late_result(app):
    started, release, finished = Event(), Event(), Event()

    def query() -> NetworkReading:
        started.set()
        try:
            assert release.wait(3), "Test did not release the background query"
            return wifi_reading()
        finally:
            finished.set()

    monitor = NetworkMonitor(query=query)
    changes = Mock()
    monitor.changed.connect(changes)
    try:
        monitor.set_active(object(), True)
        assert started.wait(2)
        monitor.close()
        assert not finished.is_set(), "Shutdown must not wait for a blocked query"
        release.set()
        assert finished.wait(2)
        app.processEvents()
        assert not changes.called
        monitor.refresh()
        assert monitor.reading["quality"] == -1
    finally:
        release.set()
        monitor.close()


def test_admin_panels_share_network_monitor_and_release_visibility_on_close(app):
    pending = PendingQueries()
    monitor = NetworkMonitor(query=wifi_reading, submit=pending.submit)
    left, right = AdminController(monitor), AdminController(monitor)
    try:
        assert left.network is right.network
        left.setNetworkVisible(True)
        right.setNetworkVisible(True)
        assert len(pending.jobs) == 1
        left.close()
        pending.finish(app)
        assert right.network.reading["quality"] == 78
        right.close()
        monitor.refresh()
        assert not pending.jobs
    finally:
        left.close()
        right.close()
        monitor.close()


@pytest.mark.qt_gui
def test_network_card_fits_small_screens_and_updates_without_recreation():
    qml = Path(__file__).resolve().parents[2] / "src/pytrain_ui/qt/qml/NetworkCard.qml"
    # Qt API names in the isolated scenario must retain their exact spelling.
    # noinspection SpellCheckingInspection
    source = r"""
import sys
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from pytrain_ui.qt.network_monitor import NetworkReading
from pytrain.utils.wifi_info import WiFiSnapshot

QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
engine = QQmlEngine()
component = QQmlComponent(engine, QUrl.fromLocalFile(sys.argv[1]))
assert component.isReady(), [error.toString() for error in component.errors()]
reading = NetworkReading(WiFiSnapshot(connected=True, ssid="Layout network", quality=78), "10.0.0.2").as_map()
card = component.createWithInitialProperties({"reading": reading})
assert card is not None, [error.toString() for error in component.errors()]
window = QQuickWindow()
card.setParentItem(window.contentItem())
window.show()
for width in (360, 639, 720):
    window.resize(width, 200)
    card.setWidth(width)
    card.setHeight(card.implicitHeight())
    app.processEvents()
    assert card.height() < 130
    for name in ("networkSsid", "networkSignal", "networkAddress"):
        label = card.findChild(QObject, name)
        assert label is not None
        assert label.width() >= 0
        point = label.mapToItem(card, 0, 0)
        assert point.x() >= 0 and point.y() >= 0
        assert point.x() + label.width() <= width
        assert point.y() + label.height() <= card.height()
label = card.findChild(QObject, "networkSignal")
assert label.property("text") == "78% · Very Good"
original_height = card.height()
card.setProperty("reading", NetworkReading().as_map())
app.processEvents()
assert label.property("text") == "Signal unavailable"
assert card.height() == original_height, "Connection changes must not move held Admin buttons"
assert card.findChild(QObject, "networkSignal") is label
assert card.findChild(QObject, "networkAddress").property("text") == "Local IP  Unavailable"
card.setProperty("reading", NetworkReading(address="10.0.0.2", ethernet=True, interface="eth0").as_map())
app.processEvents()
assert label.property("text") == "Wired"
assert card.findChild(QObject, "networkSsid").property("text") == "eth0"
assert card.height() == original_height
window.close()
print("NETWORK_CARD_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", source, str(qml)],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NETWORK_CARD_OK" in result.stdout
    assert "Error:" not in result.stderr, result.stderr
