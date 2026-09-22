import logging
import threading
from argparse import ArgumentError
from queue import Empty, Queue
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from src.pytrain.cli import pytrain as module
from src.pytrain.comm.comm_buffer import CommBufferProxy


@pytest.fixture
def runtime(bare_pytrain, monkeypatch):
    p = bare_pytrain
    p._tmcc_buffer = Mock(spec=CommBufferProxy)
    p._tmcc_listener = Mock(spec=module.ClientStateListener)
    p._tmcc_listener.update_client_if_needed.return_value = False
    p._tmcc_listener.port = 5111
    p._headless = p._api = False
    p._buttons_file = p._replay_file = p._admin_action = None
    p._service_info = p._zeroconf = p._cache_sync_manager = None
    p._version = "test"
    p._command_queue = None
    p._command_processor_available = Mock(spec=threading.Event)
    p._args = SimpleNamespace(server_port=5110)
    p._ser2 = True
    p._base_addr = "192.0.2.1"
    p._cache_sync_enabled = False
    p._cache_sync_port = 5112
    effects = Mock()
    for name in [
        "_start_cache_sync",
        "register_service",
        "_load_client_state",
        "_handle_command",
        "shutdown",
        "shutdown_service",
        "upgrade",
        "update",
        "restart",
        "reboot",
    ]:
        double = Mock()
        monkeypatch.setattr(p, name, double)
        effects.attach_mock(double, name)
    for owner, name in [
        (module, "Zeroconf"),
        (module, "ButtonsFileLoader"),
        (module.readline, "set_auto_history"),
        (module.readline, "write_history_file"),
    ]:
        double = Mock()
        monkeypatch.setattr(owner, name, double)
        effects.attach_mock(double, name)
    for owner, name in [
        (module.subprocess, "run"),
        (module.os, "kill"),
        (module.os, "execv"),
        (module, "sleep"),
        (threading.Thread, "start"),
    ]:
        monkeypatch.setattr(owner, name, Mock(side_effect=AssertionError(f"Unexpected {name}")))
    monkeypatch.setattr("builtins.input", Mock(side_effect=KeyboardInterrupt))
    monkeypatch.setattr(module.signal, "pause", Mock(side_effect=KeyboardInterrupt))
    return SimpleNamespace(p=p, effects=effects)


@pytest.mark.parametrize("mode", ["interactive", "api", "headless"])
def test_runtime_modes(runtime, mode):
    p = runtime.p
    p._api = mode == "api"
    p._headless = mode == "headless"
    p._command_queue = Mock(get=Mock(side_effect=KeyboardInterrupt))
    p.run()
    p._command_processor_available.set.assert_called_once_with()
    p._load_client_state.assert_called_once_with()
    p.shutdown.assert_called_once_with()
    p.shutdown_service.assert_called_once_with()
    assert module.readline.set_auto_history.call_count == (mode != "headless")
    assert module.readline.write_history_file.call_count == (mode == "interactive")
    if mode == "interactive":
        module.readline.write_history_file.assert_called_once_with(module.DEFAULT_HISTORY_FILE)
    elif mode == "api":
        p._command_queue.get.assert_called_once_with(block=True)
        p._command_queue.task_done.assert_not_called()
    else:
        module.signal.pause.assert_called_once_with()


@pytest.mark.parametrize(
    "enabled,manager,available", [(False, False, False), (True, False, False), (True, True, False), (True, True, True)]
)
def test_server_startup_order(runtime, enabled, manager, available):
    p = runtime.p
    p._tmcc_buffer = Mock(spec=module.CommBufferSingleton)
    p._cache_sync_enabled = enabled
    p._cache_sync_manager = SimpleNamespace(available=available) if manager else None
    p._buttons_file = "layout.py"
    p.run()
    p.register_service.assert_called_once_with(True, True, 5110, enabled and manager and available, 5112)
    p._load_client_state.assert_not_called()
    assert runtime.effects.mock_calls[:5] == [
        call._start_cache_sync(),
        call.Zeroconf(),
        call.register_service(True, True, 5110, enabled and manager and available, 5112),
        call.ButtonsFileLoader("layout.py", p),
        call.ButtonsFileLoader().join(),
    ]
    assert p._buttons_loader is module.ButtonsFileLoader.return_value


