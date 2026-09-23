import signal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from src.pytrain.cli import pytrain as mod
from src.pytrain.comm.comm_buffer import CommBufferProxy


@pytest.fixture(params=[False, True], ids=["client", "server"])
def admin(request, bare_pytrain, monkeypatch):
    obj = bare_pytrain
    obj._tmcc_buffer = Mock(spec=mod.CommBufferSingleton if request.param else CommBufferProxy)
    obj._api = False
    obj._api_thread = None
    obj._echo = obj._debug = False
    obj._exit_status = None
    obj._admin_action = None
    obj._received_admin_cmds = set()
    obj._command_processor_available = Mock()
    obj._server_ips = ["192.0.2.1"]
    obj._client_ip = "192.0.2.2"
    obj._port = 5110
    obj._dispatcher = Mock()
    obj._get_system_state = Mock()
    obj.shutdown = Mock()
    for owner, name in [(mod.os, "kill"), (mod.os, "execv"), (mod.subprocess, "run"), (mod, "sleep"), (mod, "Thread")]:
        monkeypatch.setattr(owner, name, Mock())
    monkeypatch.setattr(mod.os, "getpid", lambda: 1234)
    return obj


@pytest.mark.parametrize("command", list(mod.ACTION_TO_ADMIN_COMMAND_MAP))
@pytest.mark.parametrize("api", [False, True])
def test_callback_admin_deduplication(admin, command, api):
    admin._api = api
    admin._api_thread = Mock() if api else None
    message = mod.CommandReq(command)
    admin(message)
    admin(message)
    assert admin._command_processor_available.wait.call_count == (0 if admin.is_server else 2)
    if command == mod.TMCC1SyncCommandEnum.RESYNC:
        assert admin._admin_action is None
        mod.os.kill.assert_not_called()
        if admin.is_server:
            assert mod.Thread.call_args_list == [call(target=admin._get_system_state, daemon=True)] * 2
            assert mod.Thread.return_value.start.call_count == 2
        else:
            mod.Thread.assert_not_called()
    else:
        assert admin._admin_action == command
        assert admin._received_admin_cmds == {command}
        mod.os.kill.assert_called_once_with(1234, signal.SIGINT)
        assert admin.shutdown.call_count == int(api)
        assert admin.exit_status == (
            mod.PyTrainExitStatus.by_name(command.name, raise_exception=False) if api else None
        )


@pytest.mark.parametrize("echo_error", [False, True])
def test_callback_echo_non_admin(admin, monkeypatch, echo_error):
    admin._echo = True
    info = Mock(side_effect=ValueError("console unavailable") if echo_error else None)
    exception = Mock()
    monkeypatch.setattr(mod.log, "info", info)
    monkeypatch.setattr(mod.log, "exception", exception)
    message = SimpleNamespace(command=None)
    admin(message)
    assert str(message) in info.call_args.args[0]
    assert exception.call_count == int(echo_error)
    mod.os.kill.assert_not_called()


@pytest.mark.parametrize("target,port", [("192.0.2.9", 5110), ("192.0.2.9:5222", 5222)])
@pytest.mark.parametrize("dispatcher", [False, True])
def test_targeted_admin(admin, target, port, dispatcher):
    sender = admin._dispatcher
    if not dispatcher:
        admin._dispatcher = None
    admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.QUIT, [target])
    assert admin._admin_action is None
    if dispatcher:
        args, kwargs = sender.signal_clients.call_args
        assert args[0].command == mod.TMCC1SyncCommandEnum.QUIT
        assert kwargs == {"client": "192.0.2.9", "port": port}
    else:
        sender.signal_clients.assert_not_called()
    admin._tmcc_buffer.enqueue_command.assert_not_called()


def test_invalid_target_port(admin):
    with pytest.raises(ValueError):
        admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.QUIT, ["192.0.2.9:bad"])
    assert admin._admin_action is None


