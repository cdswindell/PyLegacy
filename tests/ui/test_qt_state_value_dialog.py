"""State editors preserve drafts, protocol capabilities, and deliberate submission."""

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
    StateValueDialog {
        id: editor
        onValueSubmitted: function(kind, value) { window.saved = value; window.commits += 1 }
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



for legacy in (True, False):
    for kind, current, choice, expected in (("Mom", 6, "High", 7), ("Smoke", 1, "Off", 0), ("Brake", 4, None, 2)):
        if kind == "Brake" and not legacy:
            continue
        def open_editor(current_value=current):
            value("editor.openFor('" + kind + "'," + str(legacy).lower() + "," + str(current_value) + ",'ENGINE 31')")
            QTest.qWait(30)
        before = window().property("commits")
        open_editor()
        assert value("editor.draftValue") == current
        assert value("editor.currentText") != "Not reported"
        assert value("editor.sliderAvailable") == (kind == "Brake" or (kind == "Mom" and legacy))
        cancel_point, set_point = point(button("Cancel")), point(button("Set"))
        assert set_point.x() - cancel_point.x() > 180
        assert abs(set_point.y() - cancel_point.y()) < 2
        if choice:
            click(choice)
        else:
            value("editor.draftValue=2")
        assert window().property("commits") == before
        click("Cancel")
        assert not value("editor.visible")
        assert window().property("commits") == before
        open_editor()
        if choice:
            click(choice)
        else:
            value("editor.draftValue=2")
        position = point(button("Set"))
        QTest.mousePress(window(), Qt.LeftButton, pos=position)
        assert value("editor.visible")
        assert window().property("commits") == before
        QTest.mouseRelease(window(), Qt.LeftButton, pos=position)
        QTest.qWait(30)
        assert not value("editor.visible")
        assert window().property("saved") == expected
        assert window().property("commits") == before + 1
        assert window().property("underlyingClicks") == 0
        open_editor("null")
        assert value("editor.currentText") == "Not reported"
        assert not value(button("Set") + ".enabled")
        click("Cancel")
window().close()
print("STATE_DIALOG_OK")
"""


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Install the qt-gui extra to test the dialog")
def test_state_dialog_drafts_and_submission() -> None:
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    qml_directory = Path(__file__).resolve().parents[2] / "src" / "pytrain_ui" / "qt" / "qml"
    result = subprocess.run(
        [sys.executable, "-c", DIALOG_CHILD, str(qml_directory)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STATE_DIALOG_OK" in result.stdout