def test_client_state_precedes_buttons(runtime):
    p = runtime.p
    p._buttons_file = "layout.py"
    p.run()
    assert runtime.effects.mock_calls[:4] == [
        call._start_cache_sync(),
        call._load_client_state(),
        call.ButtonsFileLoader("layout.py", p),
        call.ButtonsFileLoader().join(),
    ]


def test_update_required_client(runtime, monkeypatch):
    p = runtime.p
    p._tmcc_listener.update_client_if_needed.return_value = True
    callback = Mock()
    monkeypatch.setattr(module.PyTrain, "__call__", callback)
    p.run()
    p._load_client_state.assert_not_called()
    assert callback.call_args.args[0].command == module.TMCC1SyncCommandEnum.UPDATE
    p._command_processor_available.set.assert_called_once_with()


@pytest.mark.parametrize("error", [SystemExit(), ArgumentError(None, "bad argument")])
def test_interactive_parser_errors_continue(runtime, monkeypatch, error):
    prompt = Mock(side_effect=["invalid", "valid", KeyboardInterrupt()])
    monkeypatch.setattr("builtins.input", prompt)
    runtime.p._handle_command.side_effect = [error, None]
    runtime.p.run()
    assert runtime.p._handle_command.call_args_list == [call("invalid"), call("valid")]
    assert prompt.call_args_list == [call(">> ")] * 3


@pytest.mark.parametrize("error", [None, SystemExit(), ArgumentError(None, "bad argument"), KeyboardInterrupt()])
def test_api_queue_accounting(runtime, error):
    p = runtime.p
    p._api = True
    p._command_queue = Mock(get=Mock(side_effect=[Empty(), "", "engine 1 horn", KeyboardInterrupt()]))
    p._handle_command.side_effect = [None, error]
    p.run()
    assert p._handle_command.call_args_list == [call(""), call("engine 1 horn")]
    p._command_queue.task_done.assert_called_once_with()
    p.shutdown.assert_called_once_with()


def test_api_handler_can_clear_queue(runtime):
    p = runtime.p
    p._api = True
    queue = p._command_queue = Mock(get=Mock(return_value="quit"))

    def handle(command):
        p._command_queue = None
        raise KeyboardInterrupt

    p._handle_command.side_effect = handle
    p.run()
    queue.task_done.assert_not_called()


def test_replay_once_continues_after_parser_errors(runtime, tmp_path, monkeypatch):
    replay = tmp_path / "replay.txt"
    replay.write_text("first\ninvalid\nlast\n", encoding="utf-8")
    p = runtime.p
    p._replay_file = str(replay)
    p._handle_command.side_effect = [SystemExit(), ArgumentError(None, "invalid"), None, None]
    monkeypatch.setattr("builtins.input", Mock(side_effect=["interactive", KeyboardInterrupt()]))
    p.run()
    assert p._handle_command.call_args_list == [call("first\n"), call("invalid\n"), call("last\n"), call("interactive")]


def test_missing_replay_continues(runtime, tmp_path, caplog):
    runtime.p._replay_file = str(tmp_path / "missing")
    runtime.p.run()
    assert "not found, continuing" in caplog.text
    runtime.p._handle_command.assert_not_called()
    runtime.p.shutdown.assert_called_once_with()


