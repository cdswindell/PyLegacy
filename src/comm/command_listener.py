from __future__ import annotations

import socket
import threading
from collections import deque, defaultdict
from queue import Queue
from threading import Thread
from typing import Protocol, TypeVar, runtime_checkable, Tuple, Generic, List

from .enqueue_proxy_requests import EnqueueProxyRequests
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import TMCC_FIRST_BYTE_TO_INTERPRETER, CommandReq
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_QUEUE_SIZE, DEFAULT_VALID_BAUDRATES
from ..protocol.constants import CommandScope, BROADCAST_TOPIC
from ..protocol.tmcc2.tmcc2_constants import LEGACY_PARAMETER_COMMAND_PREFIX

Message = TypeVar("Message")
Topic = TypeVar("Topic")


class CommandListener(Thread):
    _instance: None = None
    _lock = threading.Lock()

    @classmethod
    def build(cls,
              baudrate: int = DEFAULT_BAUDRATE,
              port: str = DEFAULT_PORT,
              queue_size: int = DEFAULT_QUEUE_SIZE,
              build_serial_reader: bool = True) -> CommandListener:
        """
            Factory method to create a CommandListener instance
        """
        return CommandListener(baudrate=baudrate,
                               port=port,
                               queue_size=queue_size,
                               build_serial_reader=build_serial_reader)

    @classmethod
    def listen_for(cls,
                   listener: Subscriber,
                   channel: Topic,
                   address: int = None,
                   command: CommandDefEnum = None,
                   data: int = None):
        cls.build().subscribe(listener, channel, address, command, data)

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_running(cls) -> bool:
        # noinspection PyProtectedMember
        return cls._instance is not None and cls._instance._is_running

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            if cls._instance:
                cls._instance.shutdown()

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
                 port: str = DEFAULT_PORT,
                 queue_size: int = DEFAULT_QUEUE_SIZE,
                 build_serial_reader: bool = True) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        if baudrate not in DEFAULT_VALID_BAUDRATES:
            raise ValueError(f"Invalid baudrate: {baudrate}")
        self._baudrate = baudrate
        self._port = port
        super().__init__(daemon=True, name="PyLegacy Command Listener")

        # prep our consumer(s)
        self._cv = threading.Condition()
        self._deque = deque(maxlen=DEFAULT_QUEUE_SIZE)
        self._is_running = True
        self._dispatcher = CommandDispatcher.build(queue_size)

        # get initial state from Base 3 and LCS modules
        self.sync_state()

        # start listener thread
        self.start()

        # prep our producer
        if build_serial_reader:
            from .serial_reader import SerialReader
            self._serial_reader = SerialReader(baudrate, port, self)
        else:
            self._serial_reader = None

    def sync_state(self) -> None:
        """
            Get initial system state from the Base 3/LCS Modules
        """
        pass

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def port(self) -> str:
        return self._port

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
        # if specified baudrate was invalid, instance won't have most attributes
        if hasattr(self, "_cv"):
            with self._cv:
                self._is_running = False
                self._cv.notify()
        if hasattr(self, "_serial_reader"):
            if self._serial_reader:
                self._serial_reader.shutdown()
        if hasattr(self, "_dispatcher"):
            if self._dispatcher:
                self._dispatcher.shutdown()
        CommandListener._instance = None

    def subscribe(self,
                  listener: Subscriber,
                  channel: Topic,
                  address: int = None,
                  command: CommandDefEnum = None,
                  data: int = None) -> None:
        self._dispatcher.subscribe(listener, channel, address, command, data)

    def unsubscribe(self,
                    listener: Subscriber,
                    channel: Topic,
                    address: int = None,
                    command: CommandDefEnum = None,
                    data: int = None) -> None:
        self._dispatcher.unsubscribe(listener, channel, address, command, data)

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


class Channel(Generic[Topic]):
    """
        Part of the publish/subscribe pattern described here:
        https://arjancodes.com/blog/publish-subscribe-pattern-in-python/
        In our case, the "channels" are the valid CommandScopes, a tuple
        consisting of a CommandScope and an TMCC ID/Address, and a
        special "BROADCAST" channel that receives all received commands.
    """

    def __init__(self) -> None:
        self.subscribers: set[Subscriber] = set[Subscriber]()

    def subscribe(self, subscriber: Subscriber[Message]) -> None:
        self.subscribers.add(subscriber)

    def unsubscribe(self, subscriber: Subscriber[Message]) -> None:
        self.subscribers.remove(subscriber)

    def publish(self, message: Message) -> None:
        for subscriber in self.subscribers:
            try:
                subscriber(message)
            except Exception as e:
                print(f"Error publishing to {self}: {e}")


