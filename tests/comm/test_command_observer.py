"""Outgoing command observer contracts."""

from threading import Event

import pytest

from src.pytrain.comm.command_observer import CommandObserver
from src.pytrain.pdi.constants import KEEP_ALIVE_CMD, PdiCommand
from src.pytrain.pdi.pdi_req import TmccReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.fixture(autouse=True)
def reset_observer():
    CommandObserver.stop()
    yield
    CommandObserver.stop()


@pytest.mark.parametrize(
    "command",
    [TMCC1EngineCommandEnum.SET_ADDRESS, TMCC2EngineCommandEnum.SET_ADDRESS],
)
def test_observer_decodes_and_dispatches_registered_commands(command):
    received = []
    notified = Event()

    def handler(req):
        received.append(req)
        notified.set()

    CommandObserver.register(command, handler)
    request = CommandReq.build(command, address=37, scope=CommandScope.ENGINE)
    CommandObserver.offer(TmccReq(request, pdi_command=PdiCommand.TMCC_TX).as_bytes)
    assert notified.wait(2)
    assert len(received) == 1
    assert received[0].command == command
    assert received[0].address == 37


def test_observer_handler_does_not_block_offer():
    started = Event()
    release = Event()

    def handler(req):
        started.set()
        release.wait(2)

    command = TMCC2EngineCommandEnum.SET_ADDRESS
    CommandObserver.register(command, handler)
    packet = CommandReq.build(command, address=37, scope=CommandScope.ENGINE).as_bytes
    try:
        CommandObserver.offer(packet)
        assert started.wait(2)
        # The second offer must complete even while the handler is blocked.
        completed = Event()

        def enqueue():
            CommandObserver.offer(packet)
            completed.set()

        from threading import Thread

        producer = Thread(target=enqueue)
        producer.start()
        assert completed.wait(1)
        producer.join(timeout=1)
    finally:
        release.set()


def test_observer_ignores_keepalive_and_unregistered_commands():
    received = []
    command = TMCC2EngineCommandEnum.SET_ADDRESS
    CommandObserver.register(command, received.append)
    CommandObserver.offer(KEEP_ALIVE_CMD)
    CommandObserver.unregister(command, received.append)
    assert received == []
