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
    return find("item.text==='" + label + "' && item.clicked!==undefined && item.visible")


def click(label):
    QTest.mouseClick(window(), Qt.LeftButton, pos=point(button(label)))
    QTest.qWait(30)



for legacy in (True, False):
    for kind, current in (("Mom", 6), ("Smoke", 1), ("Brake", 4), ("Effort", 12), ("RPM", 3)):
        if kind in ("Brake", "Effort", "RPM") and not legacy:
            continue
        def open_editor(current_value=current):
            value("editor.openFor('" + kind + "'," + str(legacy).lower() + "," + str(current_value) + ",'ENGINE 31',5)")
            QTest.qWait(30)
        before = window().property("commits")
        open_editor()
        assert value("editor.draftValue") == current
        assert value("editor.currentText") != "Not reported"
        assert value("editor.sliderAvailable") == (kind in ("Brake", "Effort", "RPM") or (kind == "Mom" and legacy))
        if kind == "Mom":
            assert value(button("Set") + " === null")
            for count, (label, expected) in enumerate(
                (("Low", 0), ("Medium", 2 if legacy else 3), ("High", 7)), start=1
            ):
                slider = named("stateValueSlider")
                assert value(slider + ".value") == 5
                if legacy:
                    value(slider + ".value=2")
                    assert window().property("commits") == before + count - 1
                click(label)
                assert not value("editor.visible")
                assert window().property("saved") == expected
                assert window().property("commits") == before + count
                open_editor()
            click("Cancel")
            assert window().property("underlyingClicks") == 0
            continue
        if kind == "Smoke":
            assert value(button("Set") + " === null")
            click("Cancel")
            assert not value("editor.visible")
            assert window().property("commits") == before
            for level, label in enumerate(("Off", "Low", "Medium", "High") if legacy else ("Off", "On")):
                open_editor()
                click(label)
                assert not value("editor.visible")
                assert window().property("saved") == level
                assert window().property("commits") == before + level + 1
            assert window().property("underlyingClicks") == 0
            continue
        slider = named("stateValueSlider")
        assert value(slider + ".value") == current
        assert value(slider + ".from") == 0
        assert value(slider + ".to") == (31 if kind == "Effort" else 7)
        reset_label = "Off" if kind == "Brake" else "Default"
        labels = (reset_label, "Cancel", "Set")
        footer = [button(label) for label in labels]
        widths = [value(item + ".width") for item in footer]
        heights = [value(item + ".height") for item in footer]
        assert max(widths) - min(widths) <= 1
        assert max(heights) - min(heights) <= 1
        points = [point(item) for item in footer]
        assert all(p.y() == points[0].y() for p in points)
        steps = [right.x() - left.x() for left, right in zip(points, points[1:])]
        assert min(steps) - widths[0] >= 20
        assert max(steps) - min(steps) <= 1
        slider_position = point(slider) + QPoint(round(value(slider + ".width") / 4), 0)
        QTest.mouseClick(window(), Qt.LeftButton, pos=slider_position)
        chosen = value(slider + ".value")
        assert chosen != current
        assert value("editor.draftValue") == chosen
        assert window().property("commits") == before
        click("Cancel")
        assert not value("editor.visible")
        assert window().property("commits") == before
        open_editor()
        slider_position = point(slider) + QPoint(round(value(slider + ".width") / 4), 0)
        QTest.mouseClick(window(), Qt.LeftButton, pos=slider_position)
        chosen = value(slider + ".value")
        assert chosen != current
        assert value("editor.draftValue") == chosen
        position = point(button("Set"))
        QTest.mousePress(window(), Qt.LeftButton, pos=position)
        assert value("editor.visible")
        assert window().property("commits") == before
        QTest.mouseRelease(window(), Qt.LeftButton, pos=position)
        QTest.qWait(30)
        assert not value("editor.visible")
        assert window().property("saved") == chosen
        assert window().property("commits") == before + 1
        assert window().property("underlyingClicks") == 0
        open_editor("null")
        assert value("editor.currentText") == "Not reported"
        assert not value(button("Set") + ".enabled")
        click("Cancel")
        open_editor()
        click(reset_label)
        assert not value("editor.visible")
        assert window().property("saved") == (12 if kind == "Effort" else 0)
        assert window().property("commits") == before + 2
        assert window().property("underlyingClicks") == 0
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
