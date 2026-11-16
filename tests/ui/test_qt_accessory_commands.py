import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtCore")

from pytrain.db.component_state import ComponentStateDict
from pytrain.gui.controller.lcs_device_registry import ASC2
from pytrain.gui.controller.lcs_id_map import LcsOccupant
from pytrain.pdi.constants import Amc2Action, Asc2Action, Bpc2Action, IrdaAction, PdiCommand
from pytrain.pdi.irda_req import IrdaSequence
from pytrain.pdi.pdi_req import PdiReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from pytrain_ui.qt import accessory_controller as module
from pytrain_ui.qt.accessory_controller import AccessoryCatalogController, AccessoryDescriptor, AccessoryViewKind


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.setattr(module.ConfiguredAccessorySet, "from_file", lambda: SimpleNamespace(configured_all=list))
    monkeypatch.setattr(module.ComponentStateStore, "get", lambda: SimpleNamespace(get_all=lambda _scope: []))
    monkeypatch.setattr(module.ComponentStateStore, "get_state", lambda *_args, **_kwargs: None)
    monkeypatch.setitem(vars(module), "occupants_of", lambda *_args, **_kwargs: [])
    monkeypatch.setitem(vars(module), "occupants", lambda *_args, **_kwargs: [])
    catalog = AccessoryCatalogController()
    yield catalog
    catalog.close()


@pytest.fixture
def sent(monkeypatch):
    requests = []

    def capture(packet):
        requests.append(packet)

    monkeypatch.setattr(PdiReq, "send", capture)
    monkeypatch.setattr(CommandReq, "send", capture)
    return requests


def occupy(monkeypatch, *devices):
    occupants = [
        SimpleNamespace(device=SimpleNamespace(label=kind, key=kind), mode=SimpleNamespace(key=mode))
        for kind, mode in devices
    ]
    monkeypatch.setitem(vars(module), "occupants_of", lambda address, **_kwargs: occupants if address == 24 else [])


def test_colocated_bpc2_and_asc2_send_to_the_selected_device(controller, sent, monkeypatch):
    occupy(monkeypatch, ("BPC2", "acc_8"), ("ASC2", "acc_8"))
    controller.quickAction("ON", 24, "BPC2")
    controller.quickAction("OFF", 24, "BPC2")
    controller.quickAction("ON", 24, "ASC2")
    controller.quickAction("OFF", 24, "ASC2")
    assert [(req.tmcc_id, req.pdi_command, req.action, req.state) for req in sent] == [
        (24, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, 1),
        (24, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, 0),
        (24, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, 1),
        (24, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, 0),
    ]


def test_asc2_release_reaches_original_address_after_discovery_changes(controller, sent, monkeypatch):
    occupy(monkeypatch, ("ASC2", "acc_8"))
    controller.holdQuickAction(24, True)
    controller.holdQuickAction(24, True)
    occupy(monkeypatch)
    controller.holdQuickAction(25, False)
    controller.holdQuickAction(24, False)
    controller.holdQuickAction(24, False)
    assert [(req.tmcc_id, req.action, req.values, req.time) for req in sent] == [
        (24, Asc2Action.CONTROL1, 1, 0),
        (24, Asc2Action.CONTROL1, 0, 0),
    ]


@pytest.mark.parametrize("kind,mode", [("ASC2", "acc_1"), ("BPC2", "acc_8")])
def test_momentary_is_unavailable_on_uncoupling_asc2_and_bpc2(controller, sent, monkeypatch, kind, mode):
    occupy(monkeypatch, (kind, mode))
    controller.holdQuickAction(24, True)
    controller.holdQuickAction(24, False)
    controller.quickAction("MOMENTARY", 24, kind)
    if kind == "ASC2":
        controller.quickAction("ON", 24, kind)
    assert sent == []


