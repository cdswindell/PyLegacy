"""Speed-limit editing stays local until the operator explicitly applies it."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


# Embedded Qt API identifiers must retain their exact spelling.
# noinspection SpellCheckingInspection
DIALOG_CHILD = r"""
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
import "."
ApplicationWindow {
    id: window
    width: 639; height: 800; visible: true
    property int saved: 10
    property int commits: 0
    property int clears: 0
    property int underlyingClicks: 0
    MouseArea { anchors.fill: parent; onClicked: window.underlyingClicks += 1 }
    SpeedLimitDialog {
        id: editor
        onLimitSubmitted: function(value) { window.saved = value; window.commits += 1 }
        onLimitCleared: { window.saved = 255; window.clears += 1 }
    }
}
''', QUrl.fromLocalFile(str(Path(sys.argv[1]) / "speed_limit_validation.qml")))
assert component.status() == QQmlComponent.Ready, [error.toString() for error in component.errors()]
created = component.create()
assert isinstance(created, QQuickWindow)
QTest.qWait(80)


def window():
    return next(surface for surface in app.allWindows() if surface.property("saved") is not None)


def value(source):
    current = window()
    expression = QQmlExpression(QQmlEngine.contextForObject(current), current, source)
    result = expression.evaluate()
    assert not expression.hasError(), expression.error().toString()
    return result[0] if isinstance(result, tuple) else result


def named(name):
    return find("item.objectName==='" + name + "'")


def find(predicate):
    return (
        "(function find(item){if(" + predicate
        + ")return item;for(var i=0;i<item.children.length;++i){"
        "var found=find(item.children[i]);if(found)return found;}return null;})(editor.contentItem)"
    )


def point(item):
    encoded = value(
        "(function(){var b=" + item
        + ";var p=b.mapToItem(null,b.width/2,b.height/2);return JSON.stringify({x:p.x,y:p.y});})()"
    )
    coordinates = json.loads(encoded)
    return QPoint(round(coordinates["x"]), round(coordinates["y"]))


def button(label):
    return find("item.text==='" + label + "' && item.clicked!==undefined")


def click(label):
    QTest.mouseClick(window(), Qt.LeftButton, pos=point(button(label)))
    QTest.qWait(30)


def open_editor():
    value("editor.openFor(10," + str(maximum) + ",'ENGINE 31')")
    QTest.qWait(40)
    assert value("editor.visible")
    assert value("editor.height") <= window().height() - 24
    assert value("editor.entryText") == "10"
    assert value(button("Clear") + ".enabled")
    assert value(button("Set") + ".enabled")
    zero_position, set_position = point(button("0")), point(button("Set"))
    assert set_position.y() == zero_position.y()
    assert set_position.x() > zero_position.x()
    assert value(named("speedLimitSlider") + ".to") == maximum
    protocol = "TMCC" if maximum == 31 else "Legacy"
    assert value(named("speedLimitRange") + ".text") == protocol + " speed limit: 1–" + str(maximum)


target = 57 if maximum == 199 else 25
open_editor()
for digit in str(target):
    click(digit)
assert value("editor.entryText") == str(target)
assert value(named("speedLimitSlider") + ".value") == target
assert window().property("commits") == 0
assert window().property("saved") == 10
click("Close")
assert not value("editor.visible")
assert window().property("saved") == 10

open_editor()
for digit in str(target):
    QTest.keyClick(window(), Qt.Key(ord(digit)))
QTest.qWait(30)
assert value("editor.entryText") == str(target)
assert value(named("speedLimitSlider") + ".value") == target
position = point(button("Set"))
QTest.mousePress(window(), Qt.LeftButton, pos=position)
QTest.qWait(30)
assert value("editor.visible"), "The dialog must not close before pointer release"
assert window().property("commits") == 0
QTest.mouseRelease(window(), Qt.LeftButton, pos=position)
QTest.qWait(30)
assert not value("editor.visible")
assert window().property("saved") == target
assert window().property("commits") == 1
assert window().property("underlyingClicks") == 0

open_editor()
value("editor.entryText='" + str(maximum + 1) + "'")
assert not value("editor.acceptableInput")
assert not value(button("Set") + ".enabled")
value("editor.commit()")
assert value("editor.visible")
assert window().property("commits") == 1
click("Close")

open_editor()
for digit in str(target):
    click(digit)
click("⌫")
assert value("editor.entryText") == str(target)[:-1]
assert value(named("speedLimitSlider") + ".value") == int(str(target)[:-1])
slider = named("speedLimitSlider")
encoded = value(
    "(function(){var s=" + slider
    + ";var p=s.mapToItem(null,s.width*0.75,s.height/2);return JSON.stringify({x:p.x,y:p.y});})()"
)
coordinates = json.loads(encoded)
QTest.mouseClick(window(), Qt.LeftButton, pos=QPoint(round(coordinates["x"]), round(coordinates["y"])))
QTest.qWait(30)
assert int(value("editor.entryText")) == round(value(slider + ".value"))
assert int(value("editor.entryText")) > 10
assert window().property("commits") == 1
click("Close")

open_editor()
value("editor.entryText='" + str(maximum + 1) + "'")
assert not value("editor.acceptableInput")
position = point(button("Clear"))
QTest.mousePress(window(), Qt.LeftButton, pos=position)
QTest.qWait(30)
assert value("editor.visible"), "Clear must wait for pointer release"
assert window().property("clears") == 0
QTest.mouseRelease(window(), Qt.LeftButton, pos=position)
QTest.qWait(30)
assert not value("editor.visible"), "Clear must close the dialog"
assert window().property("clears") == 1
assert window().property("saved") == 255
assert window().property("commits") == 1
assert window().property("underlyingClicks") == 0

for no_limit in (0, 255):
    value("editor.openFor(" + str(no_limit) + "," + str(maximum) + ",'ENGINE 31')")
    QTest.qWait(40)
    assert value("editor.entryText") == ""
    assert not value(button("Clear") + ".enabled")
    assert not value(button("Set") + ".enabled")
    click("Clear")
    click("Set")
    QTest.keyClick(window(), Qt.Key_Return)
    assert value("editor.visible")
    assert window().property("clears") == 1
    assert window().property("commits") == 1
    click("1")
    assert value(button("Set") + ".enabled")
    assert not value(button("Clear") + ".enabled")
    click("⌫")
    assert not value(button("Set") + ".enabled")
    click("Close")

open_editor()
value("editor.entryText='0'")
assert not value(button("Set") + ".enabled")
value("editor.entryText='" + str(maximum) + "'")
assert value(button("Set") + ".enabled")
value("editor.entryText=''")
assert not value(button("Set") + ".enabled")
assert value(button("Clear") + ".enabled")
click("Close")

open_editor()
for digit in str(target):
    click(digit)
click("Set")
assert window().property("saved") == target
assert window().property("commits") == 2
assert not value("editor.visible")
assert window().property("underlyingClicks") == 0
window().close()
print("SPEED_LIMIT_DIALOG_OK")
"""


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Install the qt-gui extra to test the dialog")
@pytest.mark.parametrize("maximum", [31, 199])
def test_speed_limit_dialog_commits_on_set_or_clear(maximum: int) -> None:
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    qml_directory = Path(__file__).resolve().parents[2] / "src" / "pytrain_ui" / "qt" / "qml"
    result = subprocess.run(
        [sys.executable, "-c", DIALOG_CHILD, str(qml_directory), str(maximum)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SPEED_LIMIT_DIALOG_OK" in result.stdout
