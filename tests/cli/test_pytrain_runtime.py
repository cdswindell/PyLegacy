import logging
import threading
from argparse import ArgumentError
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from src.pytrain.cli import pytrain as module
from src.pytrain.comm.comm_buffer import CommBufferProxy

THREAD_START = threading.Thread.start


@pytest.fixture
def runtime(bare_pytrain, monkeypatch):
    p = bare_pytrain
    p._shutdown_lock = threading.Lock()
    p._tmcc_buffer = Mock(spec=CommBufferProxy)
    p._tmcc_listener = Mock(spec=module.ClientStateListener)
    p._tmcc_listener.update_client_if_needed.return_value = False
    p._tmcc_listener.port = 5111
    p._headless = p._api = False
    p._echo = False
    p._api_thread = None
    p._server_ips = ["192.0.2.1"]
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
        "shutdown_cache",
        "upgrade",
        "update",
        "restart",
        "reboot",
    ]:
        double = Mock()
        monkeypatch.setattr(p, name, double)
        effects.attach_mock(double, name)
    p.shutdown_cache.side_effect = lambda: setattr(p, "_cache_sync_manager", None)
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
    p.shutdown_cache.assert_called_once_with()
    assert runtime.effects.mock_calls[-2:] == [call.shutdown_service(), call.shutdown_cache()]
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


def test_startup_update_interrupt_runs_full_shutdown(runtime):
    p = runtime.p
    p._tmcc_listener.update_client_if_needed.return_value = True
    module.os.kill.side_effect = KeyboardInterrupt
    try:
        p.run()
    except KeyboardInterrupt:
        pytest.fail("Startup UPDATE interrupt escaped before full shutdown")
    p.shutdown.assert_called_once_with()
    p.update.assert_called_once_with()
    p._handle_command.assert_not_called()
    calls = runtime.effects.mock_calls
    assert calls.index(call.shutdown()) < calls.index(call.shutdown_cache()) < calls.index(call.update())


@pytest.mark.parametrize("stage", ["shutdown", "shutdown_service", "shutdown_cache", "write_history_file"])
@pytest.mark.parametrize("error", [KeyboardInterrupt, RuntimeError])
@pytest.mark.parametrize("action", ["UPDATE", "UPGRADE", "RESTART", "REBOOT", "SHUTDOWN"])
def test_escaping_cleanup_error_never_dispatches_action(runtime, stage, error, action):
    p = runtime.p
    p._admin_action = module.TMCC1SyncCommandEnum[action]
    target = module.readline.write_history_file if stage == "write_history_file" else getattr(p, stage)
    target.side_effect = error("independent cancellation")
    with pytest.raises(error, match="independent cancellation"):
        p.run()
    for name in ("update", "upgrade", "restart", "reboot"):
        getattr(p, name).assert_not_called()
    module.subprocess.run.assert_not_called()
    module.os.execv.assert_not_called()


@pytest.fixture
def real_exit_runtime(runtime, monkeypatch):
    p = runtime.p
    for name in ("shutdown", "shutdown_service", "shutdown_cache"):
        monkeypatch.setattr(p, name, getattr(module.PyTrain, name).__get__(p))
    effects = Mock()
    for owner, method, name in [
        (module.CacheSyncManager, "stop", "cache"),
        (p._tmcc_buffer, "disconnect", "disconnect"),
        (module.CommBuffer, "stop", "buffer"),
        (module.CommandListener, "stop", "tmcc"),
        (module.PdiListener, "stop", "pdi"),
        (module.ComponentStateStore, "reset", "state"),
        (module.GpioHandler, "reset_all", "gpio"),
        (p, "update", "update"),
    ]:
        double = Mock()
        monkeypatch.setattr(owner, method, double)
        effects.attach_mock(double, name)
    p._cache_sync_manager = object()
    p._handle_command.side_effect = lambda _: p.do_admin_cmd(module.TMCC1SyncCommandEnum.UPDATE)
    monkeypatch.setattr("builtins.input", Mock(return_value="update"))
    return SimpleNamespace(p=p, effects=effects)