@pytest.mark.parametrize(
    "action,method,kwargs",
    [
        ("UPGRADE", "upgrade", {}),
        ("UPDATE", "update", {}),
        ("RESTART", "restart", {}),
        ("REBOOT", "reboot", {}),
        ("SHUTDOWN", "reboot", {"reboot": False}),
        ("QUIT", None, {}),
    ],
)
def test_deferred_actions_after_cleanup(runtime, action, method, kwargs):
    p = runtime.p
    p._admin_action = module.TMCC1SyncCommandEnum[action]
    p.run()
    calls = runtime.effects.mock_calls
    if method:
        getattr(p, method).assert_called_once_with(**kwargs)
        assert calls.index(call.shutdown_service()) < calls.index(getattr(call, method)(**kwargs))
    else:
        for name in ("upgrade", "update", "restart", "reboot"):
            getattr(p, name).assert_not_called()


@pytest.mark.parametrize("source", ["state", "buttons", "command"])
def test_unexpected_runtime_errors_still_close_service(runtime, source):
    p = runtime.p
    error = RuntimeError("runtime failure")
    if source == "state":
        p._load_client_state.side_effect = error
    elif source == "buttons":
        p._buttons_file = "layout.py"
        module.ButtonsFileLoader.return_value.join.side_effect = error
    else:
        p._api = True
        p._command_queue = Mock(get=Mock(return_value="command"))
        p._handle_command.side_effect = error
    with pytest.raises(RuntimeError, match="runtime failure"):
        p.run()
    p.shutdown_service.assert_called_once_with()
    p.shutdown.assert_not_called()
    if source == "command":
        p._command_queue.task_done.assert_called_once_with()


@pytest.mark.parametrize(
    "api,queue_present,command",
    [(True, True, "horn"), (True, False, "horn"), (False, True, "horn"), (True, True, ""), (False, False, None)],
)
def test_queue_command_routing(runtime, api, queue_present, command):
    p = runtime.p
    p._api = api
    queue = Mock()
    p._command_queue = queue if queue_present else None
    p.queue_command(command)
    if command and api and queue_present:
        queue.put.assert_called_once_with(command)
        p._handle_command.assert_not_called()
    elif command:
        p._handle_command.assert_called_once_with(command)
        queue.put.assert_not_called()
    else:
        queue.put.assert_not_called()
        p._handle_command.assert_not_called()


@pytest.mark.parametrize(
    "script,expected",
    [
        ("self._pytrain.queue_command('engine 1 horn')", None),
        ("if :", "SyntaxError"),
        ("raise RuntimeError('script failed')", "RuntimeError"),
        (None, "not found, continuing"),
    ],
)
def test_buttons_loader(bare_pytrain, monkeypatch, tmp_path, caplog, script, expected):
    path = tmp_path / "buttons.py"
    if script is not None:
        path.write_text(script, encoding="utf-8")
    start = Mock()
    monkeypatch.setattr(threading.Thread, "start", start)
    bare_pytrain.queue_command = Mock()
    loader = module.ButtonsFileLoader(str(path), bare_pytrain)
    start.assert_called_once_with()
    assert loader.daemon is True
    assert loader.name == f"{module.PROGRAM_NAME} Buttons Script Loader"
    assert loader._pytrain is bare_pytrain
    assert loader._buttons_file == str(path)
    with caplog.at_level(logging.INFO, logger=module.__name__):
        loader.run()
    if expected:
        assert expected in caplog.text
        bare_pytrain.queue_command.assert_not_called()
    else:
        bare_pytrain.queue_command.assert_called_once_with("engine 1 horn")
        assert "Buttons registered" in caplog.text


