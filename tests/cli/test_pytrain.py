import logging
import os
import sys
from unittest.mock import call

import pytest

import src.pytrain as package
from src.pytrain.cli import pytrain as module
from src.pytrain.cli.pytrain import PyTrain, PyTrainExitException, PyTrainExitStatus
from src.pytrain.utils.singleton import _SingletonMeta
from .conftest import isolated_pytrain_state


@pytest.mark.parametrize(
    "args,base,port,ser2",
    [
        (["-base", "192.0.2.30"], "192.0.2.30", module.DEFAULT_BASE_PORT, False),
        (["-base", "192.0.2.30:6000", "-ser2"], "192.0.2.30", "6000", True),
        (["-base"], "192.0.2.30", module.DEFAULT_BASE_PORT, False),
        (["-ser2"], None, None, True),
    ],
)
def test_server_startup(pytrain_startup, args, base, port, ser2):
    d = pytrain_startup
    pt = d.initialize(args)
    assert pt.is_server and not pt.is_client
    assert pt._client is False
    assert (pt._base_addr, pt._base_port) == (base, port)
    assert pt._is_base is (base is not None)
    assert pt._is_ser2 is ser2
    d.build.assert_called_once_with(baudrate=module.DEFAULT_BAUDRATE, port=module.DEFAULT_PORT, server=None, ser2=ser2)
    d.listen.assert_called_once_with(
        baudrate=module.DEFAULT_BAUDRATE,
        port=str(module.DEFAULT_PORT),
        ser2_receiver=ser2,
        base3_receiver=base is not None,
        server_port=module.DEFAULT_SERVER_PORT,
    )
    d.receiver.assert_called_once_with(d.server_buffer, module.DEFAULT_SERVER_PORT)
    listeners = (d.listener, d.pdi) if base else (d.listener,)
    d.store.assert_called_once_with(listeners=listeners, is_base=base is not None, is_ser2=ser2)
    if base:
        d.pdi_build.assert_called_once_with(base, int(port))
        d.roster.assert_called_once_with(is_startup=True)
        assert d.server_buffer.is_use_base3 is True
    else:
        d.pdi_build.assert_not_called()
        d.roster.assert_not_called()
    assert d.server_buffer.base3_address == base
    d.discovery.assert_not_called()
    assert d.base_discovery.call_count == (args == ["-base"])
    d.client_listen.assert_not_called()
    assert PyTrain.current() is pt
    assert pt._initialized
    d.run.assert_called_once_with()
    d.thread.assert_not_called()


@pytest.mark.parametrize("explicit", [False, True])
def test_client_startup(pytrain_startup, explicit):
    d = pytrain_startup
    args = ["-server", "192.0.2.10", "-server_port", "6001"] if explicit else ["-client"]
    pt = d.initialize(args)
    port = 6001 if explicit else 5110
    assert pt.is_client and not pt.is_server
    assert str(pt._server) == "192.0.2.10"
    assert pt._server_ips == {pt._server}
    assert pt._port == port
    assert pt._client_ip == "192.0.2.20"
    d.build.assert_called_once_with(baudrate=module.DEFAULT_BAUDRATE, port=port, server=pt._server, ser2=False)
    assert d.discovery.call_count == (not explicit)
    d.client_listen.assert_called_once_with()
    d.store.assert_called_once_with(listeners=(d.client_listener,), is_base=False, is_ser2=False)
    d.listen.assert_not_called()
    d.receiver.assert_not_called()
    d.pdi_build.assert_not_called()
    d.roster.assert_not_called()
    d.client_listener.subscribe.assert_called_once_with(pt, module.CommandScope.SYNC)
    assert pt.store.listen_for.call_args_list == [
        call(scope)
        for scope in (
            module.CommandScope.BASE,
            module.CommandScope.ENGINE,
            module.CommandScope.TRAIN,
            module.CommandScope.SWITCH,
            module.CommandScope.ROUTE,
            module.CommandScope.ACC,
            module.CommandScope.IRDA,
            module.CommandScope.SYNC,
            module.CommandScope.BLOCK,
        )
    ]
    assert pt.command_dispatcher is d.dispatcher.return_value
    assert pt._pdi_state_store is d.pdi_store.return_value
    assert pt._cache_sync_port == module.default_cache_sync_port(pt._args.server_port)
    assert pt._cache_sync_enabled and not pt._cache_sync_started
    assert pt._cache_sync_manager is None
    d.debug.assert_not_called()
    d.echo.assert_not_called()


