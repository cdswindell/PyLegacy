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
from unittest.mock import Mock, patch

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt.app import run_cab
from pytrain_ui.qt.pycab import QtCabCommand

ComponentStateStore.build()
previous_sigint = signal.getsignal(signal.SIGINT)
mode, cleanup_failure = sys.argv[1:]

def create_app(argv):
    app = QGuiApplication(argv)
    def request_exit():
        if mode == "signal":
            os.kill(os.getpid(), signal.SIGINT)
        else:
            windows = [window for window in app.allWindows() if window.isVisible()]
            assert windows, "Qt cab did not create a visible window"
            windows[0].close()
    QTimer.singleShot(250, request_exit)
    return app

runtime = Mock()
command = Mock(spec=QtCabCommand)
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
    assert QtCabCommand.send(command) == 0
    close_cab.assert_called_once_with()
    close_catalog.assert_called_once_with()

runtime.shutdown.assert_called_once_with()
assert signal.getsignal(signal.SIGINT) == previous_sigint
import pygame
assert pygame.display.get_driver() == "dummy"
print("QT_EXIT_OK")
"""


@pytest.mark.skipif(importlib.util.find_spec("PySide6") is None, reason="Install the qt-gui extra to test Qt exits")
@pytest.mark.parametrize("action", ["close", "signal"])
@pytest.mark.parametrize("cleanup", ["success", "failure"])
def test_qt_process_exits_and_shuts_down_runtime(action: str, cleanup: str) -> None:
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
    if cleanup == "failure":
        assert "continuing shutdown" in result.stderr
