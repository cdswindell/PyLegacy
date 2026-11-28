"""Real-window coverage of buttons-file startup and committed GUI selections."""

import os
import subprocess
import sys

import pytest


# The embedded child program uses valid Qt API class names.
# noinspection SpellCheckingInspection
WINDOW_CHECK = r"""
import sys
import traceback
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine
from pytrain.cli.pytrain import PyTrain
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.components import ConsistComponent
from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt import QtCabGui

store = ComponentStateStore.build()
for scope, address in ((CommandScope.ENGINE, 37), (CommandScope.ENGINE, 12), (CommandScope.TRAIN, 502),
                       (CommandScope.SWITCH, 4), (CommandScope.ROUTE, 6)):
    state = store.get_state(scope, address)
    state.initialize(scope, address)
    if scope in (CommandScope.ENGINE, CommandScope.TRAIN):
        state.comp_data.road_name = "Test"
        state.comp_data.control_type = 2
        state.comp_data.engine_type = 5 if address == 12 else 0
store.get_state(CommandScope.TRAIN, 502).comp_data.consist_comps = [ConsistComponent(12, 10)]
runtime = SimpleNamespace(register_startup_gui=lambda run, close: None, is_server=False,
                          server_version=None, admin_exit_requested=False, debug=False, echo=False,
                          is_synchronized=lambda: True)
failures = []
deck = sys.argv[1] == "deck"
seen = []

def factory(argv):
    app = QGuiApplication(argv)
    def check():
        try:
            window = next(window for window in app.allWindows() if window.property("activeTarget") is not None)
            context = QQmlEngine.contextForObject(window)
            if deck:
                workspace = window.property("rightPane")
                cab = context.contextProperty("rightCabController")
                links = context.contextProperty("rightTrainLinkController")
            else:
                assert (window.width(), window.height()) == (800, 1280)
                workspace = window.property("workspace")
                cab = context.contextProperty("cabController")
                links = context.contextProperty("trainLinkController")
            assert gui.scope == CommandScope.TRAIN
            assert gui.tmcc_id == 502, gui.selection
            assert gui.active_engine_state is store.get_state(CommandScope.TRAIN, 502)
            assert links.select(12)
            app.processEvents()
            assert (gui.scope, gui.tmcc_id) == (CommandScope.ENGINE, 12), gui.selection
            assert cab.tmccId == 502, "Selecting a car must preserve the train throttle target"
            links.clearSelection()
            app.processEvents()
            assert (gui.scope, gui.tmcc_id) == (CommandScope.TRAIN, 502)
            if deck:
                left = context.contextProperty("leftCabController")
                left.selectAddress("ENGINE", 37)
                window.property("leftPane").setProperty("activeScope", "ENGINE")
                context.contextProperty("deckController").focusPane("left")
                app.processEvents()
                assert (gui.scope, gui.tmcc_id) == (CommandScope.ENGINE, 37), gui.selection
            else:
                cab.selectAddress("ENGINE", 37)
                workspace.setProperty("activeScope", "ENGINE")
                app.processEvents()
                assert (gui.scope, gui.tmcc_id) == (CommandScope.ENGINE, 37), gui.selection
                switches = context.contextProperty("switchOpsController")
                switches.select(4)
                workspace.setProperty("activeScope", "SWITCH")
                app.processEvents()
                assert (gui.scope, gui.tmcc_id) == (CommandScope.SWITCH, 4), gui.selection
                routes = context.contextProperty("routeOpsController")
                routes.select(6)
                workspace.setProperty("activeScope", "ROUTE")
                app.processEvents()
                assert (gui.scope, gui.tmcc_id) == (CommandScope.ROUTE, 6), gui.selection
            assert seen, "The startup handle must notify subscribers"
        except Exception:
            failures.append(traceback.format_exc())
        finally:
            gui.close()
    QTimer.singleShot(400, check)
    QTimer.singleShot(10000, app.quit)
    return app

with patch("pytrain.comm.command_listener.CommandDispatcher.get", return_value=Mock()), \
     patch.object(PyTrain, "current", return_value=runtime), \
     patch("pytrain_ui.qt.session.restore_engine", return_value=37), \
     patch("pytrain_ui.qt.session.save_engine"), \
     patch("PySide6.QtGui.QGuiApplication", factory):
    gui = QtCabGui(tmcc_id=502, scope=CommandScope.TRAIN, deck=deck,
                   width=1280 if deck else 800, height=800 if deck else 1280, full_screen=False)
    gui.subscribe(seen.append)
    assert gui.run() == 0
assert not failures, "\n".join(failures)
print("STARTUP_GUI_OK")
"""


@pytest.mark.qt_gui
@pytest.mark.parametrize("mode", ["cab", "deck"])
def test_startup_window_reports_selection_and_preserves_existing_runtime(mode):
    pytest.importorskip("PySide6")
    result = subprocess.run(
        [sys.executable, "-c", WINDOW_CHECK, mode],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STARTUP_GUI_OK" in result.stdout
    assert "Error:" not in result.stderr, result.stderr
