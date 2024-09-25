from __future__ import annotations

import threading
from collections import deque, defaultdict
from queue import Queue
from threading import Thread
from typing import Protocol, TypeVar, runtime_checkable, Tuple

from ..protocol.command_req import TMCC_FIRST_BYTE_TO_INTERPRETER, CommandReq
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_QUEUE_SIZE
from ..protocol.tmcc2.tmcc2_constants import LEGACY_PARAMETER_COMMAND_PREFIX


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
        self._dispatcher = CommandDispatcher()
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
            if self._deque[0] in TMCC_FIRST_BYTE_TO_INTERPRETER and dq_len >= 3:
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

    def offer(self, data: bytes) -> None:
        if data:
            with self._cv:
                self._deque.extend(data)
                self._cv.notify()

    def shutdown(self) -> None:
        self._is_running = False
        if self._serial_reader:
            self._serial_reader.shutdown()
        if self._dispatcher:
            self._dispatcher.shutdown()


Message = TypeVar("Message")
Topic = TypeVar("Topic")


@runtime_checkable
class Subscriber[Message](Protocol):
    def __call__(self, message: Message) -> None:
        ...


class Sub:
    def __init__(self, d: str):
        self.d = d

    def __call__(self, message: Message) -> None:
        print(f"Message: {message}")


class Channel[Message]:
    def __init__(self) -> None:
        self.subscribers: set[Subscriber[Message]] = set[Subscriber[Message]]()

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


class CommandDispatcher(Thread):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in a process
        """
        with cls._lock:
            if CommandDispatcher._instance is None:
                CommandDispatcher._instance = super(CommandDispatcher, cls).__new__(cls)
                CommandDispatcher._instance._initialized = False
            return CommandDispatcher._instance

    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(name="PyLegacy Command Dispatcher")
        self.channels: dict[Topic | Tuple[Topic, int], Channel[Message]] = defaultdict(Channel)
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
            cmd = self._queue.get()
            # publish dispatched commands to listeners on the command scope,
            # to listeners
            if isinstance(cmd, CommandReq):
                self.publish((cmd.scope, cmd.address), cmd)
                self.publish(cmd.scope, cmd)
                if self._broadcasts:
                    self.publish("BROADCAST", cmd)
            # self.publish_all(cmd)
            # print(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {cmd}")

    def offer(self, cmd: CommandReq) -> None:
        if cmd:
            with self._cv:
                self._queue.put(cmd)
                self._cv.notify()

    def shutdown(self) -> None:
        self._is_running = False

    def publish(self, channel: Topic, message: Message) -> None:
        self.channels[channel].publish(message)

    def subscribe(self, subscriber: Subscriber, channel: Topic, address: int = None) -> None:
        if address is None:
            self.channels[channel].subscribe(subscriber)
        else:
            self.channels[(channel, address)].subscribe(subscriber)

    def subscribe_any(self, subscriber: Subscriber) -> None:
        # receive broadcasts
        self.channels["BROADCAST"].subscribe(subscriber)
        self._broadcasts = True

    def unsubscribe_any(self, subscriber: Subscriber) -> None:
        # receive broadcasts
        self.channels["BROADCAST"].unsubscribe(subscriber)
        if not self.channels["BROADCAST"].subscribers:
            self._broadcasts = False

    def unsubscribe(self, subscriber: Subscriber, channel: Topic, address: int = None) -> None:
        if address is None:
            self.channels[channel].unsubscribe(subscriber)
        else:
            self.channels[(channel, address)].unsubscribe(subscriber)
