"""A keypad click must finish before the popup closes or a selection changes."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


# Embedded Qt API identifiers must retain their exact spelling.
# noinspection SpellCheckingInspection
POINTER_CHILD = r"""
from pathlib import Path
import sys

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
engine = QQmlEngine()
source = b'''
import QtQuick
import QtQuick.Controls
import "."
ApplicationWindow {
    id: window
    width: 720; height: 900; visible: true
    property int selectedId: 0
    property int submissions: 0
    property int programmedId: 0
    property int underlyingClicks: 0
    property bool keypadVisible: keypad.visible
    MouseArea { anchors.fill: parent; onClicked: window.underlyingClicks += 1 }
    TmccKeypad {
        id: keypad
        title: "Engine TMCC ID"
        maximumId: 9999
        showSetAddress: true
        onSetAddressRequested: function(tmccId) { window.programmedId = tmccId; close() }
        onSubmitted: function(tmccId) {
            window.selectedId = tmccId
            window.submissions += 1
            close()
        }
    }
    Component.onCompleted: keypad.openFor("")
}
'''
component = QQmlComponent(engine)
component.setData(source, QUrl.fromLocalFile(str(Path(sys.argv[1]) / "pointer_validation.qml")))
assert component.status() == QQmlComponent.Ready, [error.toString() for error in component.errors()]
window = component.create()
assert isinstance(window, QQuickWindow)
window.requestActivate()
QTest.qWait(80)

def items(parent):
    yield parent
    for child in parent.childItems():
        yield from items(child)

def root_window():
    return next(surface for surface in app.allWindows() if surface.property("selectedId") is not None)

def key(label):
    for surface in app.allWindows():
        if not hasattr(surface, "contentItem"):
            continue
        for item in items(surface.contentItem()):
            if (item.isVisible() and item.property("text") == label
                    and item.metaObject().indexOfSignal("clicked()") >= 0):
                return item
    raise AssertionError("Missing keypad key: " + label)

def click(item):
    surface = item.window()
    position = item.mapToScene(item.boundingRect().center()).toPoint()
    QTest.mousePress(surface, Qt.LeftButton, pos=position)
    QTest.qWait(30)
    QTest.mouseRelease(surface, Qt.LeftButton, pos=position)
    QTest.qWait(30)

for digit in "3233":
    click(key(digit))
assert root_window().property("selectedId") == 0
action = sys.argv[2]
label = {"submit": "↵", "close": "Close", "program": "Set Address"}[action]
button = key(label)
surface = button.window()
position = button.mapToScene(button.boundingRect().center()).toPoint()
QTest.mousePress(surface, Qt.LeftButton, pos=position)
QTest.qWait(80)
assert root_window().property("keypadVisible"), "Keypad closed before the click was released"
assert root_window().property("selectedId") == 0, "Selection changed while Enter was still held"
assert root_window().property("programmedId") == 0
QTest.mouseRelease(surface, Qt.LeftButton, pos=position)
QTest.qWait(80)
assert not root_window().property("keypadVisible")
assert root_window().property("selectedId") == (3233 if sys.argv[2] == "submit" else 0)
assert root_window().property("submissions") == (1 if sys.argv[2] == "submit" else 0)
assert root_window().property("programmedId") == (3233 if action == "program" else 0)
assert root_window().property("underlyingClicks") == 0, "Keypad click reached the row underneath"
root_window().close()
print("KEYPAD_POINTER_OK")
"""


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Install the qt-gui extra to test pointer input"
)
@pytest.mark.parametrize("action", ["submit", "close", "program"])
def test_keypad_click_finishes_before_selection_or_close(action: str) -> None:
    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    qml_directory = Path(__file__).resolve().parents[2] / "src" / "pytrain_ui" / "qt" / "qml"
    result = subprocess.run(
        [sys.executable, "-c", POINTER_CHILD, str(qml_directory), action],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "KEYPAD_POINTER_OK" in result.stdout
