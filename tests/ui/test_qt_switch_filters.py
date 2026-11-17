"""Exercise switch state filters and switch/route badge feedback in the real cab."""

import os
import subprocess
import sys
from unittest.mock import Mock

import pytest


# Embedded Qt API identifiers must retain their exact spelling.
# noinspection SpellCheckingInspection
FILTER_CHILD = r"""
import json
import sys
import traceback
from unittest.mock import Mock, patch

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine, QQmlExpression
from PySide6.QtTest import QTest
from pytrain.db.comp_data import RouteData
from pytrain.db.components import RouteComponent
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.pdi.base_req import BaseReq
from pytrain.pdi.constants import PdiCommand
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum
from pytrain_ui.qt.app import run_cab

store = ComponentStateStore.build()
engine = store.get_state(CommandScope.ENGINE, 1)
engine.initialize(CommandScope.ENGINE, 1)
engine.comp_data.road_name = "Test engine"
engine.comp_data.control_type = 1
engine.comp_data.engine_type = 0
for address in range(1, 42):
    state = store.get_state(CommandScope.SWITCH, address)
    state.initialize(CommandScope.SWITCH, address)
    if address != 41:
        state.comp_data.road_name = f"Switch {42 - address:02d}"
        state.comp_data.road_number = f"{address:04d}"
    if address != 40:
        command = TMCC1SwitchCommandEnum.THRU if address % 2 else TMCC1SwitchCommandEnum.OUT
        state.update(CommandReq.build(command, address))
for address, source in ((1, 1), (2, 2), (3, 40)):
    data = RouteData(None, address)
    data.road_name = f"Test route {address}"
    data.components = [RouteComponent(source, 0)]
    request = BaseReq(address, PdiCommand.BASE_MEMORY, scope=CommandScope.ROUTE, data_bytes=data.as_bytes())
    store.get_state(CommandScope.ROUTE, address).update(BaseReq(request.as_bytes))
failures = []


def app_factory(argv):
    app = QGuiApplication(argv)

    def checks():
        try:
            window = next(w for w in app.allWindows() if w.property("activeScope") is not None)
            window.resize(720, 1280)

            def evaluate(source, target=window):
                if target is window:
                    target = window.property("workspace")
                    context = QQmlEngine.contextForObject(target.childItems()[0])
                else:
                    context = QQmlEngine.contextForObject(target)
                expression = QQmlExpression(context, target, source)
                result = expression.evaluate()
                assert not expression.hasError(), expression.error().toString()
                return result[0] if isinstance(result, tuple) else result

            def descendants(item):
                yield item
                for child in item.childItems():
                    yield from descendants(child)

            def visible(name):
                return next(item for item in descendants(window.contentItem())
                            if item.isVisible() and item.objectName() == name)

            def tab(label):
                return next(item for item in descendants(visible("switchFilterTabs"))
                            if item.isVisible() and item.property("text") == label
                            and item.metaObject().indexOfSignal("clicked()") >= 0)

            def click(item, fraction=0.5):
                point = item.mapToScene(QPointF(item.width() * fraction, item.height() / 2)).toPoint()
                QTest.mouseClick(window, Qt.LeftButton, pos=point)
                QTest.qWait(60)

            def ids():
                return json.loads(evaluate("JSON.stringify(switchOpsView.rosterRows.map(row => row.tmccId))"))

            def badge_colors():
                return {item.property("tmccId"): item.property("color").name()
                        for item in descendants(window.contentItem())
                        if item.isVisible() and item.objectName() == "operationsIdBadge"}

            evaluate('window.changeScope("SWITCH", false)')
            QTest.qWait(120)
            assert ids() == list(range(1, 41))
            evaluate('switchOpsView.sortKey = "roadName"')
            QTest.qWait(60)
            colors = badge_colors()
            assert colors[40] == "#18232e"
            click(tab("Thru"))
            assert set(ids()) == set(range(1, 40, 2))
            assert set(badge_colors().values()) == {"#23694c"}
            click(tab("Out"))
            assert set(ids()) == set(range(2, 40, 2))
            assert set(badge_colors().values()) == {"#4b3920"}
            evaluate('switchOpsView.sortKey = "tmccId"')
            assert ids() == list(range(2, 40, 2))
            evaluate('searchField.text = "Switch 40"', visible("operationsRoster"))
            assert ids() == [2]
            evaluate('searchField.text = ""', visible("operationsRoster"))
            evaluate('switchOpsView.showInactiveSwitches = true')
            click(tab("Thru"))
            assert 41 in ids()
            evaluate('switchOpsView.showInactiveSwitches = false')
            evaluate('searchField.text = "41";root.submitTmccId(true)', visible("operationsRoster"))
            assert ids() == [41], "Exact ID entry must bypass unnamed and state filters"
            evaluate('switchOpsView.directTmccId = 0')
            evaluate('searchField.text = ""', visible("operationsRoster"))
            click(tab("Out"))
            # Reproduce packet notification reaching Qt before the store update.
            evaluate('switchOpsController.commandReceived(2, "SWITCH")')
            QTest.qWait(60)
            assert 2 in ids()
            state = store.get_state(CommandScope.SWITCH, 2)
            state.update(CommandReq.build(TMCC1SwitchCommandEnum.THRU, 2))
            # Base state feedback need not produce a TMCC dispatcher notification.
            QTest.qWait(120)
            assert 2 not in ids(), "Authoritative state changes must update filter membership"

            roster = visible("operationsRoster")
            for gesture in ("double", "hold"):
                evaluate('positionViewAtEnd()', roster)
                QTest.qWait(100)
                assert not roster.property("atYBeginning")
                control = tab("Out")
                if gesture == "double":
                    click(control, 0.15)
                    click(control, 0.85)
                else:
                    point = control.mapToScene(control.boundingRect().center()).toPoint()
                    QTest.mousePress(window, Qt.LeftButton, pos=point)
                    QTest.qWait(1100)
                    QTest.mouseRelease(window, Qt.LeftButton, pos=point)
                QTest.qWait(100)
                assert roster.property("atYBeginning"), gesture
                assert evaluate('switchOpsView.switchStateFilter') == "OUT"

            evaluate('window.changeScope("ENGINE", false)')
            evaluate('window.changeScope("SWITCH", false)')
            QTest.qWait(100)
            assert tab("Out").property("checked")
            tabs = visible("switchFilterTabs")
            control = tab("Out")
            left = control.mapToItem(tabs, QPointF(0, 0)).x()
            assert left >= 0 and left + control.width() <= tabs.width() + 1

            store.get_state(CommandScope.SWITCH, 2).update(CommandReq.build(TMCC1SwitchCommandEnum.OUT, 2))
            evaluate('window.changeScope("ROUTE", false)')
            QTest.qWait(100)
            assert badge_colors() == {1: "#23694c", 2: "#4b3920", 3: "#18232e"}, badge_colors()
            source = store.get_state(CommandScope.SWITCH, 2)
            source.update(CommandReq.build(TMCC1SwitchCommandEnum.THRU, 2))
            QTest.qWait(120)
            assert badge_colors()[2] == "#23694c"
            evaluate('window.changeScope("SWITCH", false)')
            click(tab("All"))
            created = store.get_state(CommandScope.SWITCH, 42)
            created.initialize(CommandScope.SWITCH, 42)
            created.comp_data.road_name = "New turnout"
            created.comp_data.road_number = "0042"
            created.update(CommandReq.build(TMCC1SwitchCommandEnum.OUT, 42))
            QTest.qWait(120)
            assert 42 in ids(), "New states must enter the roster without a command broadcast"
            assert created.clear()
            QTest.qWait(120)
            assert 42 not in ids(), "Deleted states must leave the roster without a DELETE broadcast"
            from threading import enumerate as threads
            assert len([thread for thread in threads() if thread.name == "PyCab state changes"]) == 1
            assert not any("State Watcher Switch" in thread.name or "State Watcher Route" in thread.name
                           for thread in threads())
            print("STATE_FILTERS_OK")
        except Exception as error:
            traceback.print_exc()
            failures.append(error)
        finally:
            app.exit(1 if failures else 0)

    QTimer.singleShot(150, checks)
    return app


with (
    patch("PySide6.QtGui.QGuiApplication", side_effect=app_factory),
    patch("pytrain.comm.command_listener.CommandDispatcher.get", return_value=Mock()),
    patch("pytrain_ui.qt.session.restore_engine", return_value=None),
    patch("pytrain_ui.qt.session.save_engine"),
    patch("pytrain.protocol.command_req.CommandReq.send"),
    patch("pytrain.comm.comm_buffer.CommBuffer.build", return_value=Mock()),
    patch("pytrain.pdi.base_req.BaseReq.process_sync_reqs"),
):
    result = run_cab(CommandScope.ENGINE, 1, [])
sys.exit(result)
"""