def test_echo_while_cache_shutdown_waits_finishes_cleanup_before_update(real_exit_runtime, caplog, monkeypatch):
    p, effects = real_exit_runtime.p, real_exit_runtime.effects
    monkeypatch.setattr(threading.Thread, "start", THREAD_START)
    caplog.set_level(logging.DEBUG, logger=module.log.name)
    waiting = threading.Event()
    echoed = threading.Event()

    def echo():
        assert waiting.wait(2)
        try:
            p(module.CommandReq(module.TMCC1SyncCommandEnum.UPDATE))
            p(module.CommandReq(module.TMCC1SyncCommandEnum.RESTART))
        finally:
            echoed.set()

    def stop():
        waiting.set()
        assert echoed.wait(2)

    module.CacheSyncManager.stop.side_effect = stop
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(echo)
        p.run()
        future.result(timeout=2)
    assert effects.mock_calls == [
        call.cache(),
        call.disconnect(5111),
        call.buffer(),
        call.tmcc(),
        call.pdi(),
        call.state(),
        call.gpio(),
        call.update(),
    ]
    assert p._cache_sync_manager is None
    assert p._admin_action == module.TMCC1SyncCommandEnum.UPDATE
    module.os.kill.assert_not_called()
    assert "Full teardown entered" in caplog.text
    assert "Full teardown completed" in caplog.text
    assert "Entering deferred action action=UPDATE" in caplog.text


@pytest.mark.parametrize("retry_interrupted", [False, True])
def test_interrupted_full_shutdown_retries_cache_but_never_updates(real_exit_runtime, retry_interrupted):
    p, effects = real_exit_runtime.p, real_exit_runtime.effects
    manager = p._cache_sync_manager

    def interrupted():
        if module.CacheSyncManager.stop.call_count == 1 or retry_interrupted:
            assert p._cache_sync_manager is manager
            raise KeyboardInterrupt("cache interrupted")

    module.CacheSyncManager.stop.side_effect = interrupted
    with pytest.raises(KeyboardInterrupt, match="cache interrupted"):
        p.run()
    assert p._cache_sync_manager is (manager if retry_interrupted else None)
    assert not p._shutdown_lock.locked()
    assert effects.mock_calls == [call.cache(), call.cache()]
    p.update.assert_not_called()
    module.CacheSyncManager.stop.side_effect = None
    p.shutdown()
    assert p._cache_sync_manager is None
    p._tmcc_buffer.disconnect.assert_called_once_with(5111)
    p.update.assert_not_called()


def test_failed_cache_stop_blocks_update_until_retry_finishes(real_exit_runtime):
    p = real_exit_runtime.p
    manager = p._cache_sync_manager
    module.CacheSyncManager.stop.side_effect = RuntimeError("still stopping")
    with pytest.raises(RuntimeError, match="still stopping"):
        p.run()
    assert p._cache_sync_manager is manager
    p._tmcc_buffer.disconnect.assert_called_once_with(5111)
    p.update.assert_not_called()
    module.CacheSyncManager.stop.side_effect = None
    p.shutdown_cache()
    assert p._cache_sync_manager is None


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
    p.shutdown_service.assert_called_once_with()
    p.shutdown_cache.assert_called_once_with()
    cleanup_index = calls.index(call.shutdown_service())
    assert calls[cleanup_index : cleanup_index + 2] == [call.shutdown_service(), call.shutdown_cache()]
    if method:
        getattr(p, method).assert_called_once_with(**kwargs)
        assert calls.index(call.shutdown_cache()) < calls.index(getattr(call, method)(**kwargs))
    else:
        for name in ("upgrade", "update", "restart", "reboot"):
            getattr(p, name).assert_not_called()


@pytest.mark.parametrize("source", ["state", "buttons", "command"])
def test_unexpected_runtime_errors_still_close_service_and_cache(runtime, source):
    p = runtime.p
    p._admin_action = module.TMCC1SyncCommandEnum.UPDATE
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
    with pytest.raises(RuntimeError, match="runtime failure") as exc:
        p.run()
    assert exc.value is error
    p.shutdown_service.assert_called_once_with()
    p.shutdown_cache.assert_called_once_with()
    assert runtime.effects.mock_calls[-2:] == [call.shutdown_service(), call.shutdown_cache()]
    p.shutdown.assert_not_called()
    p.update.assert_not_called()
    if source == "command":
        p._command_queue.task_done.assert_called_once_with()


