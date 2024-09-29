import threading
import time
from collections import defaultdict
from queue import Queue
from typing import Any

import pytest

# noinspection PyProtectedMember
from src.comm.command_listener import CommandListener, _CommandDispatcher, Message, _Channel
from src.protocol.command_req import CommandReq
from src.protocol.constants import DEFAULT_QUEUE_SIZE, BROADCAST_TOPIC, CommandScope
from src.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandDef, TMCC1SwitchState
from src.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef, TMCC2RouteCommandDef, TMCC2HaltCommandDef
from test.test_base import TestBase

CALLBACK_DICT = {}


@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmpdir) -> None:
    """
        Fixture to execute asserts before and after a test is run
    """
    # Setup: fill with any logic you want

    yield  # this is where the testing happens

    # Teardown : fill with any logic you want
    CALLBACK_DICT.clear()
    if CommandListener.is_built:
        CommandListener().shutdown()
    assert CommandListener.is_built is False

    if _CommandDispatcher.is_built:
        _CommandDispatcher().shutdown()
    assert _CommandDispatcher.is_built is False


class TestCommandDispatcher(TestBase):
    def __call__(self, message: Message) -> None:
        self.register_callback(BROADCAST_TOPIC, message)

    def switch_topic(self, message: Message) -> None:
        self.register_callback(CommandScope.SWITCH, message)

    def engine_topic(self, message: Message) -> None:
        self.register_callback(CommandScope.ENGINE, message)

    def engine_13_topic(self, message: Message) -> None:
        self.register_callback((CommandScope.ENGINE, 13), message)

    def engine_22_ring_bell_topic(self, message: Message) -> None:
        self.register_callback((CommandScope.ENGINE, 22, TMCC2EngineCommandDef.RING_BELL), message)

    @staticmethod
    def register_callback(topic: Any, message: Message) -> None:
        if topic in CALLBACK_DICT:
            CALLBACK_DICT[topic].append(message)
        else:
            CALLBACK_DICT[topic] = [message]

    def teardown_method(self, test_method):
        super().teardown_method(test_method)

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

    def test_channel_class(self):
        channel = _Channel()
        assert channel is not None
        assert channel.subscribers is not None
        assert not channel.subscribers
        assert isinstance(channel.subscribers, set)

        # add this class as a subscriber
        channel.subscribe(self)
        assert channel.subscribers
        assert len(channel.subscribers) == 1

        # add self again, should not change subscriber count
        channel.subscribe(self)
        assert len(channel.subscribers) == 1

        # unsubscribe
        channel.unsubscribe(self)
        assert len(channel.subscribers) == 0

        # resubscribe and try publishing
        channel.subscribe(self)
        channel.publish("ABC")
        assert len(CALLBACK_DICT) == 1
        assert len(CALLBACK_DICT[BROADCAST_TOPIC]) == 1
        assert CALLBACK_DICT[BROADCAST_TOPIC][0] == "ABC"

        # remove subscriber and republish; should be no exception
        channel.unsubscribe(self)
        CALLBACK_DICT.clear()
        channel.publish("ABC")
        assert len(CALLBACK_DICT) == 0

    def test_publish_all(self) -> None:
        # create dispatcher and add some channels
        dispatcher = _CommandDispatcher()
        assert dispatcher.broadcasts_enabled is False
        dispatcher.subscribe_any(self)
        assert dispatcher.broadcasts_enabled is True

        dispatcher.unsubscribe_any(self)
        assert dispatcher.broadcasts_enabled is False

        # test publish_all
        dispatcher.subscribe_any(self)
        assert dispatcher.broadcasts_enabled is True
        ring_req = CommandReq.build(TMCC2EngineCommandDef.RING_BELL, 2)
        dispatcher.offer(ring_req)
        time.sleep(0.1)
        dispatcher.shutdown()
        dispatcher.join()
        assert dispatcher.is_running is False
        assert len(CALLBACK_DICT) == 1
        assert len(CALLBACK_DICT[BROADCAST_TOPIC]) == 1
        assert CALLBACK_DICT[BROADCAST_TOPIC][0] == ring_req

    # noinspection DuplicatedCode
    def test_publish(self) -> None:
        # create dispatcher and add some channels
        dispatcher = _CommandDispatcher()
        assert dispatcher.broadcasts_enabled is False

        # register callbacks
        assert len(dispatcher._channels) == 0
        dispatcher.subscribe(self.switch_topic, CommandScope.SWITCH)
        dispatcher.subscribe(self.engine_topic, CommandScope.ENGINE)
        dispatcher.subscribe(self.engine_13_topic, CommandScope.ENGINE, 13)
        dispatcher.subscribe(self.engine_22_ring_bell_topic,
                             CommandScope.ENGINE,
                             22,
                             TMCC2EngineCommandDef.RING_BELL)
        assert dispatcher.broadcasts_enabled is False
        assert len(dispatcher._channels) == 4

        # offer an Engine Req, should only trigger one listener
        ring_req = CommandReq.build(TMCC2EngineCommandDef.RING_BELL, 3)
        assert ring_req.address == 3
        dispatcher.offer(ring_req)
        time.sleep(0.05)
        assert dispatcher.is_running is True
        assert len(dispatcher._channels) == 4
        # listener should have triggered one exception
        assert len(CALLBACK_DICT) == 1
        assert len(CALLBACK_DICT[CommandScope.ENGINE]) == 1
        assert CALLBACK_DICT[CommandScope.ENGINE][0] == ring_req

        # retest for eng request to engine 13
        CALLBACK_DICT.clear()
        ring_req = CommandReq.build(TMCC2EngineCommandDef.RING_BELL, 13)
        assert ring_req.address == 13
        dispatcher.offer(ring_req)
        time.sleep(0.05)
        assert dispatcher.is_running is True
        # listener should have triggered one exception
        assert len(CALLBACK_DICT) == 2
        assert len(CALLBACK_DICT[(CommandScope.ENGINE, 13)]) == 1
        assert CALLBACK_DICT[(CommandScope.ENGINE, 13)][0] == ring_req
        assert len(CALLBACK_DICT[CommandScope.ENGINE]) == 1
        assert CALLBACK_DICT[CommandScope.ENGINE][0] == ring_req

        # retest for eng request to engine 22
        CALLBACK_DICT.clear()
        ring_req = CommandReq.build(TMCC2EngineCommandDef.RING_BELL, 22)
        assert ring_req.address == 22
        dispatcher.offer(ring_req)
        time.sleep(0.05)
        assert dispatcher.is_running is True
        # listener should have triggered one exception
        assert len(CALLBACK_DICT) == 2
        assert len(CALLBACK_DICT[(CommandScope.ENGINE, 22, TMCC2EngineCommandDef.RING_BELL)]) == 1
        assert CALLBACK_DICT[(CommandScope.ENGINE, 22, TMCC2EngineCommandDef.RING_BELL)][0] == ring_req
        assert len(CALLBACK_DICT[CommandScope.ENGINE]) == 1
        assert CALLBACK_DICT[CommandScope.ENGINE][0] == ring_req

        # retest for route request, should generate no callbacks
        CALLBACK_DICT.clear()
        rte_req = CommandReq.build(TMCC2RouteCommandDef.FIRE, 13)
        dispatcher.offer(rte_req)
        time.sleep(0.05)
        assert dispatcher.is_running is True
        assert len(CALLBACK_DICT) == 0

        # unsubscribe engine 22 and fire request, callback should not be invoked
        dispatcher.unsubscribe(self.engine_22_ring_bell_topic,
                               CommandScope.ENGINE,
                               22,
                               TMCC2EngineCommandDef.RING_BELL)
        assert len(dispatcher._channels) == 3
        ring_req = CommandReq.build(TMCC2EngineCommandDef.RING_BELL, 22)
        assert ring_req.address == 22
        dispatcher.offer(ring_req)
        time.sleep(0.05)
        assert dispatcher.is_running is True
        # listener should have triggered one exception
        assert len(CALLBACK_DICT) == 1
        assert len(CALLBACK_DICT[CommandScope.ENGINE]) == 1
        assert CALLBACK_DICT[CommandScope.ENGINE][0] == ring_req

        # retest switch, should only be one callback
        CALLBACK_DICT.clear()
        sw_req = CommandReq.build(TMCC1SwitchState.OUT, 22)
        assert sw_req.address == 22
        dispatcher.offer(sw_req)
        time.sleep(0.05)
        assert dispatcher.is_running is True
        # listener should have triggered one callback
        assert len(CALLBACK_DICT) == 1
        assert len(CALLBACK_DICT[CommandScope.SWITCH]) == 1
        assert CALLBACK_DICT[CommandScope.SWITCH] == [sw_req]

    # noinspection DuplicatedCode
    def test_publish_halt(self) -> None:
        # create dispatcher and add some channels
        dispatcher = _CommandDispatcher()
        assert dispatcher.broadcasts_enabled is False

        # register callbacks
        assert len(dispatcher._channels) == 0
        dispatcher.subscribe(self.switch_topic, CommandScope.SWITCH)
        dispatcher.subscribe(self.engine_topic, CommandScope.ENGINE)
        dispatcher.subscribe(self.engine_13_topic, CommandScope.ENGINE, 13)
        dispatcher.subscribe(self.engine_22_ring_bell_topic,
                             CommandScope.ENGINE,
                             22,
                             TMCC2EngineCommandDef.RING_BELL)
        assert dispatcher.broadcasts_enabled is False
        assert len(dispatcher._channels) == 4

        # send a halt command; should be received by all listeners
        halt_req = CommandReq.build(TMCC1HaltCommandDef.HALT)
        dispatcher.offer(halt_req)
        time.sleep(0.05)
        assert dispatcher.is_running is True
        assert len(dispatcher._channels) == 4
        # listener should have triggered 4 exception
        assert len(CALLBACK_DICT) == 4
        assert CALLBACK_DICT[CommandScope.ENGINE] == [halt_req]
        assert CALLBACK_DICT[(CommandScope.ENGINE, 13)] == [halt_req]
        assert CALLBACK_DICT[(CommandScope.ENGINE, 22, TMCC2EngineCommandDef.RING_BELL)] == [halt_req]
        assert CALLBACK_DICT[CommandScope.SWITCH] == [halt_req]

    # noinspection DuplicatedCode
    def test_publish_system_halt(self) -> None:
        #  Test receipt of SYSTEM_HALT
        dispatcher = _CommandDispatcher()
        assert dispatcher.broadcasts_enabled is False

        # register callbacks
        assert len(dispatcher._channels) == 0
        dispatcher.subscribe(self.switch_topic, CommandScope.SWITCH)
        dispatcher.subscribe(self.engine_topic, CommandScope.ENGINE)
        dispatcher.subscribe(self.engine_13_topic, CommandScope.ENGINE, 13)
        dispatcher.subscribe(self.engine_22_ring_bell_topic,
                             CommandScope.TRAIN,
                             22,
                             TMCC2EngineCommandDef.RING_BELL)
        assert dispatcher.broadcasts_enabled is False
        assert len(dispatcher._channels) == 4

        # send a halt command; should be received by all listeners
        sys_halt_req = CommandReq.build(TMCC2HaltCommandDef.HALT)
        dispatcher.offer(sys_halt_req)
        time.sleep(0.05)
        assert dispatcher.is_running is True
        assert len(dispatcher._channels) == 4
        # listener should have triggered engine and train channels
        assert len(CALLBACK_DICT) == 3
        assert CALLBACK_DICT[CommandScope.ENGINE] == [sys_halt_req]
        assert CALLBACK_DICT[(CommandScope.ENGINE, 13)] == [sys_halt_req]
        assert CALLBACK_DICT[(CommandScope.ENGINE, 22, TMCC2EngineCommandDef.RING_BELL)] == [sys_halt_req]