def add_descriptor(controller, monkeypatch, kind):
    scope_key = "irda:24" if kind == "SENSOR" else "acc:24"
    labels = () if kind == "TMCC" else (f"{kind} 24",)
    preferred = AccessoryViewKind.GENERIC if kind == "TMCC" else AccessoryViewKind.LCS
    descriptor = AccessoryDescriptor(scope_key, (24,), 24, kind, "", None, labels, (preferred,), preferred, True)

    # Supply a discovered descriptor to exercise the same slots that QML invokes.
    # noinspection PyProtectedMember
    monkeypatch.setitem(controller._descriptors, scope_key, descriptor)
    return scope_key


def test_tmcc_keypad_and_relative_speed_target_the_selected_address(controller, sent, monkeypatch):
    key = add_descriptor(controller, monkeypatch, "TMCC")
    controller.tmccCommand(key, 24, "NUMERIC", 9)
    controller.tmccCommand(key, 24, "RELATIVE_SPEED", -5)
    controller.tmccCommand(key, 24, "RELATIVE_SPEED", 0)
    controller.tmccCommand(key, 24, "BOOST", 0)
    controller.tmccCommand(key, 25, "BRAKE", 0)
    controller.tmccCommand(key, 24, "RELATIVE_SPEED", 6)
    assert [(req.address, req.command, req.data) for req in sent] == [
        (24, TMCC1AuxCommandEnum.NUMERIC, 9),
        (24, TMCC1AuxCommandEnum.RELATIVE_SPEED, -5),
        (24, TMCC1AuxCommandEnum.RELATIVE_SPEED, 0),
        (24, TMCC1AuxCommandEnum.BOOST, 0),
    ]


def test_sensor_sequence_targets_the_irda_device(controller, sent, monkeypatch):
    key = add_descriptor(controller, monkeypatch, "SENSOR")
    controller.setSensorSequence(key, 9)
    controller.setSensorSequence(key, 100)
    assert len(sent) == 1
    request = sent[0]
    assert (request.tmcc_id, request.pdi_command, request.action, request.sequence) == (
        24,
        PdiCommand.IRDA_SET,
        IrdaAction.SEQUENCE,
        IrdaSequence(9),
    )


def test_amc2_motor_and_lamp_target_the_selected_outputs(controller, sent, monkeypatch):
    key = add_descriptor(controller, monkeypatch, "AMC2")
    controller.setAmc2Output(key, True, 2, 35)
    controller.setAmc2Output(key, False, 4, 45)
    controller.setAmc2Output(key, True, 3, 50)
    motor, select_motor, power_motor, lamp, select_lamp = sent
    assert (motor.tmcc_id, motor.action, motor.motor, motor.speed) == (24, Amc2Action.MOTOR, 2, 35)
    assert (lamp.tmcc_id, lamp.action, lamp.lamp, lamp.level) == (24, Amc2Action.LAMP, 4, 45)
    assert [(req.command, req.data) for req in (select_motor, power_motor, select_lamp)] == [
        (TMCC1AuxCommandEnum.NUMERIC, 2),
        (TMCC1AuxCommandEnum.AUX1_OPT_ONE, 0),
        (TMCC1AuxCommandEnum.NUMERIC, 6),
    ]


def test_switch_mode_is_excluded_from_accessory_rows_and_mixed_ports_are_discoverable(controller, monkeypatch):
    mixed = LcsOccupant(24, ASC2, ASC2.mode_for_pdi_mode(0), 8, scope=CommandScope.ACC)
    switch = LcsOccupant(40, ASC2, ASC2.mode_for_pdi_mode(3), 4, scope=CommandScope.ACC)
    acc_states = ComponentStateDict(CommandScope.ACC)
    acc_records = [acc_states[address] for address in (40, 41, 55)]

    def get_all(scope):
        return acc_records if scope == CommandScope.ACC else []

    monkeypatch.setattr(module.ComponentStateStore, "get", lambda: SimpleNamespace(get_all=get_all))
    monkeypatch.setitem(vars(module), "occupants", lambda scope: [mixed] if scope == CommandScope.ACC else [switch])
    monkeypatch.setitem(
        vars(module), "occupants_of", lambda address, **_kwargs: [mixed.at(address)] if mixed.claims(address) else []
    )

    controller.reload()
    rows = {row["primaryTmccId"]: row for row in controller.rows}
    assert set(rows) == {*range(24, 32), 55}
    assert rows[55]["kind"] == "TMCC"
    assert rows[31]["kind"] == "ASC2"
    assert [(action["label"], action["selected"]) for action in rows[31]["quickActions"]] == [
        ("On", False),
        ("Off", False),
        ("Hold", False),
    ]