@pytest.mark.parametrize("cache_failure", [False, True])
def test_runtime_finalization_repeats_helpers_without_repeating_successful_cleanup(
    runtime, monkeypatch, caplog, cache_failure
):
    caplog.set_level(logging.WARNING, logger=module.__name__)
    p = runtime.p
    info = p._service_info = object()
    zeroconf = p._zeroconf = Mock()
    p._cache_sync_manager = object()
    effects = Mock()
    for name in ("shutdown", "shutdown_service", "shutdown_cache"):
        double = Mock(wraps=getattr(module.PyTrain, name).__get__(p))
        monkeypatch.setattr(p, name, double)
        effects.attach_mock(double, name)
    operations = [
        (zeroconf, "unregister_service", "unregister"),
        (zeroconf, "close", "close"),
        (module.CacheSyncManager, "stop", "cache"),
        (p._tmcc_buffer, "disconnect", "disconnect"),
        (module.CommBuffer, "stop", "buffer"),
        (module.CommandListener, "stop", "tmcc"),
        (module.PdiListener, "stop", "pdi"),
        (module.ComponentStateStore, "reset", "state"),
        (module.GpioHandler, "reset_all", "gpio"),
    ]
    for owner, method, name in operations:
        double = Mock(side_effect=[RuntimeError("cache"), None] if name == "cache" and cache_failure else None)
        monkeypatch.setattr(owner, method, double)
        effects.attach_mock(double, name)

    p.run()

    expected_calls = [
        call.shutdown(),
        call.shutdown_service(),
        call.unregister(info),
        call.close(),
        call.shutdown_cache(),
        call.cache(),
        call.disconnect(5111),
        call.buffer(),
        call.tmcc(),
        call.pdi(),
        call.state(),
        call.gpio(),
        call.shutdown_service(),
        call.shutdown_cache(),
    ]
    if cache_failure:
        expected_calls.append(call.cache())
    assert effects.mock_calls == expected_calls
    p.shutdown.assert_called_once_with()
    assert p.shutdown_service.call_count == p.shutdown_cache.call_count == 2
    zeroconf.unregister_service.assert_called_once_with(info)
    zeroconf.close.assert_called_once_with()
    assert module.CacheSyncManager.stop.call_count == (2 if cache_failure else 1)
    assert p._service_info is p._zeroconf is p._cache_sync_manager is None
    assert caplog.messages == (
        ["Error closing cache sync manager, continuing shutdown: cache"] if cache_failure else []
    )


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