@pytest.mark.parametrize("failure", [None, "service", "api", "disconnect", "buffer", "tmcc", "pdi", "state", "gpio"])
def test_shutdown_continues_after_individual_failure(runtime, monkeypatch, caplog, failure):
    p = runtime.p
    p._api = True
    queue = p._command_queue = Queue()
    queue.put("pending")
    effects = Mock()
    operations = [
        (p, "shutdown_service", "service"),
        (p._tmcc_buffer, "disconnect", "disconnect"),
        (module.CommBuffer, "stop", "buffer"),
        (module.CommandListener, "stop", "tmcc"),
        (module.PdiListener, "stop", "pdi"),
        (module.ComponentStateStore, "reset", "state"),
        (module.GpioHandler, "reset_all", "gpio"),
    ]
    for owner, method, name in operations:
        double = Mock(side_effect=RuntimeError(name) if failure == name else None)
        monkeypatch.setattr(owner, method, double)
        effects.attach_mock(double, name)
    if failure == "api":
        monkeypatch.setattr(queue.all_tasks_done, "notify_all", Mock(side_effect=RuntimeError("api")))
    module.PyTrain.shutdown(p)
    assert effects.mock_calls == [
        call.service(),
        call.disconnect(5111),
        call.buffer(),
        call.tmcc(),
        call.pdi(),
        call.state(),
        call.gpio(),
    ]
    assert queue.empty()
    if failure != "api":
        assert queue.unfinished_tasks == 0
        assert p._command_queue is None
    if failure:
        assert "continuing shutdown" in caplog.text


@pytest.mark.parametrize("server,port,api", [(True, 5111, False), (False, None, True), (False, 0, False)])
def test_shutdown_without_client_or_queue(runtime, monkeypatch, server, port, api):
    p = runtime.p
    p._api = api
    p._tmcc_listener.port = port
    if server:
        p._tmcc_buffer = Mock(spec=module.CommBufferSingleton)
    for owner, name in [
        (module.CommBuffer, "stop"),
        (module.CommandListener, "stop"),
        (module.PdiListener, "stop"),
        (module.ComponentStateStore, "reset"),
        (module.GpioHandler, "reset_all"),
    ]:
        monkeypatch.setattr(owner, name, Mock())
    module.PyTrain.shutdown(p)
    if not server:
        p._tmcc_buffer.disconnect.assert_not_called()
    module.GpioHandler.reset_all.assert_called_once_with()


@pytest.mark.parametrize("failure", [None, "cache", "unregister", "close"])
def test_service_shutdown_failure_boundaries(runtime, monkeypatch, caplog, failure):
    p = runtime.p
    manager = p._cache_sync_manager = Mock()
    info = p._service_info = object()
    zeroconf = p._zeroconf = Mock()
    stop = Mock(side_effect=RuntimeError("cache") if failure == "cache" else None)
    monkeypatch.setattr(module.CacheSyncManager, "stop", stop)
    if failure in ("unregister", "close"):
        getattr(zeroconf, "unregister_service" if failure == "unregister" else "close").side_effect = RuntimeError(
            failure
        )
        with pytest.raises(RuntimeError, match=failure):
            module.PyTrain.shutdown_service(p)
        assert p._service_info is info
        assert p._zeroconf is zeroconf
        assert zeroconf.close.call_count == (failure == "close")
    else:
        module.PyTrain.shutdown_service(p)
        zeroconf.close.assert_called_once_with()
        assert p._service_info is p._zeroconf is None
    stop.assert_called_once_with()
    zeroconf.unregister_service.assert_called_once_with(info)
    assert p._cache_sync_manager is (manager if failure == "cache" else None)
    if failure == "cache":
        assert "continuing shutdown" in caplog.text


@pytest.mark.parametrize("info,zeroconf", [(None, None), (object(), None), (None, Mock())])
def test_service_shutdown_without_registration(runtime, monkeypatch, info, zeroconf):
    p = runtime.p
    p._service_info, p._zeroconf = info, zeroconf
    stop = Mock()
    monkeypatch.setattr(module.CacheSyncManager, "stop", stop)
    module.PyTrain.shutdown_service(p)
    stop.assert_called_once_with()
    assert p._cache_sync_manager is None
    if zeroconf is not None:
        zeroconf.assert_not_called()
        assert zeroconf.mock_calls == []