@pytest.mark.parametrize("args", [None, [], ["192.0.2.1"], ["me"]])
@pytest.mark.parametrize("command", [mod.TMCC1SyncCommandEnum.QUIT, mod.TMCC1SyncCommandEnum.RESYNC])
def test_admin_broadcast_and_local_routing(admin, args, command):
    local_client = not admin.is_server and args == ["me"]
    if command == mod.TMCC1SyncCommandEnum.RESYNC or local_client:
        admin.do_admin_cmd(command, args)
    else:
        with pytest.raises(KeyboardInterrupt):
            admin.do_admin_cmd(command, args)
    expected_action = None if command == mod.TMCC1SyncCommandEnum.RESYNC or local_client else command
    assert admin._admin_action == expected_action
    if admin.is_server:
        admin._tmcc_buffer.enqueue_command.assert_not_called()
        if command == mod.TMCC1SyncCommandEnum.RESYNC:
            admin._get_system_state.assert_called_once_with()
            admin._dispatcher.signal_clients.assert_not_called()
        else:
            assert admin._dispatcher.signal_clients.call_args.args[0].command == command
    else:
        payload = mod.CommandReq(command).as_bytes
        admin._tmcc_buffer.enqueue_command.assert_called_once_with(
            payload + (admin._client_ip.encode() if local_client else b"")
        )


def test_client_on_server_host(admin):
    if admin.is_server:
        admin._server_ips = []
        with pytest.raises(KeyboardInterrupt):
            admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.QUIT, ["elsewhere"])
        admin._dispatcher.signal_clients.assert_called_once()
    else:
        admin._client_ip = admin._server_ips[0]
        admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.QUIT, ["me"])
        admin._tmcc_buffer.enqueue_command.assert_called_once_with(
            mod.CommandReq(mod.TMCC1SyncCommandEnum.QUIT).as_bytes
        )
    assert admin._admin_action == mod.TMCC1SyncCommandEnum.QUIT


@pytest.mark.parametrize("interrupt", [False, True])
def test_restart(admin, monkeypatch, interrupt):
    monkeypatch.setattr(mod.log, "info", Mock(side_effect=KeyboardInterrupt if interrupt else None))
    admin.relaunch = Mock()
    admin.restart()
    admin.relaunch.assert_called_once_with(mod.PyTrainExitStatus.RESTART)


@pytest.mark.parametrize("status", list(mod.PyTrainExitStatus))
def test_relaunch_api(admin, monkeypatch, status):
    admin._api = True
    monkeypatch.setattr(mod.random, "randint", Mock(return_value=9))
    with pytest.raises(mod.PyTrainExitException):
        admin.relaunch(status)
    assert admin.exit_status == status
    assert mod.sleep.call_args_list == ([] if admin.is_server else [call(9)])
    mod.os.execv.assert_not_called()
    mod.subprocess.run.assert_not_called()


@pytest.mark.parametrize("linux,returncode", [(False, 0), (True, 0), (True, 3)])
def test_service_detection(admin, monkeypatch, linux, returncode):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: linux)
    mod.subprocess.run.return_value.returncode = returncode
    assert admin.is_service == (linux and returncode == 0)
    if linux:
        role = "server" if admin.is_server else "client"
        mod.subprocess.run.assert_called_once_with(
            ["systemctl", "is-active", "--quiet", f"pytrain_{role}.service"], check=False
        )
    else:
        mod.subprocess.run.assert_not_called()


def test_service_relaunch(admin, monkeypatch):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: True)
    mod.subprocess.run.return_value.returncode = 0
    admin.relaunch(mod.PyTrainExitStatus.RESTART, delay=False)
    role = "server" if admin.is_server else "client"
    assert mod.subprocess.run.call_args_list[-1] == call(
        ["sudo", "systemctl", "restart", f"pytrain_{role}.service"], check=False
    )
    mod.os.execv.assert_not_called()
    mod.sleep.assert_not_called()


@pytest.mark.parametrize("enabled,present", [(False, False), (False, True), (True, False), (True, True)])
def test_command_line_relaunch_preserves_arguments(admin, monkeypatch, enabled, present):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: False)
    original = ["/bin/pytrain", "-server", "192.0.2.1"]
    monkeypatch.setattr(mod.sys, "argv", original + (["-echo", "-debug"] if present else []))
    admin._echo = admin._debug = enabled
    admin.relaunch(mod.PyTrainExitStatus.RESTART, delay=False)
    expected = original + (["-echo", "-debug"] if enabled else [])
    mod.os.execv.assert_called_once_with(original[0], expected)
    assert mod.sys.argv == expected
    mod.sleep.assert_not_called()


