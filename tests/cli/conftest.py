import logging
import os
import sys
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@contextmanager
def isolated_pytrain_state():
    """Restore process state even when initialization or a test raises."""
    from src.pytrain.cli import pytrain as module
    from src.pytrain.utils.singleton import _SingletonMeta

    loggers = [logging.getLogger(), module.log]
    logging_state = [(log, log.level, log.handlers[:], log.propagate, log.disabled) for log in loggers]
    handler_levels = {handler: handler.level for log in loggers for handler in log.handlers}
    argv = sys.argv
    argv_contents = argv[:]
    environment = dict(os.environ)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(module.PyTrain, "_current", None)
        patch.setattr(_SingletonMeta, "_instances", dict(_SingletonMeta._instances))
        patch.setattr(_SingletonMeta, "_init_done", dict(_SingletonMeta._init_done))
        try:
            yield
        finally:
            sys.argv = argv
            argv[:] = argv_contents
            os.environ.clear()
            os.environ.update(environment)
            for log, level, handlers, propagate, disabled in logging_state:
                log.setLevel(level)
                log.handlers[:] = handlers
                log.propagate = propagate
                log.disabled = disabled
            for handler, level in handler_levels.items():
                handler.setLevel(level)


@pytest.fixture
def pytrain_isolation():
    with isolated_pytrain_state():
        yield


@pytest.fixture
def bare_pytrain(pytrain_isolation):
    from src.pytrain.cli import pytrain as module

    return module.PyTrain.__new__(module.PyTrain)


@pytest.fixture
def pytrain_startup(bare_pytrain, monkeypatch):
    """Real constructor/parser, inert service factories, and no runtime loop."""
    import src.pytrain as package
    from src.pytrain.cli import pytrain as module
    from src.pytrain.comm.comm_buffer import CommBufferProxy

    doubles = SimpleNamespace(instance=bare_pytrain)
    doubles.server_buffer = Mock(spec=module.CommBufferSingleton)
    doubles.client_buffer = Mock(spec=CommBufferProxy)
    doubles.client_buffer.server_ip.return_value = "192.0.2.20"
    doubles.client_buffer.server_version = (1, 2, 3)
    doubles.client_buffer.base3_address = None
    doubles.listener = Mock(spec=module.CommandListener)
    doubles.client_listener = Mock(spec=module.ClientStateListener)
    doubles.client_listener.port = 5111
    doubles.pdi = Mock(spec=module.PdiListener)

    def replace(owner, name, **kwargs):
        double = Mock(**kwargs)
        monkeypatch.setattr(owner, name, double)
        return double

    doubles.build = replace(
        module.CommBuffer,
        "build",
        side_effect=lambda **kw: doubles.server_buffer if kw["server"] is None else doubles.client_buffer,
    )
    doubles.listen = replace(module.CommandListener, "build", return_value=doubles.listener)
    doubles.client_listen = replace(module.ClientStateListener, "build", return_value=doubles.client_listener)
    doubles.pdi_build = replace(module.PdiListener, "build", return_value=doubles.pdi)
    doubles.receiver = replace(module, "EnqueueProxyRequests")
    doubles.store = replace(module, "ComponentStateStore")
    doubles.pdi_store = replace(module, "PdiStateStore")
    doubles.dispatcher = replace(module.CommandDispatcher, "get")
    doubles.discovery = replace(module.PyTrain, "get_service_info", return_value=("192.0.2.10", 5110))
    doubles.base_discovery = replace(module, "find_base_address", return_value="192.0.2.30")
    doubles.roster = replace(module.PyTrain, "_get_system_state")
    doubles.run = replace(module.PyTrain, "run")
    doubles.debug = replace(module.PyTrain, "_enable_debug")
    doubles.echo = replace(module.PyTrain, "_enable_echo")
    doubles.thread = replace(module, "Thread")
    replace(package, "get_version", return_value="9.8.7")
    replace(module.socket, "gethostbyname", side_effect=lambda host: host)
    for owner, name in [
        (module.subprocess, "run"),
        (module.os, "execv"),
        (module.os, "kill"),
        (module, "Zeroconf"),
        (module, "ServiceBrowser"),
        (module, "sleep"),
        (module.GpioHandler, "reset_all"),
        (threading.Thread, "start"),
    ]:
        replace(owner, name, side_effect=AssertionError(f"Unexpected startup side effect: {name}"))

    def initialize(args=None):
        module.PyTrain.__init__(bare_pytrain, args)
        return bare_pytrain

    doubles.initialize = initialize
    return doubles
