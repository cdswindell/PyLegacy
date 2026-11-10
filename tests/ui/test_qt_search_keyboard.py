"""Touch search edits the roster query without selecting a component."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


# Embedded Qt API identifiers must retain their exact spelling.
# noinspection SpellCheckingInspection
KEYBOARD_CHILD = r"""
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
component = QQmlComponent(engine)
component.setData(b'''
import QtQuick
import QtQuick.Controls
import "."
ApplicationWindow {
    id: window
    width: 639; height: 800; visible: true
    property int edits: 0
    property int selections: 0
    TouchSearchField {
        id: field
        objectName: "testSearchField"
        width: parent.width; height: 60
        touchKeyboardEnabled: true
        onTextEdited: window.edits += 1
        onAccepted: window.selections += 1
    }
    function keyboardPopup() {
        for (var i = 0; i < field.data.length; ++i)
            if (field.data[i].objectName === "searchKeyboard") return field.data[i];
        return null;
    }
}
''', QUrl.fromLocalFile(str(Path(sys.argv[1]) / "search_keyboard_validation.qml")))
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


def find(predicate):
    return (
        "(function find(item){if(" + predicate
        + ")return item;for(var i=0;i<item.children.length;++i){"
        "var found=find(item.children[i]);if(found)return found;}return null;})(window.keyboardPopup().contentItem)"
    )


def button(text):
    return find("item.text==='" + text + "' && item.clicked!==undefined")


def click(item):
    encoded = value(
        "(function(){var b=" + item
        + ";var p=b.mapToItem(null,b.width/2,b.height/2);return JSON.stringify([p.x,p.y]);})()"
    )
    x, y = json.loads(encoded)
    QTest.mouseClick(window(), Qt.LeftButton, pos=QPoint(round(x), round(y)))
    QTest.qWait(30)


click("field")
assert value("window.keyboardPopup().visible"), "Tapping the field must open the keyboard"
assert value("window.keyboardPopup().height") < window().height()
for key in ("Clear", "Space", "−", "Done"):
    assert value(button(key) + ".width") >= 44, "Keyboard footer keys must remain tappable"
    assert value(button(key) + ".height") >= 44
for key in ["c", "s", "x", "1", "2"]:
    click(button(key))
assert value("field.text") == "csx12"
assert window().property("edits") == 5
click(button("⌫"))
assert value("field.text") == "csx1"
click(button("⇧"))
click(button("A"))
click(button("Space"))
click(button("−"))
assert value("field.text") == "csx1A -"
click(button("Done"))
assert not value("window.keyboardPopup().visible")
assert window().property("selections") == 0
QTest.qWait(80)
assert not value("window.keyboardPopup().visible"), "Closing must not immediately reopen the keyboard"
click("field")
click(button("Clear"))
assert value("field.text") == ""
click(button("3"))
assert value("field.text") == "3"
click(button("×"))
assert not value("window.keyboardPopup().visible")
assert window().property("selections") == 0
value("field.touchKeyboardEnabled=false")
click("field")
assert not value("window.keyboardPopup().visible"), "Desktop text entry must remain available without the popup"
window().close()
print("SEARCH_KEYBOARD_OK")
"""


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Install the qt-gui extra to test the keyboard")
def test_touch_search_keyboard_filters_without_selecting() -> None:
    qml_directory = Path(__file__).resolve().parents[2] / "src" / "pytrain_ui" / "qt" / "qml"
    result = subprocess.run(
        [sys.executable, "-c", KEYBOARD_CHILD, str(qml_directory)],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SEARCH_KEYBOARD_OK" in result.stdout