def test_callback_records_action_and_shuts_down_before_interrupt(admin):
    admin._api = True
    admin._api_thread = Mock()

    def interrupt(pid, sig):
        assert (pid, sig) == (1234, signal.SIGINT)
        assert admin._admin_action == mod.TMCC1SyncCommandEnum.RESTART
        assert admin.exit_status == mod.PyTrainExitStatus.RESTART
        admin.shutdown.assert_called_once_with()
        raise KeyboardInterrupt

    mod.os.kill.side_effect = interrupt
    with pytest.raises(KeyboardInterrupt):
        admin(mod.CommandReq(mod.TMCC1SyncCommandEnum.RESTART))


@pytest.mark.parametrize("command", [mod.TMCC1SyncCommandEnum.UPDATE, mod.TMCC1SyncCommandEnum.RESTART])
@pytest.mark.parametrize("api", [False, True])
def test_local_exit_suppresses_immediate_and_late_echoes(admin, command, api):
    admin._api = api
    admin._api_thread = Mock() if api else None
    dispatch = admin._dispatcher.signal_clients if admin.is_server else admin._tmcc_buffer.enqueue_command
    dispatch.side_effect = lambda *args: admin(mod.CommandReq(command))
    with pytest.raises(KeyboardInterrupt):
        admin.do_admin_cmd(command)
    admin._shutdown_started = True
    for late in [command, mod.TMCC1SyncCommandEnum.SHUTDOWN]:
        admin(mod.CommandReq(late))
        try:
            admin.do_admin_cmd(late)
        except KeyboardInterrupt:
            pytest.fail("Late local exit raised a redundant interrupt")
    assert admin._admin_action == command
    assert admin._received_admin_cmds == {command}
    dispatch.assert_called_once()
    admin.shutdown.assert_not_called()
    mod.os.kill.assert_not_called()


def test_simultaneous_exiting_callbacks_accept_one_action(admin):
    barrier = Barrier(2)

    def callback(command):
        barrier.wait(timeout=2)
        admin(mod.CommandReq(command))

    commands = [mod.TMCC1SyncCommandEnum.UPDATE, mod.TMCC1SyncCommandEnum.RESTART]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(callback, commands))
    assert admin._admin_action in commands
    assert admin._received_admin_cmds == {admin._admin_action}
    mod.os.kill.assert_called_once_with(1234, signal.SIGINT)


def test_failed_local_dispatch_can_be_retried(admin):
    dispatch = admin._dispatcher.signal_clients if admin.is_server else admin._tmcc_buffer.enqueue_command
    dispatch.side_effect = OSError("dispatch failed")
    with pytest.raises(OSError, match="dispatch failed"):
        admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.UPDATE)
    assert admin._admin_action is None
    assert not admin._received_admin_cmds
    assert not admin._exit_requested
    dispatch.side_effect = None
    admin(mod.CommandReq(mod.TMCC1SyncCommandEnum.RESTART))
    assert admin._admin_action == mod.TMCC1SyncCommandEnum.RESTART
    mod.os.kill.assert_called_once()


@pytest.mark.parametrize("same_host", [False, True])
def test_client_me_waits_for_callback(admin, same_host):
    if admin.is_server:
        return
    if same_host:
        admin._client_ip = admin._server_ips[0]
    admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.UPDATE, ["me"])
    assert not admin._exit_requested
    admin(mod.CommandReq(mod.TMCC1SyncCommandEnum.UPDATE))
    assert admin._admin_action == mod.TMCC1SyncCommandEnum.UPDATE
    mod.os.kill.assert_called_once()


def test_routing_cannot_replace_committed_action(admin):
    admin(mod.CommandReq(mod.TMCC1SyncCommandEnum.UPDATE))
    admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.RESYNC)
    admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.QUIT, ["192.0.2.9"])
    if admin.is_client:
        admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.RESTART, ["me"])
    assert admin._admin_action == mod.TMCC1SyncCommandEnum.UPDATE
    mod.os.kill.assert_called_once()