def test_startup_options_and_api_handoff(pytrain_startup):
    d = pytrain_startup
    pt = d.initialize(
        [
            "-ser2",
            "-api",
            "-debug",
            "-echo",
            "-headless",
            "-no_wait",
            "-no_d4",
            "-force_sync",
            "-no_cache_sync",
            "-cache_sync_port",
            "6200",
            "-port",
            "/dev/test",
            "-baudrate",
            "19200",
            "-buttons_file",
            "Buttons.py",
            "-replay_file",
            "Replay.txt",
        ]
    )
    assert (pt._buttons_file, pt._replay_file) == ("Buttons.py", "Replay.txt")
    assert pt._headless and pt._no_wait and pt._no_d4 and pt._force_sync
    assert pt._debug and pt._echo
    assert not pt._cache_sync_enabled
    assert pt._cache_sync_port == pt._server_cache_sync_port == 6200
    assert pt._port == "/dev/test" and pt._baudrate == 19200
    assert pt.is_api and pt.is_api_active
    assert pt._command_queue.maxsize == module.DEFAULT_QUEUE_SIZE
    assert pt._command_queue.empty()
    d.thread.assert_called_once_with(target=pt.run, daemon=True)
    d.thread.return_value.start.assert_called_once_with()
    d.run.assert_not_called()
    d.debug.assert_called_once_with()
    d.echo.assert_called_once_with()
    assert not pt._command_processor_ev.is_set()
    assert not pt._command_processor_available.is_set()


@pytest.mark.parametrize("args", [None, []])
def test_startup_uses_process_arguments(pytrain_startup, monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["pytrain", "-ser2"])
    assert pytrain_startup.initialize(args).is_server


@pytest.mark.parametrize(
    "args,dependency,error,text",
    [
        (["-base"], "base_discovery", AttributeError, "could not find a Lionel Base"),
        (["-client"], "discovery", RuntimeError, "No PyTrain server"),
    ],
)
def test_discovery_failure_precedes_services(pytrain_startup, args, dependency, error, text):
    d = pytrain_startup
    getattr(d, dependency).return_value = None
    with pytest.raises(error, match=text):
        d.initialize(args)
    d.build.assert_not_called()
    d.run.assert_not_called()
    assert PyTrain.current(False) is None


def test_transport_failure_does_not_register_current(pytrain_startup):
    d = pytrain_startup
    d.build.side_effect = OSError("serial unavailable")
    with pytest.raises(OSError, match="serial unavailable"):
        d.initialize(["-ser2"])
    d.store.assert_not_called()
    d.run.assert_not_called()
    assert PyTrain.current(False) is None


def test_current_before_initialization(bare_pytrain):
    assert PyTrain.current(False) is None
    with pytest.raises(RuntimeError, match="current.*before.*created"):
        PyTrain.current()
    PyTrain._current = bare_pytrain
    assert PyTrain.current() is PyTrain.current(False) is bare_pytrain


def test_parser_defaults(bare_pytrain):
    args = PyTrain.command_line_parser().parse_args([])
    assert args.client and args.base is None and args.server is None
    assert args.baudrate == module.DEFAULT_BAUDRATE
    assert args.port == module.DEFAULT_PORT
    assert args.server_port == module.DEFAULT_SERVER_PORT
    assert args.cache_sync_port is None
    assert args.buttons_file is args.replay_file is None
    for option in ("api", "ser2", "debug", "echo", "headless", "force_sync", "no_cache_sync", "no_d4", "no_wait"):
        assert getattr(args, option) is False


@pytest.mark.parametrize(
    "args",
    [
        ["-base", "-client"],
        ["-server", "192.0.2.10", "-base"],
        ["-client", "-server", "192.0.2.10"],
        ["-baudrate", "123"],
        ["-server_port", "invalid"],
        ["-cache_sync_port", "invalid"],
        ["-unknown"],
    ],
)
def test_parser_rejects_invalid_options(bare_pytrain, args):
    with pytest.raises(SystemExit) as exc:
        PyTrain.command_line_parser().parse_args(args)
    assert exc.value.code == 2


