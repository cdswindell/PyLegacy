"""Exercise the PyCab startup update handoff without Tk or external processes."""

import os
import sys
from unittest.mock import Mock, call, patch

import pytest

import src.pytrain as package
from src.pytrain.cli import pycab, pytrain
from src.pytrain.protocol.command_base import CommandBase
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum

RUN_WORKER = pytrain.PyTrain.run


@pytest.mark.parametrize(
    "update_during_construction", [True, False], ids=["before-constructor-returns", "at-sync-wait"]
)
def test_pycab_startup_update_runs_on_the_host(pytrain_startup, monkeypatch, update_during_construction):
    startup = pytrain_startup
    startup.client_listener.update_client_if_needed.return_value = True
    startup.store.return_value.get_state.return_value = None

    def run_worker():
        active = pytrain.PyTrain.current()
        assert active is not None
        with patch.object(pytrain.PyTrain, "run", RUN_WORKER):
            active.run()

    startup.run.side_effect = run_worker
    thread = startup.thread.return_value
    if update_during_construction:
        thread.start.side_effect = startup.run

    monkeypatch.setattr(pytrain.PyTrain, "_start_cache_sync", Mock())
    monkeypatch.setattr(
        pytrain.PyTrain, "_load_client_state", Mock(side_effect=AssertionError("Roster sync was skipped"))
    )
    for owner, method in (
        (pytrain.CommandObserver, "stop"),
        (pytrain.CommBuffer, "stop"),
        (pytrain.CommandListener, "stop"),
        (pytrain.PdiListener, "stop"),
        (pytrain.GpioHandler, "reset_all"),
    ):
        monkeypatch.setattr(owner, method, Mock())
    monkeypatch.setattr("src.pytrain.cli.pytrain.self_update_disabled", lambda: False)
    monkeypatch.setattr("src.pytrain.cli.pytrain.is_steam_deck", lambda: False)
    monkeypatch.setattr("src.pytrain.utils.flatpak_updates.installed_flatpak_tag", lambda: None)
    monkeypatch.setattr(package, "is_package", lambda: False)
    watcher = Mock()
    monkeypatch.setattr("src.pytrain.protocol.command_base.StateWatcher", Mock(return_value=watcher))
    window = Mock(side_effect=AssertionError("A startup update must run before Tk opens"))
    monkeypatch.setattr(pycab, "PyCabPanelGui", window)
    subprocess_run = Mock()
    relaunch = Mock()
    monkeypatch.setattr(pytrain.subprocess, "run", subprocess_run)
    monkeypatch.setattr(pytrain.PyTrain, "relaunch", relaunch)

    monkeypatch.setattr(pycab, "window_geometry", lambda *_args: (600, 960, 1.0))
    cli = pycab.PyCabCli(cmd_line=["-server", "192.0.2.10"], do_fire=False)
    command = cli.command
    assert isinstance(command, pycab.PyCabGuiCmd)
    worker = command.pytrain
    wait_for_sync = command.wait_for_sync

    def wait_for_startup(_command):
        if not update_during_construction:
            startup.run()
        # Check the wake-up before waiting so a regression fails instead of hanging the suite.
        # noinspection PyProtectedMember
        assert command._sc.is_set()
        wait_for_sync()

    monkeypatch.setattr(CommandBase, "wait_for_sync", wait_for_startup)
    command.send()

    assert pytrain.PyTrain.current() is worker
    assert not worker.is_api
    # The pending action must be the startup UPDATE recorded by the worker.
    # noinspection PyProtectedMember
    assert worker._admin_action is TMCC1SyncCommandEnum.UPDATE
    startup.run.assert_called_once_with()
    window.assert_not_called()
    assert watcher.shutdown.call_count == int(not update_during_construction)
    thread.join.assert_called_once_with(timeout=1.0)
    assert subprocess_run.call_args_list == [
        call([sys.executable, "-m", "pip", "install", "-U", "pip"], cwd=os.getcwd(), check=False),
        call(["git", "pull"], cwd=os.getcwd(), check=False),
        call([sys.executable, "-m", "pip", "install", "-r", worker.requirements_file], cwd=os.getcwd(), check=False),
    ]
    relaunch.assert_called_once_with(pytrain.PyTrainExitStatus.UPDATE)
