"""Startup scripts register a presentation without creating a second runtime."""

from threading import Lock, current_thread, main_thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.pytrain.cli.pytrain import PyTrain


@pytest.fixture
def runtime(monkeypatch):
    # Build only lifecycle state; no network, command, GPIO, or GUI threads are started.
    train = object.__new__(PyTrain)
    vars(train).update(
        _api=False,
        _gui_admin_close=None,
        _gui_owns_admin_lifecycle=False,
        _admin_state_lock=Lock(),
        _exit_requested=False,
        _shutdown_started=False,
        _headless=True,
        _buttons_file="buttons.py",
        _replay_file=None,
        _admin_action=None,
        _cache_sync_manager=None,
    )
    monkeypatch.setattr(PyTrain, "is_server", property(lambda _: False))
    monkeypatch.setattr(PyTrain, "is_client", property(lambda _: False))
    for name in ("_start_cache_sync", "shutdown", "shutdown_service", "shutdown_cache", "perform_gui_admin_action"):
        monkeypatch.setattr(train, name, Mock())
    vars(train)["_command_processor_available"] = Mock()
    return train


def test_gui_runs_on_main_thread_after_complete_buttons_script(runtime, monkeypatch):
    from src.pytrain.cli import pytrain as module

    events = []

    def launch():
        assert current_thread() is main_thread()
        events.append("gui")
        return 0

    def load(_path, train):
        train.register_startup_gui(launch, Mock())
        events.append("script finished")
        return SimpleNamespace(join=lambda: events.append("loader joined"))

    monkeypatch.setattr(module, "ButtonsFileLoader", load)
    runtime.run()
    assert events == ["script finished", "loader joined", "gui"]
    runtime.shutdown.assert_called_once_with()
    runtime.shutdown_service.assert_called_once_with()
    runtime.shutdown_cache.assert_called_once_with()
    runtime.perform_gui_admin_action.assert_not_called()


def test_registration_rejects_api_mode_and_duplicate_gui(runtime):
    vars(runtime)["_api"] = True
    with pytest.raises(RuntimeError, match="API mode"):
        runtime.register_startup_gui(Mock(), Mock())
    vars(runtime)["_api"] = False
    runtime.register_startup_gui(Mock(), Mock())
    with pytest.raises(RuntimeError, match="already registered"):
        runtime.register_startup_gui(Mock(), Mock())


# The log capture fixture name is supplied by pytest.
# noinspection SpellCheckingInspection
def test_gui_failure_still_shuts_down_runtime_and_remaining_services(runtime, monkeypatch, caplog):
    from src.pytrain.cli import pytrain as module

    launch = Mock(side_effect=ValueError("window failed"))
    monkeypatch.setattr(module, "ButtonsFileLoader", lambda *_: SimpleNamespace(join=lambda: None))
    runtime.register_startup_gui(launch, Mock())
    runtime.shutdown.side_effect = RuntimeError("cleanup failed")
    with pytest.raises(ValueError, match="window failed"):
        runtime.run()
    runtime.shutdown_service.assert_called_once_with()
    runtime.shutdown_cache.assert_called_once_with()
    assert "cleanup failed" in caplog.text


def test_admin_request_before_window_start_skips_gui_and_finishes_handoff(runtime, monkeypatch):
    from src.pytrain.cli import pytrain as module

    launch = Mock()
    runtime.register_startup_gui(launch, Mock())
    vars(runtime)["_exit_requested"] = True
    monkeypatch.setattr(module, "ButtonsFileLoader", lambda *_: SimpleNamespace(join=lambda: None))
    runtime.run()
    launch.assert_not_called()
    runtime.shutdown.assert_called_once_with()
    runtime.perform_gui_admin_action.assert_called_once_with()