@pytest.mark.parametrize(
    "failure", [None, "service", "cache", "api", "disconnect", "buffer", "tmcc", "pdi", "state", "gpio"]
)
def test_shutdown_continues_after_individual_failure(runtime, monkeypatch, caplog, failure):
    p = runtime.p
    p._api = True
    queue = p._command_queue = Queue()
    queue.put("pending")
    effects = Mock()
    operations = [
        (p, "shutdown_service", "service"),
        (p, "shutdown_cache", "cache"),
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
        call.cache(),
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
    assert ("Error closing zeroconf, continuing shutdown: service" in caplog.messages) == (failure == "service")
    assert ("Error closing cache sync manager, continuing shutdown: cache" in caplog.messages) == (failure == "cache")


@pytest.mark.parametrize("service_failure", [None, "unregister", "close"])
@pytest.mark.parametrize("cache_failure", [False, True])
def test_shutdown_real_helpers_isolate_failures_and_retry(runtime, monkeypatch, caplog, service_failure, cache_failure):
    p = runtime.p
    p._api = True
    queue = p._command_queue = Queue()
    queue.put("pending")
    info = p._service_info = object()
    zeroconf = p._zeroconf = Mock()
    manager = p._cache_sync_manager = object()
    monkeypatch.setattr(p, "shutdown_service", module.PyTrain.shutdown_service.__get__(p))
    monkeypatch.setattr(p, "shutdown_cache", module.PyTrain.shutdown_cache.__get__(p))
    effects = Mock()
    operations = [
        (zeroconf, "unregister_service", "unregister"),
        (zeroconf, "close", "close"),
        (module.CacheSyncManager, "stop", "cache"),
        (p._tmcc_buffer, "disconnect", "disconnect"),
        (module.CommBuffer, "stop", "buffer"),
        (module.CommandListener, "stop", "tmcc"),
        (module.PdiListener, "stop", "pdi"),
        (module.ComponentStateStore, "reset", "state"),
        (module.GpioHandler, "reset_all", "gpio"),
    ]
    for owner, method, name in operations:
        fails = name == service_failure or (name == "cache" and cache_failure)
        double = Mock(side_effect=[RuntimeError(name), None] if fails else None)
        monkeypatch.setattr(owner, method, double)
        effects.attach_mock(double, name)

    module.PyTrain.shutdown(p)

    downstream = [call.disconnect(5111), call.buffer(), call.tmcc(), call.pdi(), call.state(), call.gpio()]
    service_calls = [call.unregister(info)]
    if service_failure != "unregister":
        service_calls.append(call.close())
    assert effects.mock_calls == service_calls + [call.cache()] + downstream
    assert queue.empty()
    assert queue.unfinished_tasks == 0
    assert p._command_queue is None
    assert p._service_info is (info if service_failure else None)
    assert p._zeroconf is (zeroconf if service_failure else None)
    assert p._cache_sync_manager is (manager if cache_failure else None)
    expected_warnings = []
    if service_failure:
        expected_warnings.append(f"Error closing zeroconf, continuing shutdown: {service_failure}")
    if cache_failure:
        expected_warnings.append("Error closing cache sync manager, continuing shutdown: cache")
    assert caplog.messages == expected_warnings

    effects.reset_mock()
    caplog.clear()
    module.PyTrain.shutdown(p)

    retry_calls = [call.unregister(info), call.close()] if service_failure else []
    if cache_failure:
        retry_calls.append(call.cache())
    assert effects.mock_calls == retry_calls + downstream
    assert p._service_info is p._zeroconf is p._cache_sync_manager is None
    assert p._command_queue is None
    assert not caplog.messages


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


@pytest.mark.parametrize("failure", [None, "unregister", "close"])
def test_service_shutdown_failure_boundaries(runtime, monkeypatch, failure):
    p = runtime.p
    manager = p._cache_sync_manager = Mock()
    info = p._service_info = object()
    zeroconf = p._zeroconf = Mock()
    stop = Mock()
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
        assert p._service_info is p._zeroconf is None
        module.PyTrain.shutdown_service(p)
        zeroconf.close.assert_called_once_with()
        assert p._service_info is p._zeroconf is None
    stop.assert_not_called()
    zeroconf.unregister_service.assert_called_once_with(info)
    assert p._cache_sync_manager is manager
    assert manager.mock_calls == []


@pytest.mark.parametrize("info,zeroconf", [(None, None), (object(), None), (None, Mock())])
def test_service_shutdown_without_registration(runtime, monkeypatch, info, zeroconf):
    p = runtime.p
    manager = p._cache_sync_manager = Mock()
    p._service_info, p._zeroconf = info, zeroconf
    stop = Mock()
    monkeypatch.setattr(module.CacheSyncManager, "stop", stop)
    module.PyTrain.shutdown_service(p)
    stop.assert_not_called()
    assert p._cache_sync_manager is manager
    assert manager.mock_calls == []
    assert p._service_info is info
    assert p._zeroconf is zeroconf
    if zeroconf is not None:
        zeroconf.assert_not_called()
        assert zeroconf.mock_calls == []


def _api_status_for_action(action: module.TMCC1SyncCommandEnum) -> module.PyTrainExitStatus:
    # Deferred upgrade() historically publishes UPDATE to the API host, not UPGRADE.
    if action == module.TMCC1SyncCommandEnum.UPGRADE:
        return module.PyTrainExitStatus.UPDATE
    return module.PyTrainExitStatus.by_name(action.name, raise_exception=True)


def _wire_api_deferred_methods(p, monkeypatch):
    """Match real API deferred methods: set status then raise PyTrainExitException."""

    def install(name, status):
        def method(*_args, **_kwargs):
            p._exit_status = status
            raise module.PyTrainExitException(status)

        monkeypatch.setattr(p, name, method)

    install("upgrade", module.PyTrainExitStatus.UPDATE)
    install("update", module.PyTrainExitStatus.UPDATE)
    install("restart", module.PyTrainExitStatus.RESTART)

    def reboot(reboot=True):
        status = module.PyTrainExitStatus.REBOOT if reboot else module.PyTrainExitStatus.SHUTDOWN
        p._exit_status = status
        raise module.PyTrainExitException(status)

    monkeypatch.setattr(p, "reboot", reboot)


@pytest.mark.parametrize("server", [False, True], ids=["client", "server"])
@pytest.mark.parametrize(
    "action",
    [
        module.TMCC1SyncCommandEnum.UPDATE,
        module.TMCC1SyncCommandEnum.RESTART,
        module.TMCC1SyncCommandEnum.REBOOT,
        module.TMCC1SyncCommandEnum.SHUTDOWN,
        module.TMCC1SyncCommandEnum.UPGRADE,
        module.TMCC1SyncCommandEnum.QUIT,
    ],
)
def test_queued_api_exit_publishes_status_before_one_host_notification(runtime, monkeypatch, server, action):
    p = runtime.p
    p._api = True
    p._api_thread = Mock()
    p._dispatcher = Mock()
    if server:
        p._tmcc_buffer = Mock(spec=module.CommBufferSingleton)
    expected = _api_status_for_action(action)
    _wire_api_deferred_methods(p, monkeypatch)
    monkeypatch.setattr(module.os, "kill", Mock())
    monkeypatch.setattr(module.os, "getpid", lambda: 4321)

    def handle(_cmd):
        p.do_admin_cmd(action)

    if action == module.TMCC1SyncCommandEnum.QUIT:
        # Plain quit is claimed inside _handle_command, not do_admin_cmd.
        p._handle_command = Mock(side_effect=lambda _cmd: module.PyTrain._handle_command(p, "quit"))
    else:
        p._handle_command = Mock(side_effect=handle)
    p._command_queue = Mock(get=Mock(return_value=action.name.lower()))

    observed = []

    def notify_probe(status):
        observed.append(
            {
                "status_arg": status,
                "notified_before": p._api_exit_notified,
                "cache": p._cache_sync_manager,
                "phase": p._lifecycle_phase,
                "action": p._admin_action,
            }
        )
        assert p._api_exit_notified is False
        module.PyTrain._notify_api_exit(p, status)
        assert p.exit_status == status
        assert p._api_exit_notified is True

    monkeypatch.setattr(p, "_notify_api_exit", notify_probe)
    p.shutdown_cache.side_effect = lambda: setattr(p, "_cache_sync_manager", None)

    p.run()

    assert len(observed) == 1
    snapshot = observed[0]
    assert snapshot["status_arg"] == expected
    assert snapshot["cache"] is None
    assert snapshot["action"] == action
    assert snapshot["phase"] == "deferred-action"
    assert p.exit_status == expected
    assert p._api_exit_notified is True
    assert p._admin_action == action
    module.os.kill.assert_called_once_with(4321, module.signal.SIGINT)
    p.shutdown.assert_called_once_with()
    p.shutdown_service.assert_called_once_with()
    p.shutdown_cache.assert_called_once_with()


@pytest.mark.parametrize("server", [False, True], ids=["client", "server"])
def test_queued_api_exit_suppresses_echoes_and_late_actions(runtime, monkeypatch, server):
    p = runtime.p
    p._api = True
    p._api_thread = Mock()
    p._dispatcher = Mock()
    if server:
        p._tmcc_buffer = Mock(spec=module.CommBufferSingleton)
        p._dispatcher.signal_clients.side_effect = lambda *_a, **_k: p(
            module.CommandReq(module.TMCC1SyncCommandEnum.UPDATE)
        )
    else:
        p._tmcc_buffer.enqueue_command.side_effect = lambda *_a, **_k: p(
            module.CommandReq(module.TMCC1SyncCommandEnum.UPDATE)
        )
    _wire_api_deferred_methods(p, monkeypatch)
    monkeypatch.setattr(module.os, "kill", Mock())
    monkeypatch.setattr(module.os, "getpid", lambda: 4321)

    def handle(_cmd):
        p.do_admin_cmd(module.TMCC1SyncCommandEnum.UPDATE)

    p._handle_command = Mock(side_effect=handle)
    p._command_queue = Mock(get=Mock(return_value="update"))

    def during_shutdown():
        # Echo and a different late action during teardown must not notify or replace.
        p(module.CommandReq(module.TMCC1SyncCommandEnum.UPDATE))
        p(module.CommandReq(module.TMCC1SyncCommandEnum.RESTART))
        try:
            p.do_admin_cmd(module.TMCC1SyncCommandEnum.SHUTDOWN)
        except KeyboardInterrupt:
            pytest.fail("late local exit raised a redundant interrupt")

    p.shutdown.side_effect = during_shutdown
    p.run()

    assert p._admin_action == module.TMCC1SyncCommandEnum.UPDATE
    assert p.exit_status == module.PyTrainExitStatus.UPDATE
    assert p._api_exit_notified is True
    module.os.kill.assert_called_once_with(4321, module.signal.SIGINT)


@pytest.mark.parametrize("stage", ["shutdown", "shutdown_cache"])
@pytest.mark.parametrize("error", [KeyboardInterrupt, RuntimeError])
def test_queued_api_exit_skips_notification_when_cleanup_escapes(runtime, monkeypatch, stage, error):
    p = runtime.p
    p._api = True
    p._api_thread = Mock()
    p._dispatcher = Mock()
    p._tmcc_buffer = Mock(spec=module.CommBufferSingleton)
    monkeypatch.setattr(module.os, "kill", Mock())
    p._handle_command = Mock(side_effect=lambda _cmd: p.do_admin_cmd(module.TMCC1SyncCommandEnum.UPDATE))
    p._command_queue = Mock(get=Mock(return_value="update"))
    getattr(p, stage).side_effect = error("cleanup failed")
    with pytest.raises(error, match="cleanup failed"):
        p.run()
    assert p.exit_status is None
    assert p._api_exit_notified is False
    module.os.kill.assert_not_called()
    p.update.assert_not_called()


def test_queued_api_exit_skips_notification_when_deferred_action_fails(runtime, monkeypatch):
    p = runtime.p
    p._api = True
    p._api_thread = Mock()
    p._dispatcher = Mock()
    monkeypatch.setattr(module.os, "kill", Mock())
    p._handle_command = Mock(side_effect=lambda _cmd: p.do_admin_cmd(module.TMCC1SyncCommandEnum.UPDATE))
    p._command_queue = Mock(get=Mock(return_value="update"))
    p.update.side_effect = RuntimeError("update failed")
    with pytest.raises(RuntimeError, match="update failed"):
        p.run()
    assert p.exit_status is None
    assert p._api_exit_notified is False
    module.os.kill.assert_not_called()


def test_callback_only_api_exit_still_notifies_once(runtime, monkeypatch):
    p = runtime.p
    p._api = True
    p._api_thread = Mock()
    monkeypatch.setattr(module.os, "kill", Mock())
    monkeypatch.setattr(module.os, "getpid", lambda: 4321)
    # Callback-only path: no queued command; host notification happens in __call__.
    p._command_queue = Mock(get=Mock(side_effect=KeyboardInterrupt))
    p(module.CommandReq(module.TMCC1SyncCommandEnum.RESTART))
    assert p.exit_status == module.PyTrainExitStatus.RESTART
    assert p._api_exit_notified is True
    module.os.kill.assert_called_once_with(4321, module.signal.SIGINT)
    p.shutdown.assert_called_once_with()
    # run() then exits without a second notification.
    p.run()
    module.os.kill.assert_called_once_with(4321, module.signal.SIGINT)
    assert p.exit_status == module.PyTrainExitStatus.RESTART