@pytest.mark.parametrize("packaged", [False, True])
@pytest.mark.parametrize("extended", [False, True])
def test_parser_version_and_optional_files(bare_pytrain, monkeypatch, capsys, packaged, extended):
    monkeypatch.setattr(package, "is_package", lambda: packaged)
    monkeypatch.setattr(package, "get_version", lambda: "9.8.7")
    parser = bare_pytrain.command_line_parser_ex() if extended else PyTrain.command_line_parser()
    assert parser.prog == ("pytrain" if packaged else "pytrain.py")
    args = parser.parse_args(["-buttons_file", "-replay_file", "-base"])
    assert args.buttons_file == module.DEFAULT_BUTTONS_FILE
    assert args.replay_file == module.DEFAULT_REPLAY_FILE
    assert args.base == []
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["-version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "PyTrain 9.8.7"


@pytest.mark.parametrize(
    "args,role,base",
    [(["-ser2"], "Server", None), (["-base", "192.0.2.30"], "Server", "192.0.2.30"), (["-client"], "Client", None)],
)
def test_basic_properties_and_representation(pytrain_startup, monkeypatch, args, role, base):
    d = pytrain_startup
    pt = d.initialize(args)
    monkeypatch.setattr(module, "timer", lambda: pt._started_at + 65)
    monkeypatch.setattr(module, "get_native_id", lambda: 123)
    assert repr(pt) == f"<PyTrain {role} 0:01:05>"
    assert pt.tid == 123
    assert pt.exit_status is None
    assert pt.store is d.store.return_value
    assert pt.tmcc_buffer is (d.server_buffer if role == "Server" else d.client_buffer)
    assert pt.base3_ip_addr == base
    assert pt.pdi_listener is (d.pdi if base else pt._tmcc_listener)
    assert pt.pdi_dispatcher is (d.pdi if base else pt.tmcc_buffer)
    assert not pt.is_api and not pt.is_api_active
    expected = f"PyTrain {role} 9.8.7"
    if role == "Client":
        expected += "; Server v1.2.3 @192.0.2.10"
    if base:
        expected += f"; Base 3 @{base}"
    assert pt.version == expected


def test_client_base_address_and_version_without_server(pytrain_startup):
    pt = pytrain_startup.initialize(["-client"])
    pt._server = None
    pt.tmcc_buffer.base3_address = "192.0.2.30"
    assert pt.base3_ip_addr == "192.0.2.30"
    assert pt.version == "PyTrain Client 9.8.7; Base 3 @192.0.2.30"
    pt._tmcc_buffer = None
    assert pt.base3_ip_addr is None


@pytest.mark.parametrize(
    "api,queue,thread,expected",
    [
        (False, None, None, False),
        (True, None, None, False),
        (True, object(), None, False),
        (True, object(), object(), True),
    ],
)
def test_api_active_requires_all_components(bare_pytrain, api, queue, thread, expected):
    bare_pytrain._api, bare_pytrain._command_queue, bare_pytrain._api_thread = api, queue, thread
    assert bare_pytrain.is_api_active is expected


@pytest.mark.parametrize(
    "status,value",
    [
        (PyTrainExitStatus.QUIT, 0),
        (PyTrainExitStatus.REBOOT, 11),
        (PyTrainExitStatus.RESTART, 12),
        (PyTrainExitStatus.SHUTDOWN, 13),
        (PyTrainExitStatus.UPDATE, 14),
        (PyTrainExitStatus.UPGRADE, 15),
    ],
)
def test_exit_status_and_exception(status, value):
    assert status.value == value
    assert PyTrainExitStatus.by_name(status.name) is status
    error = PyTrainExitException(status)
    assert error.reason is status
    assert str(error) == f"PyTrain Exiting: {status.name}"
    with pytest.raises(PyTrainExitException) as exc:
        raise error
    assert exc.value is error


def test_isolation_restores_state_after_exception():
    current = PyTrain._current
    instances, events = _SingletonMeta._instances, _SingletonMeta._init_done
    argv, contents, environment = sys.argv, sys.argv[:], dict(os.environ)
    root = logging.getLogger()
    level, handlers = root.level, root.handlers[:]
    handler_levels = [handler.level for handler in handlers]
    with pytest.raises(RuntimeError, match="fixture teardown"):
        with isolated_pytrain_state():
            PyTrain._current = object()
            _SingletonMeta._instances[PyTrain] = object()
            _SingletonMeta._init_done[PyTrain] = object()
            sys.argv.append("-debug")
            os.environ["PYTRAIN_ISOLATION_TEST"] = "changed"
            root.setLevel(logging.CRITICAL)
            for handler in root.handlers:
                handler.setLevel(logging.ERROR)
            root.addHandler(logging.NullHandler())
            raise RuntimeError("fixture teardown")
    assert PyTrain._current is current
    assert _SingletonMeta._instances is instances and _SingletonMeta._init_done is events
    assert sys.argv is argv and sys.argv == contents
    assert dict(os.environ) == environment
    assert root.level == level and root.handlers == handlers
    assert [handler.level for handler in handlers] == handler_levels
