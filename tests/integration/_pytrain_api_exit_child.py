"""One canonical-import lifecycle per process; never collected by pytest."""

import asyncio
from contextlib import ExitStack
import importlib
import json
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
from unittest import TestCase
from unittest.mock import Mock, patch


class Relaunched(BaseException):
    """A successful exec never returns to the host's outer dispatcher."""


def main():
    checkout = Path(sys.argv[1]).resolve()
    role, route, action_name, scenario = sys.argv[2:]
    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root / "src"), str(checkout / "src")]
    events = []
    real_kill = os.kill
    real_thread_start = threading.Thread.start

    def forbidden(*args, **kwargs):
        raise AssertionError(f"Unexpected external side effect: {args!r} {kwargs!r}")

    with ExitStack() as stack:

        def replace(owner, name, value):
            return stack.enter_context(patch.object(owner, name, value))

        # Do not consult the developer's dotenv files or inherited API credentials.
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "SECRET_KEY": "integration-only-not-a-production-secret",
                    "SECRET_PHRASE": "INTEGRATION",
                    "API_TOKEN": "integration-only-token",
                    "ALGORITHM": "HS256",
                    "API_SERVER": "https://api.invalid",
                    "ALEXA_TOKEN_EXP_MIN": "15",
                    "UNSECURE_TOKENS": "",
                },
            )
        )
        import dotenv

        replace(dotenv, "find_dotenv", lambda *a, **kw: "synthetic.env")
        replace(dotenv, "load_dotenv", lambda *a, **kw: False)
        replace(os, "system", forbidden)
        replace(os, "execv", forbidden)
        replace(os, "kill", forbidden)
        replace(subprocess, "Popen", forbidden)
        replace(socket.socket, "connect", forbidden)
        replace(socket.socket, "bind", forbidden)
        # luma creates a hardware-rendering pool during import; keep it inert too.
        replace(threading.Thread, "start", Mock())

        import pytrain
        from pytrain.cli import pytrain as pt
        from pytrain.comm.comm_buffer import CommBufferProxy
        from pytrain_api import pytrain_api as api
        import uvicorn

        def check_origin(module, directory):
            origin = Path(module.__file__).resolve()
            assert origin.is_relative_to(directory), (module.__name__, origin, directory)
            return str(origin)

        origins = {
            "pytrain": check_origin(pytrain, root / "src/pytrain"),
            "lifecycle": check_origin(pt, root / "src/pytrain"),
            "api": check_origin(api, checkout / "src/pytrain_api"),
        }
        assert api.PyTrain is pytrain.PyTrain is pt.PyTrain
        assert api.PyTrainExitStatus is pytrain.PyTrainExitStatus is pt.PyTrainExitStatus
        enum_module = importlib.import_module(pt.PyTrainExitStatus.__module__)
        origins["status"] = check_origin(enum_module, root / "src/pytrain")
        print(json.dumps({"origins": origins, "python": sys.version, "uvicorn": uvicorn.__version__}), flush=True)

        action = pt.TMCC1SyncCommandEnum[action_name]
        expected_name = "UPDATE" if route == "queued" and action_name == "UPGRADE" else action_name
        expected = pt.PyTrainExitStatus[expected_name]
        buffer = Mock(spec=pt.CommBufferSingleton if role == "server" else CommBufferProxy)
        listener = Mock(spec=pt.CommandListener if role == "server" else pt.ClientStateListener)
        listener.port = 5111
        if role == "client":
            buffer.server_ip.return_value = "192.0.2.20"
            listener.update_client_if_needed.return_value = False
        dispatcher = Mock()
        replace(pt.CommBuffer, "build", Mock(return_value=buffer))
        replace(pt.CommandListener, "build", Mock(return_value=listener))
        replace(pt.ClientStateListener, "build", Mock(return_value=listener))
        replace(pt.CommandDispatcher, "get", Mock(return_value=dispatcher))
        replace(pt, "EnqueueProxyRequests", Mock())
        replace(pt, "ComponentStateStore", Mock())
        replace(pt, "PdiStateStore", Mock())
        replace(pt, "Thread", Mock())
        replace(pt, "Zeroconf", Mock())
        replace(pt.PyTrain, "register_service", Mock(return_value=object()))
        replace(pt.PyTrain, "get_service_info", Mock(return_value=("192.0.2.10", 5110)))
        replace(pt.PyTrain, "_load_client_state", Mock())
        replace(pt, "sleep", Mock())
        replace(api, "sleep", Mock())
        replace(api, "is_linux", lambda: False)
        replace(api, "is_package", lambda: False)
        replace(api.PyTrainApi, "write_env", forbidden)
        replace(pt.socket, "gethostbyname", lambda host: host)
        replace(pt.readline, "set_auto_history", Mock())

        def echo(*args, **kwargs):
            p = pt.PyTrain.current()
            p(pt.CommandReq(action))
            p(
                pt.CommandReq(
                    pt.TMCC1SyncCommandEnum.RESTART if action_name != "RESTART" else pt.TMCC1SyncCommandEnum.UPDATE
                )
            )

        dispatcher.signal_clients.side_effect = echo
        buffer.enqueue_command.side_effect = echo
        if role == "client":
            buffer.disconnect.side_effect = lambda *a: events.append("disconnect")
        for owner, name, event in [
            (pt.CommBuffer, "stop", "buffer-stop"),
            (pt.CommandListener, "stop", "listener-stop"),
            (pt.PdiListener, "stop", "pdi-stop"),
            (pt.ComponentStateStore, "reset", "store-reset"),
            (pt.GpioHandler, "reset_all", "gpio-reset"),
        ]:

            def cleanup(*args, event=event, **kwargs):
                events.append(event)
                echo()

            replace(owner, name, cleanup)

        def notify(pid, sig):
            p = pt.PyTrain.current()
            assert pid == os.getpid() and sig == signal.SIGINT
            assert p.exit_status is expected
            assert p._api_exit_notified and p._admin_action is action
            if scenario == "cache-failure":
                assert p._cache_sync_manager is manager
            else:
                assert p._cache_sync_manager is None
            assert p._command_queue is None
            assert events[-1] == "gpio-reset" or (
                route == "queued" and action_name == "UPDATE" and events[-1] == "pytrain-pip"
            )
            assert events.count("gpio-reset") == 1
            assert p._service_info is p._zeroconf is None
            if role == "client":
                assert "disconnect" in events
            events.append("notify")
            if scenario == "signal":
                assert threading.current_thread() is not threading.main_thread()
                real_kill(pid, sig)

        replace(os, "kill", notify)

        def pytrain_subprocess(args, **kwargs):
            assert args == [sys.executable, "-m", "pip", "install", "-U", "pip"]
            assert kwargs == {"cwd": os.getcwd(), "check": False}
            events.append("pytrain-pip")
            echo()
            return subprocess.CompletedProcess(args, 0)

        replace(subprocess, "run", pytrain_subprocess)
        host_commands = []

        def host_system(command):
            assert events.count("notify") == 1
            host_commands.append(command)
            events.append("host-system")
            echo()
            return 0

        replace(os, "system", host_system)

        def execv(*args):
            events.append("exec")
            raise Relaunched()

        replace(os, "execv", execv)
        host_actions = []
        for name in ["update", "upgrade", "reboot", "relaunch"]:
            original = getattr(api.PyTrainApi, name)

            def record(self, *args, name=name, original=original, **kwargs):
                host_actions.append(name)
                assert self.pytrain.exit_status is expected
                if scenario == "signal":
                    assert threading.current_thread() is threading.main_thread()
                    assert "server-return" in events
                return original(self, *args, **kwargs)

            replace(api.PyTrainApi, name, record)

        manager = Mock(spec=pt.CacheSyncManager)
        cache_stop = Mock(side_effect=[RuntimeError("controlled cache stop failure"), None])
        if scenario == "cache-failure":
            replace(pt.CacheSyncManager, "stop", cache_stop)

        def server_return(app, **kwargs):
            assert kwargs["reload"] is False
            p = api.PyTrainApi.get().pytrain
            assert type(p) is pytrain.PyTrain
            assert p.is_server == (role == "server")
            if scenario == "cache-failure":
                p._cache_sync_manager = manager
            if route == "queued":
                p.queue_command(action_name.lower())
                p.run()
            else:
                p._command_processor_available.set()
                if scenario == "cache-failure":
                    with TestCase().assertLogs(pt.log, level="WARNING") as captured:
                        p(pt.CommandReq(action))
                    assert any(
                        record.levelno == logging.WARNING and record.getMessage() == "Cache sync cleanup is incomplete"
                        for record in captured.records
                    ), captured.output
                    events.append("cache-warning")
                else:
                    p(pt.CommandReq(action))
            echo()
            assert p._admin_action is action
            assert events.count("notify") == 1
            events.append("server-return")

        if scenario == "signal":
            from pytrain_api import endpoints

            workers = []
            worker_errors = []
            received = asyncio.Event()
            real_run = uvicorn.run
            real_handle_exit = uvicorn.Server.handle_exit
            real_raise_signal = signal.raise_signal

            def handle_exit(self, sig, frame):
                assert threading.current_thread() is threading.main_thread()
                assert pt.PyTrain.current().exit_status is expected
                events.append("uvicorn-receive")
                real_handle_exit(self, sig, frame)
                received.set()

            def replay(sig):
                assert threading.current_thread() is threading.main_thread()
                assert sig == signal.SIGINT
                events.append("uvicorn-replay")
                real_raise_signal(sig)

            def deliver(request, *args, **kwargs):
                assert request.command is action
                events.append("endpoint-transport")
                pt.PyTrain.current()(request)

            replace(endpoints.CommandReq, "send", deliver)
            replace(uvicorn.Server, "handle_exit", handle_exit)
            replace(signal, "raise_signal", replay)

            async def serve_without_sockets(self, sockets=None):
                assert threading.current_thread() is threading.main_thread()
                assert signal.getsignal(signal.SIGINT) == self.handle_exit
                self.started = True
                events.append("handlers-ready")
                loop = asyncio.get_running_loop()
                done = asyncio.Event()

                def drive():
                    try:
                        p = pt.PyTrain.current()
                        assert p.is_server == (role == "server")
                        if route == "endpoint":
                            p._command_processor_available.set()
                            asyncio.run(endpoints.update())
                        else:
                            p.queue_command(action_name.lower())
                            p.run()
                        echo()
                        assert p._admin_action is action
                    except BaseException as exc:
                        worker_errors.append(exc)
                    finally:
                        loop.call_soon_threadsafe(done.set)

                worker = threading.Thread(target=drive, name="api-exit-driver", daemon=True)
                workers.append(worker)
                real_thread_start(worker)
                await asyncio.wait_for(asyncio.gather(done.wait(), received.wait()), timeout=5)
                assert not worker_errors, worker_errors
                assert self.should_exit
                assert self._captured_signals == [signal.SIGINT]

            def signal_server(app, **kwargs):
                assert kwargs["reload"] is False
                try:
                    real_run(app, **kwargs)
                    events.append("server-return")
                finally:
                    for worker in workers:
                        worker.join(timeout=5)
                        assert not worker.is_alive(), "API exit worker failed to terminate"

            replace(uvicorn.Server, "_serve", serve_without_sockets)
            replace(uvicorn, "run", signal_server)
        else:
            replace(uvicorn, "run", server_return)
        args = ["-ser2"] if role == "server" else ["-server", "192.0.2.10"]
        try:
            api.PyTrainApi(args + ["-no_cache_sync"])
        except Relaunched:
            assert scenario in {"success", "signal", "cache-failure"} and action_name != "QUIT"
        else:
            assert action_name == "QUIT", "Expected terminal host relaunch"
        if scenario == "cache-failure":
            assert events.count("cache-warning") == 1
            p = pt.PyTrain.current()
            assert p._cache_sync_manager is manager
            assert p._admin_action is action
            assert p.exit_status is expected and p._api_exit_notified
            assert p._command_queue is None
            assert events.count("gpio-reset") == 1
            if role == "client":
                assert "disconnect" in events
            for event in ["buffer-stop", "listener-stop", "pdi-stop", "store-reset", "gpio-reset"]:
                assert events.count(event) == 1
                assert events.index(event) < events.index("notify")
            before_retry = (events.copy(), host_actions.copy(), host_commands.copy())
            echo()
            cache_stop.assert_called_once_with()
            assert p._cache_sync_manager is manager
            p.shutdown_cache()
            assert cache_stop.call_count == 2
            assert p._cache_sync_manager is None
            echo()
            assert p._admin_action is action
            assert p.exit_status is expected and p._api_exit_notified
            assert (events, host_actions, host_commands) == before_retry
        assert events.count("notify") == 1
        assert events.index("notify") < events.index("server-return")
        if scenario == "signal":
            assert events.count("uvicorn-receive") == events.count("uvicorn-replay") == 1
            assert events.index("handlers-ready") < events.index("notify")
            assert events.index("notify") < events.index("uvicorn-receive")
            assert events.index("uvicorn-receive") < events.index("uvicorn-replay")
            assert events.index("uvicorn-replay") < events.index("server-return")
            assert events.count("endpoint-transport") == (route == "endpoint")
        expected_actions = {
            "QUIT": [],
            "UPDATE": ["update", "relaunch"],
            "RESTART": ["relaunch"],
            "REBOOT": ["reboot", "relaunch"],
            "SHUTDOWN": ["reboot", "relaunch"],
            "UPGRADE": ["upgrade", "update", "relaunch"],
        }
        assert host_actions == expected_actions[expected_name], host_actions
        assert events.count("exec") == (action_name != "QUIT")
        assert events.count("pytrain-pip") == (route == "queued" and action_name == "UPDATE")
        updates = expected_name in {"UPDATE", "UPGRADE"}
        assert sum("pip install -U pip" in c for c in host_commands) == updates
        assert sum("git pull" in c for c in host_commands) == updates
        assert sum("pip install -r requirements.txt" in c for c in host_commands) == updates
        if expected_name in {"REBOOT", "SHUTDOWN"}:
            assert host_commands == ["sudo shutdown -r now" if expected_name == "REBOOT" else "sudo shutdown now"]
        elif not updates:
            assert host_commands == []
        assert not any(name == "src.pytrain" or name.startswith("src.pytrain.") for name in sys.modules)
        print(
            "API_EXIT_OK "
            + json.dumps(
                {
                    "role": role,
                    "route": route,
                    "action": action_name,
                    "scenario": scenario,
                    "status": expected.name,
                    "events": events,
                    "host_actions": host_actions,
                    "host_commands": host_commands,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
