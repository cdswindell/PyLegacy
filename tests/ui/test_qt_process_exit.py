"""Exercise real Qt process exits without a server or train hardware."""

import importlib.util
import os
import subprocess
import sys

import pytest


# The embedded child must use Qt API identifiers verbatim.
# noinspection SpellCheckingInspection
QT_CHILD = r"""
import os
import signal
import sys
from threading import Event, Thread
from unittest.mock import Mock, patch

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from pytrain.cli.pytrain import PyTrain
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum as Sync
from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt.app import run_cab
from pytrain_ui.qt.pycab import QtCabCommand

ComponentStateStore.build()
previous_sigint = signal.getsignal(signal.SIGINT)
mode, cleanup_failure = sys.argv[1:]
admin_command = Sync[mode] if mode in Sync.__members__ else None

def create_app(argv):
    app = QGuiApplication(argv)
    def request_exit():
        if mode == "signal":
            os.kill(os.getpid(), signal.SIGINT)
        elif admin_command is not None:
            Thread(target=request_admin_exit, daemon=True).start()
        else:
            windows = [window for window in app.allWindows() if window.isVisible()]
            assert windows, "Qt cab did not create a visible window"
            windows[0].close()
    QTimer.singleShot(250, request_exit)
    return app

runtime = Mock(admin_exit_requested=False, is_client=True)
command = Mock(spec=QtCabCommand)
command._sc = Event()

def claim_exit(action, *, source):
    assert source == "callback"
    runtime.admin_exit_requested = True
    runtime._admin_action = action
    return True

def request_admin_exit():
    PyTrain._request_admin_exit(runtime, admin_command, source="callback")

runtime._claim_admin_exit.side_effect = claim_exit
runtime._gui_owns_admin_lifecycle = True
runtime._gui_admin_close = lambda: QtCabCommand._close_for_admin_action(command)

command.pytrain = runtime
# Supply the CLI normally installed by the constructor, without starting network services.
# noinspection PyProtectedMember
command._cli = Mock(scope=CommandScope.ENGINE, tmcc_id=1)

with patch("PySide6.QtGui.QGuiApplication", side_effect=create_app), \
     patch("pytrain.comm.command_listener.CommandDispatcher.get", return_value=Mock()), \
     patch("pytrain_ui.qt.catalog_controller.EngineCatalogController.close") as close_catalog, \
     patch("pytrain_ui.qt.cab_controller.CabController.close") as close_cab:
    if cleanup_failure == "failure":
        close_catalog.side_effect = RuntimeError("Deliberate catalog cleanup failure")
    def run_deferred_action():
        close_cab.assert_called_once_with()
        runtime.shutdown.assert_called_once_with()
        assert runtime._admin_action == admin_command

    runtime.perform_gui_admin_action.side_effect = run_deferred_action
    assert QtCabCommand.send(command) == 0
    close_cab.assert_called_once_with()
    close_catalog.assert_called_once_with()

runtime.shutdown.assert_called_once_with()
if admin_command is None:
    runtime.perform_gui_admin_action.assert_not_called()
else:
    runtime.perform_gui_admin_action.assert_called_once_with()
assert signal.getsignal(signal.SIGINT) == previous_sigint
import pygame
assert pygame.display.get_driver() == "dummy"
print("QT_EXIT_OK")
"""


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Install the qt-gui extra to test Qt exits")
@pytest.mark.parametrize("action", ["close", "signal"])
@pytest.mark.parametrize("cleanup", ["success", "failure"])
def test_qt_process_exits_and_shuts_down_runtime(action: str, cleanup: str) -> None:
    result = _run_qt_child(action, cleanup)
    if cleanup == "failure":
        assert "continuing shutdown" in result.stderr


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Install the qt-gui extra to test Qt exits")
@pytest.mark.parametrize("action", ["QUIT", "REBOOT", "RESTART", "SHUTDOWN", "UPDATE", "UPGRADE"])
def test_admin_commands_close_qt_before_running_deferred_action(action: str) -> None:
    _run_qt_child(action, "success")


def _run_qt_child(action: str, cleanup: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    environment.pop("SDL_VIDEODRIVER", None)
    result = subprocess.run(
        [sys.executable, "-c", QT_CHILD, action, cleanup],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QT_EXIT_OK" in result.stdout
    assert "Unable to assign [undefined] to bool" not in result.stderr
    return result
