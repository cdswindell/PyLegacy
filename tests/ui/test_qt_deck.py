"""Regression coverage for the single-window Qt Steam Deck frontend."""

from __future__ import annotations

import os
import subprocess
import sys
from unittest.mock import patch

import pytest

from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt.app import run_cab, run_deck


def test_deck_platform_uses_two_pane_entrypoint() -> None:
    with (
        patch("pytrain.utils.host_info.is_steam_deck", return_value=True),
        patch("pytrain_ui.qt.app.run_deck", return_value=7) as launch,
    ):
        assert run_cab(CommandScope.ENGINE, 12, ["--test"]) == 7
    launch.assert_called_once_with(CommandScope.ENGINE, 12, ["--test"])


@pytest.mark.parametrize(("width", "height"), [(0, 800), (1280, 0), (-1, 800)])
def test_deck_rejects_invalid_window_dimensions(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="dimensions must be positive"):
        run_deck(CommandScope.ENGINE, 1, width=width, height=height)


# Exercise real Qt component contexts and native input routing in a separate process:
# Qt owns a process-wide application and must not share it with unrelated UI tests.
# noinspection SpellCheckingInspection
DECK_CHILD = r"""
import sys
import traceback
from unittest.mock import Mock, patch

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.gui.controller.steam_deck_input import DeckAction
from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt.app import run_deck

store = ComponentStateStore.build()
for address in (1, 2):
    state = store.get_state(CommandScope.ENGINE, address)
    state.initialize(CommandScope.ENGINE, address)
    state.comp_data.road_name = f"Deck engine {address}"
    state.comp_data.control_type = 1
    state.comp_data.engine_type = 0
failures = []

def factory(argv):
    app = QGuiApplication(argv)
    def checks():
        try:
            windows = [window for window in app.allWindows() if window.isVisible()]
            assert len(windows) == 1, "Steam Deck must use one native window"
            window = windows[0]
            assert (window.width(), window.height()) == (1280, 800)
            left = window.property("leftPane")
            right = window.property("rightPane")
            assert left is not right
            assert left.width() == right.width()
            assert left.width() < 640
            # The controller is held by QML's host context, not by a cab.
            from PySide6.QtQml import QQmlEngine
            deck = QQmlEngine.contextForObject(window).contextProperty("deckController")
            assert deck.focusedPane == "right"
            assert deck.left.cab is not deck.right.cab
            assert deck.left.cab.selectAddress("ENGINE", 1)
            assert deck.right.cab.selectAddress("ENGINE", 2)
            left.setProperty("engineCatalogVisible", False)
            right.setProperty("engineCatalogVisible", False)
            assert deck.left.cab.tmccId == 1
            assert deck.right.cab.tmccId == 2
            deck.left.evaluate('window.changeScope("SWITCH", false)')
            assert left.property("activeScope") == "SWITCH"
            assert right.property("activeScope") == "ENGINE"
            deck.left.evaluate('window.changeScope("ENGINE", false)')
            left.setProperty("engineCatalogVisible", False)
            deck.focusPane("left")
            assert left.property("inputActive")
            assert not right.property("inputActive")
            with patch.object(deck.left, "on_engine_command") as left_command, \
                 patch.object(deck.right, "on_engine_command") as right_command:
                deck._router.handle(DeckAction("bell", "focused", 1.0, "pressed"))
                left_command.assert_called_once()
                right_command.assert_not_called()
                deck.focusPane("right")
                deck._router.handle(DeckAction("bell", "focused", 1.0, "pressed"))
                right_command.assert_called_once()
            # Independent sticks retain their original pane targets.
            with patch.object(deck.left, "nudge_throttle", return_value=3) as left_nudge, \
                 patch.object(deck.right, "nudge_throttle", return_value=4) as right_nudge:
                deck._router.handle(DeckAction("throttle", "left", 1.0, "changed"))
                deck._router.handle(DeckAction("throttle", "right", 1.0, "changed"))
                deck._router.tick(10.0)
                deck._router.tick(10.1)
                left_nudge.assert_called_once()
                right_nudge.assert_called_once()
            # A focus change cancels an active repeat before resolving 'focused' again.
            with patch.object(deck.left, "on_engine_command") as left_command, \
                 patch.object(deck.right, "on_engine_command") as right_command:
                deck._router.handle(DeckAction("boost", "focused", 1.0, "pressed"))
                deck.focusPane("left")
                deck._router.tick(20.0)
                deck._router.tick(20.2)
                left_command.assert_not_called()
                assert right_command.call_count <= 1
            # Both panes have the same current widgets, while help blocks train commands.
            deck.showControls()
            QTest.qWait(30)
            assert deck.controlsVisible and deck.left.controls_visible
            with patch.object(deck.left, "on_engine_command") as command:
                deck._router.handle(DeckAction("bell", "focused", 1.0, "pressed"))
                command.assert_not_called()
            deck.closeControls()
            assert not deck.controlsVisible
            # Admin chords use the existing on-screen hold guard, including cancellation.
            deck.focusPane("right")
            deck.right.evaluate('window.manageVisible = true')
            QTest.qWait(50)
            admin = deck.right.controllers["managePyTrainController"]
            with patch.object(admin, "canRun", return_value=True), patch.object(admin, "run") as run:
                admin.changed.emit()
                QTest.qWait(30)
                deck.right.on_admin_command("QUIT", True)
                QTest.qWait(100)
                deck.right.on_admin_command("QUIT", False)
                run.assert_not_called()
                deck.right.on_admin_command("QUIT", True)
                disconnect = DeckAction("disconnect", "global", 0.0, "disconnected")
                with patch.object(deck._provider, "poll", return_value=[disconnect]):
                    deck.poll()
                QTest.qWait(100)
                run.assert_not_called()
                deck.right.on_admin_command("QUIT", True)
                QTest.qWait(3150)
                run.assert_called_once_with("QUIT", False)
                deck.right.on_admin_command("QUIT", False)
            deck.right.evaluate('window.manageVisible = false')
            deck.focusPane("left")
            deck.left.evaluate('window.changeScope("ACCESSORY", false)')
            assert right.property("activeScope") == "ENGINE"
            assert window.property("title") == "PyTrain — Accessories"
        except BaseException:
            traceback.print_exc()
            failures.append(True)
        finally:
            app.quit()
    QTimer.singleShot(250, checks)
    return app

with patch("PySide6.QtGui.QGuiApplication", side_effect=factory), \
     patch("pytrain.comm.command_listener.CommandDispatcher.get", return_value=Mock()), \
     patch("pytrain_ui.qt.session.restore_engine", return_value=None), \
     patch("pytrain_ui.qt.session.save_engine"), \
     patch("pytrain_ui.qt.deck.SteamDeckInputProvider.start"), \
     patch("pytrain_ui.qt.deck.SteamDeckInputProvider.stop") as stop:
    result = run_deck(CommandScope.ENGINE, 1, [], full_screen=False)
    stop.assert_called_once_with()
assert result == 0
sys.exit(1 if failures else 0)
"""


# Keep native Qt application ownership and child-process diagnostics isolated for this scenario.
# noinspection DuplicatedCode
@pytest.mark.qt_gui
def test_deck_workspaces_and_profile_targets_are_independent() -> None:
    pytest.importorskip("PySide6")
    result = subprocess.run(
        [sys.executable, "-c", DECK_CHILD],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software"),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TypeError:" not in result.stderr, result.stderr
