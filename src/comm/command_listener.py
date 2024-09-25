from __future__ import annotations

import threading
from collections import deque, defaultdict
from queue import Queue
from threading import Thread
from typing import Protocol, TypeVar, runtime_checkable, Tuple, Generic, List

from ..protocol.command_req import TMCC_FIRST_BYTE_TO_INTERPRETER, CommandReq
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_QUEUE_SIZE, CommandScope
from ..protocol.tmcc2.tmcc2_constants import LEGACY_PARAMETER_COMMAND_PREFIX

Message = TypeVar("Message")
Topic = TypeVar("Topic")


class CommandListener(Thread):
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def build(cls,
              baudrate: int = DEFAULT_BAUDRATE,
              port: str = DEFAULT_PORT) -> CommandListener:
        """
            Factory method to create a CommandListener instance
        """
        return CommandListener(baudrate=baudrate, port=port)

    @classmethod
    def listen_for(cls, listener: Subscriber, channel: Topic, address: int = None):
        cls.build().subscribe(listener, channel, address)

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in a process
        """
        with cls._lock:
            if CommandListener._instance is None:
                CommandListener._instance = super(CommandListener, cls).__new__(cls)
                CommandListener._instance._initialized = False
            return CommandListener._instance

    def __init__(self,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(name="PyLegacy Command Listener")
        # prep our consumer(s)
        self._is_running = True
        self._cv = threading.Condition()
        self._deque = deque(maxlen=DEFAULT_QUEUE_SIZE)
        self.start()
        self._dispatcher = _CommandDispatcher()
        # prep our producer
        from .serial_reader import SerialReader
        self._serial_reader = SerialReader(baudrate, port, self)

    def run(self) -> None:
        while self._is_running:
            # process bytes, as long as there are any
            with self._cv:
                if not self._deque:
                    self._cv.wait()  # wait to be notified
            # check if the first bite is in the list of allowable command prefixes
            dq_len = len(self._deque)
            if dq_len and self._deque[0] in TMCC_FIRST_BYTE_TO_INTERPRETER and dq_len >= 3:
                # at this point, we have some sort of command. It could be a TMCC1 or TMCC2
                # 3-byte command, or, if there are more than 3 bytes, and the 4th byte is
                # 0xf8 or 0xf9 AND the 5th byte is 0xfb, it could be a 9 byte param command
                # Try for the 9-biters first
                cmd_bytes = bytes()
                if (dq_len >= 9 and
                        self._deque[3] == LEGACY_PARAMETER_COMMAND_PREFIX and
                        self._deque[6] == LEGACY_PARAMETER_COMMAND_PREFIX):
                    for _ in range(9):
                        cmd_bytes += self._deque.popleft().to_bytes(1, byteorder='big')
                elif dq_len >= 4 and self._deque[3] == LEGACY_PARAMETER_COMMAND_PREFIX:
                    # we could be in the middle of receiving a parameter command, wait a bit longer
                    continue
                else:
                    # assume a 3 byte command
                    for _ in range(3):
                        cmd_bytes += self._deque.popleft().to_bytes(1, byteorder='big')
                if cmd_bytes:
                    try:
                        # build a CommandReq from the received bytes and send it to the dispatcher
                        self._dispatcher.offer(CommandReq.from_bytes(cmd_bytes))
                    except ValueError as ve:
                        print(ve)
            elif dq_len < 3:
                continue  # wait for more bytes
            else:
                # pop this byte and continue; we either received unparsable input
                # or started receiving data mid-command
                print(f"Ignoring {hex(self._deque.popleft())}")
        # shut down the dispatcher
        if self._dispatcher:
            self._dispatcher.shutdown()

    def offer(self, data: bytes) -> None:
        if data:
            with self._cv:
                self._deque.extend(data)
                self._cv.notify()

    def shutdown(self) -> None:
        with self._cv:
            self._is_running = False
            self._cv.notify()
        if self._serial_reader:
            self._serial_reader.shutdown()
        if self._dispatcher:
            self._dispatcher.shutdown()

    def subscribe(self, subscriber: Subscriber, channel: Topic, address: int = None) -> None:
        self._dispatcher.subscribe(subscriber, channel, address)

    def unsubscribe(self, subscriber: Subscriber, channel: Topic, address: int = None) -> None:
        self._dispatcher.unsubscribe(subscriber, channel, address)

    def subscribe_any(self, subscriber: Subscriber) -> None:
        self._dispatcher.subscribe_any(subscriber)

    def unsubscribe_any(self, subscriber: Subscriber) -> None:
        self._dispatcher.unsubscribe_any(subscriber)


@runtime_checkable
class Subscriber(Protocol):
    """
        Protocol that all listener callbacks must implement
    """
    def __call__(self, message: Message) -> None:
        ...


class _Channel(Generic[Message]):
    """
        Part of the publish/subscribe pattern described here:
        https://arjancodes.com/blog/publish-subscribe-pattern-in-python/
        In our case, the "channels" are the valid CommandScopes, a tuple
        consisting of a CommandScope and an TMCC ID/Address, and a
        special "BROADCAST" channel that receives all received commands.
    """
    def __init__(self) -> None:
        self.subscribers: set[Subscriber] = set[Subscriber]()

    def __eq__(self, other):
        if other.__class__ is self.__class__:
            return (self.subscribers,) == (other.subscribers,)
        return NotImplemented

    def subscribe(self, subscriber: Subscriber[Message]) -> None:
        self.subscribers.add(subscriber)

    def unsubscribe(self, subscriber: Subscriber[Message]) -> None:
        self.subscribers.remove(subscriber)

    def publish(self, message: Message) -> None:
        for subscriber in self.subscribers:
            try:
                subscriber(message)
            finally:
                pass


class _CommandDispatcher(Thread):
    """
        The CommandDispatcher thread receives parsed CommandReqs from the
        CommandListener and dispatches them to subscribing listeners
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in a process
        """
        with cls._lock:
            if _CommandDispatcher._instance is None:
                _CommandDispatcher._instance = super(_CommandDispatcher, cls).__new__(cls)
                _CommandDispatcher._instance._initialized = False
            return _CommandDispatcher._instance

    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(name="PyLegacy Command Dispatcher")
        self.channels: dict[Topic | Tuple[Topic, int], _Channel[Message]] = defaultdict(_Channel)
        self._cv = threading.Condition()
        self._is_running = True
        self._queue = Queue[CommandReq](queue_size)
        self._broadcasts = False
        self.start()

    def run(self) -> None:
        while self._is_running:
            with self._cv:
                if self._queue.empty():
                    self._cv.wait()
            if self._queue.empty():  # we need to do a second check in the event we're being shutdown
                continue
            cmd = self._queue.get()
            # publish dispatched commands to listeners on the command scope,
            # to listeners
            if isinstance(cmd, CommandReq):
                # if command is a TMCC1 Halt, send to everyone
                if cmd.is_halt:
                    self.publish_all(cmd)
                elif cmd.is_system_halt:
                    self.publish_all(cmd, [CommandScope.ENGINE, CommandScope.TRAIN])
                else:
                    self.publish((cmd.scope, cmd.address), cmd)
                    self.publish(cmd.scope, cmd)
                if self._broadcasts:
                    self.publish("BROADCAST", cmd)

    def offer(self, cmd: CommandReq) -> None:
        """
            Receive a command from the listener thread and dispatch it to subscribers.
            We do this in a separate thread so that the listener thread doesn't fall behind
        """
        if cmd:
            with self._cv:
                self._queue.put(cmd)
                self._cv.notify()

    def shutdown(self) -> None:
        with self._cv:
            self._is_running = False
            self._cv.notify()

    def publish_all(self, message: Message, channels: List[CommandScope] = None) -> None:
        if channels is None:
            channels = self.channels.values()
        for channel in channels:
            try:
                self.channels[channel].publish(message)
            except Exception as e:
                print(f"Error publishing to {channel}: {e}")

    def publish(self, channel: Topic, message: Message) -> None:
        self.channels[channel].publish(message)

    def subscribe(self, subscriber: Subscriber, channel: Topic, address: int = None) -> None:
        if address is None:
            self.channels[channel].subscribe(subscriber)
        else:
            self.channels[(channel, address)].subscribe(subscriber)

    def unsubscribe(self, subscriber: Subscriber, channel: Topic, address: int = None) -> None:
        if address is None:
            self.channels[channel].unsubscribe(subscriber)
        else:
            self.channels[(channel, address)].unsubscribe(subscriber)

    def subscribe_any(self, subscriber: Subscriber) -> None:
        # receive broadcasts
        self.channels["BROADCAST"].subscribe(subscriber)
        self._broadcasts = True

    def unsubscribe_any(self, subscriber: Subscriber) -> None:
        # receive broadcasts
        self.channels["BROADCAST"].unsubscribe(subscriber)
        if not self.channels["BROADCAST"].subscribers:
            self._broadcasts = False