# Isolate this QML scenario in its own process and retain per-test diagnostics.
# noinspection DuplicatedCode
def test_switch_filters_preserve_search_and_gestures_and_color_live_state() -> None:
    pytest.importorskip("PySide6")
    result = subprocess.run(
        [sys.executable, "-c", FILTER_CHILD],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software"),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STATE_FILTERS_OK" in result.stdout


def test_scope_invalidations_handle_replacement_creation_deleted_flags_and_close(monkeypatch) -> None:
    module = pytest.importorskip("pytrain_ui.qt.ops_controller")
    scope = module.CommandScope.SWITCH

    def switch(address, name):
        state = module.SwitchState(scope)
        state.initialize(scope, address)
        state.update(module.CommandReq.build(module.TMCC1SwitchCommandEnum.THRU, address))
        state.comp_data.road_name = name
        return state

    states = [switch(1, "First"), switch(2, "Second")]
    store = Mock()
    store.get_all.side_effect = lambda _: states
    # PyCharm cannot resolve these patch targets on the dynamically imported module.
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(module.ComponentStateStore, "get", Mock(return_value=store))
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(
        module.ComponentStateStore,
        "get_state",
        lambda _scope, address, **_: next((state for state in states if state.address == address), None),
    )
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(module.ComponentStateStore, "delete_state", lambda _: None)
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(module.CommandDispatcher, "get", Mock(return_value=Mock()))
    # noinspection PyUnresolvedReferences
    monkeypatch.setattr(module.PdiDispatcher, "is_built", lambda: False)
    controller = module.OpsController(scope)
    states[:] = [switch(1, "Replacement"), switch(3, "New")]
    controller.applyStateChanges(
        frozenset({module.StateChange(scope, 1), module.StateChange(scope, 2), module.StateChange(scope, 3)})
    )
    assert [row["tmccId"] for row in controller.rows] == [1, 3]
    assert controller.rows[0]["roadName"] == "Replacement"
    # Keep the deleted object in the fake store to exercise is_deleted itself.
    assert states[1].clear()
    controller.applyStateChanges(frozenset({module.StateChange(scope, 3)}))
    assert [row["tmccId"] for row in controller.rows] == [1]
    controller.close()
    states.append(switch(4, "Late"))
    controller.applyStateChanges(frozenset({module.StateChange(scope, 4)}))
    controller.reload()
    assert [row["tmccId"] for row in controller.rows] == [1]