def test_shutdown_suppresses_unclaimed_callback(admin, monkeypatch):
    admin.shutdown_service = Mock()
    admin.shutdown_cache = Mock()
    admin._cache_sync_manager = None
    admin._tmcc_listener = Mock(port=None)
    for owner, name in [
        (mod.CommBuffer, "stop"),
        (mod.CommandListener, "stop"),
        (mod.PdiListener, "stop"),
        (mod.ComponentStateStore, "reset"),
        (mod.GpioHandler, "reset_all"),
    ]:
        monkeypatch.setattr(owner, name, Mock())
    mod.PyTrain.shutdown(admin)
    admin(mod.CommandReq(mod.TMCC1SyncCommandEnum.UPDATE))
    assert admin._admin_action is None
    mod.os.kill.assert_not_called()


def test_signal_diagnostic_precedes_send(admin, caplog):
    caplog.set_level("DEBUG", logger=mod.log.name)

    def sent(*args):
        message = caplog.records[-1].getMessage()
        assert "Sending internal SIGINT" in message
        for value in [
            "action=UPDATE",
            "source=callback",
            "selected=UPDATE",
            "phase=running",
            "pid=1234",
            f"pytrain={id(admin):#x}",
            "thread=",
        ]:
            assert value in message

    mod.os.kill.side_effect = sent
    admin(mod.CommandReq(mod.TMCC1SyncCommandEnum.UPDATE))
    mod.os.kill.assert_called_once()


def test_api_callback_notification_is_one_shot(admin, caplog):
    admin._api = True
    admin._api_thread = Mock()
    caplog.set_level("DEBUG", logger=mod.log.name)

    def observe(pid, sig):
        assert (pid, sig) == (1234, signal.SIGINT)
        assert admin.exit_status == mod.PyTrainExitStatus.UPDATE
        assert admin._api_exit_notified is True
        assert any("Sending API exit notification status=UPDATE" in r.getMessage() for r in caplog.records)

    mod.os.kill.side_effect = observe
    admin(mod.CommandReq(mod.TMCC1SyncCommandEnum.UPDATE))
    admin._notify_api_exit(mod.PyTrainExitStatus.RESTART)
    admin(mod.CommandReq(mod.TMCC1SyncCommandEnum.RESTART))
    assert admin.exit_status == mod.PyTrainExitStatus.UPDATE
    assert admin._admin_action == mod.TMCC1SyncCommandEnum.UPDATE
    mod.os.kill.assert_called_once_with(1234, signal.SIGINT)
    admin.shutdown.assert_called_once_with()
    assert "Suppressed API exit notification" in caplog.text


def test_local_api_exit_does_not_notify_until_handoff(admin):
    admin._api = True
    admin._api_thread = Mock()
    with pytest.raises(KeyboardInterrupt):
        admin.do_admin_cmd(mod.TMCC1SyncCommandEnum.UPDATE)
    assert admin._admin_action == mod.TMCC1SyncCommandEnum.UPDATE
    assert admin.exit_status is None
    assert admin._api_exit_notified is False
    admin.shutdown.assert_not_called()
    mod.os.kill.assert_not_called()

    observed = []

    def observe(pid, sig):
        observed.append((admin.exit_status, admin._api_exit_notified))
        assert (pid, sig) == (1234, signal.SIGINT)

    mod.os.kill.side_effect = observe
    admin._notify_api_exit(mod.PyTrainExitStatus.UPDATE)
    assert observed == [(mod.PyTrainExitStatus.UPDATE, True)]
    assert admin.exit_status == mod.PyTrainExitStatus.UPDATE
    mod.os.kill.assert_called_once_with(1234, signal.SIGINT)


@pytest.mark.parametrize("service", [False, True])
def test_relaunch_os_errors_propagate(admin, monkeypatch, service):
    monkeypatch.setattr("src.pytrain.is_linux", lambda: service)
    monkeypatch.setattr(mod.sys, "argv", ["/bin/pytrain"])
    if service:
        mod.subprocess.run.side_effect = [SimpleNamespace(returncode=0), OSError("restart failed")]
    else:
        mod.os.execv.side_effect = OSError("restart failed")
    with pytest.raises(OSError, match="restart failed"):
        admin.relaunch(mod.PyTrainExitStatus.RESTART, delay=False)
    mod.sleep.assert_not_called()