class CommandDispatcher(Thread):
    """
        The CommandDispatcher thread receives parsed CommandReqs from the
        CommandListener and dispatches them to subscribing listeners
    """
    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(cls, queue_size: int = DEFAULT_QUEUE_SIZE) -> CommandDispatcher:
        """
            Factory method to create a CommandDispatcher instance
        """
        return CommandDispatcher(queue_size)

    @classmethod
    def listen_for(cls,
                   listener: Subscriber,
                   channel: Topic,
                   address: int = None,
                   command: CommandDefEnum = None,
                   data: int = None):
        cls.build().subscribe(listener, channel, address, command, data)

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_running(cls) -> bool:
        # noinspection PyProtectedMember
        return cls._instance is not None and cls._instance._is_running

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

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
        super().__init__(daemon=True, name="PyLegacy Command Dispatcher")
        self._channels: dict[Topic | Tuple[Topic, int], Channel[Message]] = defaultdict(Channel)
        self._cv = threading.Condition()
        self._is_running = True
        self._queue = Queue[CommandReq](queue_size)
        self._broadcasts = False
        self._client_port = EnqueueProxyRequests.port if EnqueueProxyRequests.is_built else None
        self.start()

    def run(self) -> None:
        while self._is_running:
            with self._cv:
                if self._queue.empty():
                    self._cv.wait()
            if self._queue.empty():  # we need to do a second check in the event we're being shutdown
                continue
            cmd = self._queue.get()
            try:
                # publish dispatched commands to listeners on the command scope,
                # to listeners
                if isinstance(cmd, CommandReq):
                    # if command is a TMCC1 Halt, send to everyone
                    if cmd.is_halt:
                        self.publish_all(cmd)
                    # if command is a legacy-style halt, just send to engines and trains
                    elif cmd.is_system_halt:
                        self.publish_all(cmd, [CommandScope.ENGINE, CommandScope.TRAIN])
                    # otherwise, just send to the interested parties
                    else:
                        if cmd.is_data is not None:
                            self.publish((cmd.scope, cmd.address, cmd.command, cmd.data), cmd)
                        self.publish((cmd.scope, cmd.address, cmd.command), cmd)
                        self.publish((cmd.scope, cmd.address), cmd)
                        self.publish(cmd.scope, cmd)
                    if self._broadcasts:
                        self.publish(BROADCAST_TOPIC, cmd)
                    # update state on all clients
                    if self._client_port is not None:
                        self.update_client_state(cmd)
            except Exception as e:
                print(e)
            finally:
                self._queue.task_done()

    def update_client_state(self, command: CommandReq):
        """
            Update all PyTrain clients with the dispatched command. Used to keep
            client states in sync with server
        """
        if self._client_port is not None:
            # noinspection PyTypeChecker
            for client in EnqueueProxyRequests.clients:
                try:
                    with self._lock:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.connect((client, self._client_port))
                            s.sendall(command.as_bytes)
                            _ = s.recv(16)
                except ConnectionRefusedError:
                    # ignore disconnects; client will receive state update on reconnect
                    pass
                except Exception as e:
                    print(f"Exception while sending state update to {client}: {e}")

    def send_current_state(self, client_ip: str):
        """
            When a new client attaches to the server, immediately send it all know
            component states. They will be updated as needed (see update_client_state).
        """
        if self._client_port is not None:
            from ..db.component_state_store import ComponentStateStore
            state = ComponentStateStore.build()
            for scope in state.scopes():
                for address in state.addresses(scope):
                    with self._lock:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            s.connect((client_ip, self._client_port))
                            s.sendall(state.query(scope, address).as_bytes)
                            _ = s.recv(16)

    @property
    def broadcasts_enabled(self) -> bool:
        return self._broadcasts

    def offer(self, cmd: CommandReq) -> None:
        """
            Receive a command from the listener thread and dispatch it to subscribers.
            We do this in a separate thread so that the listener thread doesn't fall behind
        """
        if cmd is not None and isinstance(cmd, CommandReq):
            with self._cv:
                self._queue.put(cmd)
                self._cv.notify()  # wake up receiving thread

    def shutdown(self) -> None:
        with self._cv:
            self._is_running = False
            self._cv.notify()
        CommandDispatcher._instance = None

    @staticmethod
    def _make_channel(channel: Topic,
                      address: int = None,
                      command: CommandDefEnum = None,
                      data: int = None) -> CommandScope | Tuple:
        if channel is None:
            raise ValueError("Channel required")
        elif address is None:
            return channel
        elif command is None:
            return channel, address
        elif data is None:
            return channel, address, command
        elif command.command_def.is_data and data is not None:
            return channel, address, command, data
        else:
            raise TypeError("Command must be Topic or CommandReq")

    def publish_all(self, message: Message, channels: List[CommandScope] = None) -> None:
        if channels is None:  # send to everyone!
            for channel in self._channels:
                self._channels[channel].publish(message)
        else:
            # send only to select channels and tuples with that channel
            for channel in self._channels.keys():
                if channel in channels or (isinstance(channel, tuple) and channel[0] in channels):
                    self._channels[channel].publish(message)

    def publish(self, channel: Topic, message: Message) -> None:
        if channel in self._channels:  # otherwise, we would create a channel simply by referencing i
            self._channels[channel].publish(message)

    def subscribe(self,
                  subscriber: Subscriber,
                  channel: Topic,
                  address: int = None,
                  command: CommandDefEnum = None,
                  data: int = None) -> None:
        if channel == BROADCAST_TOPIC:
            self.subscribe_any(subscriber)
        else:
            self._channels[self._make_channel(channel, address, command, data)].subscribe(subscriber)

    def unsubscribe(self,
                    subscriber: Subscriber,
                    channel: Topic,
                    address: int = None,
                    command: CommandDefEnum = None,
                    data: int = None) -> None:
        if channel == BROADCAST_TOPIC:
            self.unsubscribe_any(subscriber)
        else:
            channel = self._make_channel(channel, address, command, data)
            self._channels[channel].unsubscribe(subscriber)
            if len(self._channels[channel].subscribers) == 0:
                del self._channels[channel]

    def subscribe_any(self, subscriber: Subscriber) -> None:
        # receive broadcasts
        self._channels[BROADCAST_TOPIC].subscribe(subscriber)
        self._broadcasts = True

    def unsubscribe_any(self, subscriber: Subscriber) -> None:
        # receive broadcasts
        self._channels[BROADCAST_TOPIC].unsubscribe(subscriber)
        if not self._channels[BROADCAST_TOPIC].subscribers:
            self._broadcasts = False
