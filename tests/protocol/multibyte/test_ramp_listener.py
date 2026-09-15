from collections import deque
from threading import Condition, Event, Thread
from unittest.mock import Mock

import pytest

from pytrain.comm.command_listener import CommandDispatcher, CommandListener
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from pytrain.protocol.multibyte.ramp_command_req import RampCommandReq
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.mark.parametrize("command", (TMCC2EngineCommandEnumEx.RAMP_CLAIM, TMCC2EngineCommandEnumEx.RAMP_RELEASE))
@pytest.mark.parametrize("address", (7, 3180, 9999))
@pytest.mark.parametrize("scope", (CommandScope.ENGINE, CommandScope.TRAIN))
@pytest.mark.parametrize("timestamp_ms", (1, 1_700_000_000_123, (1 << 48) - 1))
def test_listener_consumes_ramp_followed_by_speed(command, address, scope, timestamp_ms):
    ramp = RampCommandReq.for_endpoint(command, address, "127.0.0.1", 5110, 123, scope, timestamp_ms=timestamp_ms)
    assert ramp.data_bytes == bytes.fromhex("7f00000113f6007b") + timestamp_ms.to_bytes(6, "big")
    assert len(ramp.data_bytes) == 14
    assert len(ramp.as_bytes) == ramp.num_bytes == 63
    assert ramp.as_bytes[5] == 16
    speed = CommandReq.build(TMCC2EngineCommandEnum.ABSOLUTE_SPEED, address, 42, scope)
    singletons = (CommandListener._instance, CommandDispatcher._instance)
    listener = object.__new__(CommandListener)
    listener._deque = deque(ramp.as_bytes + speed.as_bytes)
    listener._cv = Condition()
    listener._is_running = True
    listener._dispatcher = Mock()
    received = []
    done = Event()

    def collect(request):
        received.append(request)
        if len(received) == 2:
            listener._is_running = False

    listener._dispatcher.offer.side_effect = collect
    listener._dispatcher.shutdown.side_effect = done.set
    worker = Thread(target=listener.run, daemon=True)
    worker.start()
    try:
        completed = done.wait(1)
    finally:
        listener._is_running = False
        with listener._cv:
            listener._cv.notify_all()
        worker.join(1)

    assert not worker.is_alive()
    assert (CommandListener._instance, CommandDispatcher._instance) == singletons
    assert completed, f"Listener left {len(listener._deque)} bytes pending"
    assert not listener._deque
    assert len(received) == 2
    assert isinstance(received[0], RampCommandReq)
    assert received[0].command is command
    assert received[0].address == address
    assert received[0].scope is scope
    assert (received[0].host, received[0].port, received[0].claim_id) == ("127.0.0.1", 5110, 123)
    assert received[0].timestamp_ms == timestamp_ms
    assert received[0].data_bytes == ramp.data_bytes
    assert received[0].num_bytes == 63
    assert received[0].as_bytes == ramp.as_bytes
    assert received[1].command is TMCC2EngineCommandEnum.ABSOLUTE_SPEED
    assert received[1].address == address
    assert received[1].scope is scope
    assert received[1].data == 42
    assert received[1].as_bytes == speed.as_bytes
    listener._dispatcher.shutdown.assert_called_once_with()