# The embedded Qt API identifiers retain their exact spelling.
# noinspection SpellCheckingInspection
ROSTER_CHILD = r"""
from pathlib import Path
import sys

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
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
    id: win
    width: 639
    height: 800
    visible: true
    property string calls: ""
    property bool cover: false
    property string relayFilter: ""
    property int feedbackRevision: 0
    property var missingKinds: []
    readonly property string filterKeys: roster.typeFilters.map(filter => filter.key).join(",")
    readonly property string selectedFilter: roster.typeFilter
    QtObject {
        id: backend
        readonly property var rows: ["OPERATING", "BPC2", "ASC2", "AMC2", "SENSOR", "TMCC"].map((kind, index) => ({
            kind: kind, key: kind, primaryTmccId: index + 10, tmccIds: [index + 10],
            roadName: kind, roadNumber: "0001", lcsAssociations: "Port 1", stateSummary: "",
            userDefined: true, availableViews: [], imageSource: "",
            quickActions: kind === "BPC2" || kind === "ASC2" ? [
                {key: "ON", label: "On", selected: win.feedbackRevision > 0},
                {key: "OFF", label: "Off", selected: false}
            ] : []
        })).filter(row => !win.missingKinds.includes(row.kind))
        function holdQuickAction(address, pressed) { win.calls += address + (pressed ? "+" : "-") }
        function quickAction(action, address, kind) { win.calls += action + address + kind }
    }
    AccessoryCatalog {
        id: roster
        width: parent.width
        height: parent.height - 106
        visible: win.relayFilter.length > 0
        controller: backend
        Connections {
            target: win
            function onRelayFilterChanged() { roster.typeFilter = win.relayFilter }
        }
    }

    AccessoryOperatingView {
        width: 639; height: 800
        visible: false
        controller: backend
        accessory: ({kind: "TMCC", key: "acc:24", tmccId: 24, title: "Test Accessory"})
    }

    AccessoryActionButton {
        width: 180; height: 60
        objectName: "momentary"
        controller: backend
        tmccId: 24
        deviceKind: "ASC2"
        action: "HOLD"
        enabled: !win.cover
    }
    component PowerButton: AccessoryActionButton {
        width: 110; height: 60
        controller: backend
    }
    PowerButton { objectName: "ON24ASC2"; x: 185; tmccId: 24; deviceKind: "ASC2"; action: "ON" }
    PowerButton { objectName: "OFF24ASC2"; x: 305; tmccId: 24; deviceKind: "ASC2"; action: "OFF" }
    PowerButton { objectName: "ON42BPC2"; x: 425; tmccId: 42; deviceKind: "BPC2"; action: "ON" }
    PowerButton { objectName: "OFF42BPC2"; x: 525; tmccId: 42; deviceKind: "BPC2"; action: "OFF" }
    Component.onCompleted: {
        const expected = {
            All: "AMC2,ASC2,BPC2,OPERATING,SENSOR,TMCC",
            Operating: "OPERATING", LCS: "AMC2,ASC2,BPC2,SENSOR", TMCC: "TMCC",
            Sensor: "SENSOR", BPC2: "BPC2", ASC2: "ASC2", AMC2: "AMC2"
        }
        for (const label of Object.keys(expected)) {
            roster.typeFilter = label.toUpperCase()
            const actual = roster.visibleRows().map(row => row.kind).join(",")
            if (actual !== expected[label])
                throw new Error(label + " filter returned " + actual)
        }
        roster.typeFilter = "ALL"
        roster.searchText = "13"
        if (roster.visibleRows()[0].kind !== "AMC2")
            throw new Error("Address search did not find AMC2")
        roster.searchText = ""
        roster.sortMode = "TMCC"
        if (roster.visibleRows()[0].primaryTmccId !== 10)
            throw new Error("Address sort failed")
    }
}
''', QUrl.fromLocalFile(str(Path(sys.argv[1]) / "accessory_validation.qml")))
assert component.isReady(), [error.toString() for error in component.errors()]
window = component.create()
assert isinstance(window, QQuickWindow)
window.requestActivate()
QTest.qWait(100)
button = window.findChild(QQuickItem, "momentary")
assert button is not None
point = button.mapToScene(button.boundingRect().center()).toPoint()

QTest.mousePress(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+", "Hold must energize the port on press"
QTest.mouseRelease(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+24-", "Even a short press must release the port"

window.setProperty("calls", "")
QTest.mousePress(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+"
QTest.mouseMove(window, point + QPoint(0, 120))
assert window.property("calls") == "24+24-", "Dragging off Hold must release the port"
QTest.mouseRelease(window, Qt.LeftButton, pos=point + QPoint(0, 120))
assert window.property("calls") == "24+24-"

window.setProperty("calls", "")
QTest.mousePress(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+"
window.setProperty("cover", True)
QTest.mouseRelease(window, Qt.LeftButton, pos=point)
assert window.property("calls") == "24+24-", "Covering the roster must release the port once"

for expected in ("ON24ASC2", "OFF24ASC2", "ON42BPC2", "OFF42BPC2"):
    window.setProperty("calls", "")
    action_button = window.findChild(QQuickItem, expected)
    assert action_button is not None
    position = action_button.mapToScene(action_button.boundingRect().center()).toPoint()
    QTest.mousePress(window, Qt.LeftButton, pos=position)
    assert window.property("calls") == ""
    QTest.mouseRelease(window, Qt.LeftButton, pos=position)
    assert window.property("calls") == expected

def descendants(parent):
    for child in parent.childItems():
        yield child
        yield from descendants(child)

for kind, address in (("ASC2", 12), ("BPC2", 11)):
    window.setProperty("relayFilter", kind)
    QTest.qWait(80)
    viewport = window.findChild(QQuickItem, "accessoryRoster")
    assert viewport is not None
    on = next(item for item in descendants(viewport) if item.property("action") == "ON")
    position = on.mapToScene(on.boundingRect().center())
    assert viewport.contains(viewport.mapFromScene(position)), "The first relay row must fit inside the compact list"
    window.setProperty("calls", "")
    QTest.mousePress(window, Qt.LeftButton, pos=position.toPoint())
    window.setProperty("feedbackRevision", window.property("feedbackRevision") + 1)
    QTest.qWait(35)
    assert not window.property("calls")
    QTest.mouseRelease(window, Qt.LeftButton, pos=position.toPoint())
    assert window.property("calls") == f"ON{address}{kind}", "Feedback must preserve the in-progress relay click"

assert window.property("filterKeys") == "ALL,OPERATING,LCS,TMCC,SENSOR,BPC2,ASC2,AMC2"
window.setProperty("missingKinds", ["BPC2", "OPERATING", "SENSOR"])
QTest.qWait(35)
assert window.property("filterKeys") == "ALL,LCS,TMCC,ASC2,AMC2"
assert window.property("selectedFilter") == "ALL"

window.setProperty("missingKinds", ["BPC2", "ASC2", "AMC2", "SENSOR"])
QTest.qWait(35)
assert window.property("filterKeys") == "ALL,OPERATING,TMCC"
window.setProperty("missingKinds", ["BPC2", "ASC2", "AMC2", "SENSOR", "OPERATING"])
QTest.qWait(35)
assert window.property("filterKeys") == "ALL,TMCC"

window.close()
"""


def test_roster_filters_and_momentary_pointer_behavior() -> None:
    qml_directory = Path(__file__).resolve().parents[2] / "src" / "pytrain_ui" / "qt" / "qml"
    environment = dict(os.environ)
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-c", ROSTER_CHILD, str(qml_directory)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Error:" not in result.stderr, result.stderr
