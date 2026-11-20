"""The Qt state bridge coalesces changes without filling Qt's delivery queue."""

import os
import subprocess
import sys

import pytest


# Embedded Qt API identifiers must retain their exact spelling.
# noinspection SpellCheckingInspection
BRIDGE_CHILD = r"""
from threading import enumerate as threads, get_ident
from types import SimpleNamespace
from time import monotonic, sleep

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest
from pytrain.db.state_changes import StateChange, StateChangeHub
from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt.state_change_bridge import QtStateChangeBridge

app = QCoreApplication([])
hub = StateChangeHub()
bridge = QtStateChangeBridge({CommandScope.SWITCH, CommandScope.ROUTE}, hub=hub)
received = []
owner_thread = get_ident()


def receive(changes):
    assert get_ident() == owner_thread, "GUI consumers must run on the Qt owner thread"
    received.append(changes)


bridge.changesReady.connect(receive)


def wait_for(predicate):
    deadline = monotonic() + 2
    while not predicate() and monotonic() < deadline:
        app.processEvents()
        sleep(0.005)
    assert predicate()


for _ in range(1000):
    for address in range(1, 9):
        hub.publish(CommandScope.SWITCH, address)
    hub.publish(CommandScope.ROUTE, 7)
    hub.publish(CommandScope.ENGINE, 2)
wait_for(lambda: len(received) == 1)
assert received == [{*(StateChange(CommandScope.SWITCH, address) for address in range(1, 9)),
                     StateChange(CommandScope.ROUTE, 7)}], received
assert len([thread for thread in threads() if thread.name == "PyCab state changes"]) == 1
bridge.receiveRecordChange(SimpleNamespace(scope=CommandScope.SWITCH, tmcc_id=9))
wait_for(lambda: len(received) == 2)
assert received[-1] == {StateChange(CommandScope.SWITCH, 9)}, received
count = len(received)
hub.publish(CommandScope.SWITCH, 10)
bridge.close()
bridge.close()
bridge.receiveRecordChange(SimpleNamespace(scope=CommandScope.SWITCH, tmcc_id=11))
for _ in range(50):
    QTest.qWait(10)
    if not any(thread.name == "PyCab state changes" for thread in threads()):
        break
assert not any(thread.name == "PyCab state changes" for thread in threads())
assert len(received) == count, "Queued deliveries must be discarded after close"
fresh = hub.subscribe({CommandScope.SWITCH})
assert fresh.pending_count == 0, "No notifications may be retained globally"
fresh.close()
print("STATE_BRIDGE_OK")
"""


@pytest.mark.qt_gui
def test_qt_bridge_coalesces_delivers_on_owner_thread_and_closes_without_backlog() -> None:
    pytest.importorskip("PySide6")
    result = subprocess.run(
        [sys.executable, "-c", BRIDGE_CHILD],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STATE_BRIDGE_OK" in result.stdout
