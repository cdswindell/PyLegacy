import threading
import time
from collections import deque

# noinspection PyPackageRequirements
import pytest

# noinspection PyProtectedMember
from src.pytrain.comm.command_listener import CommandListener, CommandDispatcher
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_QUEUE_SIZE
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from test.test_base import TestBase


# noinspection PyTypeChecker
@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmpdir) -> None:
    """
    Fixture to execute asserts before and after a test is run
    """
    # Setup: fill with any logic you want

    yield  # this is where the testing happens

    # Teardown : fill with any logic you want
    if CommandListener.is_built():
        CommandListener().shutdown()
    assert CommandListener.is_built() is False

    if CommandDispatcher.is_built():
        CommandDispatcher().shutdown()
    assert CommandDispatcher.is_built() is False


class TestCommandListener(TestBase):
    def test_command_listener_singleton(self) -> None:
        assert CommandListener.is_built() is False
        listener = CommandListener()
        assert listener.is_built() is True
        assert listener.is_running() is True
        assert isinstance(listener, CommandListener)
        assert listener is CommandListener()
        assert listener.baudrate == DEFAULT_BAUDRATE
        assert listener.port == DEFAULT_PORT
        assert listener.is_alive()
        assert listener.daemon is True
        assert listener._deque is not None  # dequeue should exist
        assert listener._deque.maxlen == DEFAULT_QUEUE_SIZE
        assert isinstance(listener._deque, deque)
        assert not listener._deque  # should be empty
        assert listener._cv is not None
        assert isinstance(listener._cv, threading.Condition)

        # shutdown should clear singleton, forcing a new one to be created
        assert CommandListener._instance is not None
        listener.shutdown()
        assert CommandListener._instance is None
        assert listener.is_built() is False
        assert listener.is_running() is False
        assert CommandListener.is_built() is False
        assert listener != CommandListener()

    def test_command_listener_build(self) -> None:
        listener = CommandListener.build(baudrate=57600)
        assert listener
        assert listener.is_built() is True
        assert listener.is_running() is True
        assert CommandListener.is_built() is True
        assert CommandListener.is_running() is True
        assert listener.baudrate == 57600
        assert listener == CommandListener()
        assert CommandListener(baudrate=9600).baudrate == 57600  # original instance returned

    def test_command_listener_invalid_baudrate(self) -> None:
        with pytest.raises(ValueError, match="Invalid baudrate: 12345"):
            CommandListener.build(baudrate=12345)

    def test_command_listener_run(self) -> None:
        listener = CommandListener.build()
        # add elements to the queue and make sure they appear in deque in the correct order
        ring_req = CommandReq.build(TMCC2EngineCommandEnum.RING_BELL, 10)
        halt_req = CommandReq.build(TMCC1HaltCommandEnum.HALT)
        with listener._cv:
            listener.offer(ring_req.as_bytes)
            listener.offer(halt_req.as_bytes)
            # deque should contain 6 bytes
            assert len(listener._deque) == 6
            cmd_bytes = ring_req.as_bytes + halt_req.as_bytes
            for i in range(6):
                assert cmd_bytes[i] == listener._deque[i]
        # outside the lock context, consumer threads will run
        time.sleep(0.1)  # allow threads to clear deque
        assert len(listener._deque) == 0  # both entries processed
        # lock should be open too
        assert listener._cv.acquire(blocking=False) is True
        listener._cv.release()
