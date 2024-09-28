import threading
from collections import defaultdict
from queue import Queue

import pytest

# noinspection PyProtectedMember
from src.comm.command_listener import CommandListener, _CommandDispatcher
from src.protocol.command_req import CommandReq
from src.protocol.constants import DEFAULT_QUEUE_SIZE
from src.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandDef
from src.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef
from test.test_base import TestBase


@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmpdir) -> None:
    """
        Fixture to execute asserts before and after a test is run
    """
    # Setup: fill with any logic you want

    yield  # this is where the testing happens

    # Teardown : fill with any logic you want
    if CommandListener.is_built:
        CommandListener().shutdown()
    assert CommandListener.is_built is False

    if _CommandDispatcher.is_built:
        _CommandDispatcher().shutdown()
    assert _CommandDispatcher.is_built is False


class TestCommandDispatcher(TestBase):
    def test_command_dispatcher_singleton(self) -> None:
        assert _CommandDispatcher.is_built is False
        dispatcher = _CommandDispatcher()
        assert dispatcher.is_built is True
        assert dispatcher.is_running is True
        assert isinstance(dispatcher, _CommandDispatcher)
        assert dispatcher is _CommandDispatcher()
        assert dispatcher.is_alive()
        assert dispatcher.broadcasts_enabled is False
        assert isinstance(dispatcher._channels, defaultdict)
        assert not dispatcher._channels
        assert dispatcher.daemon is True
        assert dispatcher._queue is not None  # queue should exist
        assert dispatcher._queue.maxsize == DEFAULT_QUEUE_SIZE
        assert isinstance(dispatcher._queue, Queue)
        assert dispatcher._queue.empty()  # should be empty
        assert dispatcher._cv is not None
        assert isinstance(dispatcher._cv, threading.Condition)

        # shutdown should clear singleton, forcing a new one to be created
        assert dispatcher._instance is not None
        dispatcher.shutdown()
        assert dispatcher._instance is None
        assert _CommandDispatcher._instance is None
        assert dispatcher.is_built is False
        assert dispatcher.is_running is False
        assert _CommandDispatcher.is_built is False
        assert dispatcher != _CommandDispatcher()
        _CommandDispatcher().shutdown()
        assert _CommandDispatcher._instance is None

        # creation of a CommandListener should create a command dispatcher
        listener = CommandListener()
        dispatcher = _CommandDispatcher()
        assert listener._dispatcher is dispatcher
        assert dispatcher.is_running is True

        # shutting down the listener should shut down the dispatcher
        listener.shutdown()
        assert listener.is_running is False

    def test_command_dispatcher_run(self) -> None:
        dispatcher = _CommandDispatcher()
        # add elements to the queue and make sure they appear in deque in the correct order
        ring_req = CommandReq.build(TMCC2EngineCommandDef.RING_BELL, 20)
        halt_req = CommandReq.build(TMCC1HaltCommandDef.HALT)
        with dispatcher._cv:
            dispatcher.offer(ring_req)
            dispatcher.offer(halt_req)
            dispatcher.offer(ring_req)
            # queue should contain 3 entries
            assert dispatcher._queue.empty() is False
            assert dispatcher._queue.qsize() == 3
            req = dispatcher._queue.get_nowait()
            dispatcher._queue.task_done()
            assert req is not None
            assert req == ring_req

            req = dispatcher._queue.get_nowait()
            dispatcher._queue.task_done()
            assert req is not None
            assert req == halt_req

            req = dispatcher._queue.get_nowait()
            dispatcher._queue.task_done()
            assert req is not None
            assert req == ring_req
            assert dispatcher._queue.empty()
