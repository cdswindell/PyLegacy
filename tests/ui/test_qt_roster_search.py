"""Roster search controls edit text and select valid IDs only on release."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


# Embedded Qt API identifiers must retain their exact spelling.
# noinspection SpellCheckingInspection
SEARCH_CHILD = r"""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
engine = QQmlEngine()
maximum = int(sys.argv[2])
component = QQmlComponent(engine)
component.setData(b'''
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."
ApplicationWindow {
    id: window
    width: 639; height: 220; visible: true
    property int edits: 0
    property int selections: 0
    property int selectedId: 0
    property int underlyingClicks: 0
    MouseArea { anchors.fill: parent; onClicked: window.underlyingClicks += 1 }
    RowLayout {
        anchors.left: parent.left; anchors.right: parent.right
        anchors.top: parent.top; anchors.margins: 12
        TouchSearchField {
            id: field
            Layout.fillWidth: true
            Layout.preferredHeight: 54
            touchKeyboardEnabled: false
            onTextEdited: window.edits += 1
            onAccepted: if (setter.enabled) setter.clicked()
        }
        RosterBackspaceButton { id: backspace; field: field }
        RosterSetButton {
            id: setter
            entryText: field.text
            onClicked: { window.selectedId = Number(field.text); window.selections += 1 }
        }
    }
}
''', QUrl.fromLocalFile(str(Path(sys.argv[1]) / "roster_search_validation.qml")))
assert component.status() == QQmlComponent.Ready, [error.toString() for error in component.errors()]
created = component.create()
assert isinstance(created, QQuickWindow)
QTest.qWait(80)


def window():
    return next(surface for surface in app.allWindows() if surface.property("edits") is not None)


def value(source):
    current = window()
    expression = QQmlExpression(QQmlEngine.contextForObject(current), current, source)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result[0] if isinstance(result, tuple) else result


def point(item):
    encoded = value(
        "(function(){var b=" + item
        + ";var p=b.mapToItem(null,b.width/2,b.height/2);return JSON.stringify([p.x,p.y]);})()"
    )
    x, y = json.loads(encoded)
    return QPoint(round(x), round(y))


value("setter.maximumId=" + str(maximum))
for text in ("", "Penn", "12a", "0", "-1", "3.5", str(maximum + 1)):
    value("field.text=" + json.dumps(text))
    assert not value("setter.enabled"), "Set accepted invalid search input: " + repr(text)
for number in (1, 42, maximum):
    value("field.text='" + str(number) + "'")
    assert value("setter.enabled")
value("field.text='Penn';field.cursorPosition=4")
QTest.mouseClick(window(), Qt.LeftButton, pos=point("backspace"))
assert value("field.text") == "Pen"
assert window().property("edits") == 1
value("field.select(0,3)")
QTest.mouseClick(window(), Qt.LeftButton, pos=point("backspace"))
assert value("field.text") == ""
assert window().property("edits") == 2
assert not value("backspace.enabled")
value("field.text='Pennsylvania';field.cursorPosition=12")
position = point("backspace")
QTest.mousePress(window(), Qt.LeftButton, pos=position)
QTest.qWait(1000)
assert value("field.text") == ""
QTest.mouseRelease(window(), Qt.LeftButton, pos=position)
assert window().property("edits") == 3
value("field.text='42'")
position = point("setter")
QTest.mousePress(window(), Qt.LeftButton, pos=position)
assert window().property("selections") == 0, "Set must wait for release before switching views"
QTest.mouseRelease(window(), Qt.LeftButton, pos=position)
assert window().property("selectedId") == 42
assert window().property("selections") == 1
assert window().property("underlyingClicks") == 0
value("field.forceActiveFocus();field.text='1'")
QTest.keyClick(window(), Qt.Key_Return)
assert window().property("selectedId") == 1
assert window().property("selections") == 2
value("field.text='Penn'")
QTest.keyClick(window(), Qt.Key_Return)
assert window().property("selections") == 2
window().close()
print("ROSTER_SEARCH_OK")
"""


@pytest.mark.skipif(
    importlib.util.find_spec("PySide6") is None, reason="Install the qt-gui extra to test search controls"
)
@pytest.mark.parametrize("maximum", [98, 9999])
def test_roster_search_selects_valid_ids_on_release(maximum: int) -> None:
    qml_directory = Path(__file__).resolve().parents[2] / "src" / "pytrain_ui" / "qt" / "qml"
    result = subprocess.run(
        [sys.executable, "-c", SEARCH_CHILD, str(qml_directory), str(maximum)],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ROSTER_SEARCH_OK" in result.stdout
