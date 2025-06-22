#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import logging
import socket
from collections import defaultdict, deque
from queue import Queue
from threading import Condition, RLock, Thread
from time import sleep
from typing import Generic, List, Protocol, Tuple, TypeVar, cast, runtime_checkable

from ..db.component_state import ComponentState
from ..pdi.amc2_req import Amc2Req
from ..pdi.base_req import BaseReq
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import TMCC_FIRST_BYTE_TO_INTERPRETER, CommandReq
from ..protocol.constants import (
    BROADCAST_TOPIC,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_QUEUE_SIZE,
    DEFAULT_SERVER_PORT,
    DEFAULT_VALID_BAUDRATES,
    LOCO_TRACK_CRANE,
    PROGRAM_NAME,
    CommandScope,
)
from ..protocol.multibyte.multibyte_constants import TMCC2_VARIABLE_INDEX
from ..protocol.tmcc1.tmcc1_constants import SyncCommandDef, TMCC1AuxCommandEnum, TMCC1SyncCommandEnum
from ..protocol.tmcc2.tmcc2_constants import LEGACY_MULTIBYTE_COMMAND_PREFIX, TMCC2EngineCommandEnum
from ..utils.ip_tools import get_ip_address

log = logging.getLogger(__name__)

Message = TypeVar("Message")
Topic = TypeVar("Topic")

SYNCING = CommandReq(TMCC1SyncCommandEnum.SYNCHRONIZING)
SYNC_COMPLETE = CommandReq(TMCC1SyncCommandEnum.SYNCHRONIZED)

#
# Certain Legacy/TMCC commands, such as the Engine Numerics, change core element state, such as
# volume and rpm level. In these cases, we need to requery the Base 3 to get the updated
# impacted state
#
COMMAND_IMPACTS = {
    TMCC1AuxCommandEnum.RELATIVE_SPEED: (lambda x: x.is_amc2, Amc2Req.request_config),
    TMCC1AuxCommandEnum.AUX1_OPT_ONE: (lambda x: x.is_amc2, Amc2Req.request_config),
    TMCC1AuxCommandEnum.AUX2_OPT_ONE: (lambda x: x.is_amc2, Amc2Req.request_config),
    TMCC2EngineCommandEnum.NUMERIC: (
        lambda x: 1 <= x.address <= 99 and x.engine_type != LOCO_TRACK_CRANE,
        BaseReq.request_config,
    ),
}


class CommandListener(Thread):
    _instance: None = None
    _lock = RLock()

    @classmethod
    def build(
        cls,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        ser2_receiver: bool = True,
        base3_receiver: bool = False,
        server_port: int = None,
    ) -> CommandListener:
        """
        Factory method to create a CommandListener instance
        """
        return CommandListener(
            baudrate=baudrate,
            port=port,
            queue_size=queue_size,
            ser2_receiver=ser2_receiver,
            base3_receiver=base3_receiver,
            server_port=server_port,
        )

    @classmethod
    def get(cls) -> CommandListener:
        if cls._instance is None:
            cls.build()
        return cls._instance

    @classmethod
    def listen_for(
        cls, listener: Subscriber, channel: Topic, address: int = None, command: CommandDefEnum = None, data: int = None
    ):
        cls.build().subscribe(listener, channel, address, command, data)

    @classmethod
    def is_built(cls) -> bool:
        return cls._instance is not None

    @classmethod
    def is_running(cls) -> bool:
        # noinspection PyProtectedMember
        return cls._instance is not None and cls._instance._is_running is True

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            if cls._instance:
                cls._instance.shutdown()

    def __init__(
        self,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        ser2_receiver: bool = True,
        base3_receiver: bool = False,
        server_port: int = None,
    ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        if baudrate not in DEFAULT_VALID_BAUDRATES:
            raise ValueError(f"Invalid baudrate: {baudrate}")
        self._baudrate = baudrate
        self._port = port
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Command Listener")

        # prep our consumer(s)
        self._cv = Condition()
        self._deque = deque(maxlen=DEFAULT_QUEUE_SIZE)
        self._is_running = True
        self._dispatcher = CommandDispatcher.build(queue_size, ser2_receiver, base3_receiver, server_port)

        # get initial state from Base 3 and LCS modules
        self.sync_state()

        # start listener thread
        self.start()

        # prep our producer
        if ser2_receiver:
            from .serial_reader import SerialReader

            self._serial_reader = SerialReader(baudrate, port, self)
        else:
            self._serial_reader = None
        self._ser2_receiver = ser2_receiver
        self._base3_receiver = base3_receiver
        self._filter_updates = base3_receiver is True and ser2_receiver is True

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if CommandListener._instance is None:
                # noinspection PyTypeChecker
                CommandListener._instance = super(CommandListener, cls).__new__(cls)
                CommandListener._instance._initialized = False
            return CommandListener._instance

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
        is_tmcc4 = False
        while self._is_running:
            # process bytes, as long as there are any
            with self._cv:
                if not self._deque:
                    self._cv.wait()  # wait to be notified
            # check if the first bite is in the list of allowable command prefixes
            dq_len = len(self._deque)
            if dq_len >= 3 and int(self._deque[0]) in TMCC_FIRST_BYTE_TO_INTERPRETER:
                # At this point, we have some sort of command. It could be a TMCC1 or TMCC2
                # 3-byte command, or, if there are more than 3 bytes, and the 4th byte is
                # 0xf8 or 0xf9 AND the 5th byte is 0xfb, it could be a 9-byte param command.
                # Try for the 9+ byters first
                cmd_bytes = bytes()
                if (
                    dq_len >= 9
                    and self._deque[3] == LEGACY_MULTIBYTE_COMMAND_PREFIX
                    and self._deque[6] == LEGACY_MULTIBYTE_COMMAND_PREFIX
                ) or (
                    dq_len >= 21
                    and self._deque[7] == LEGACY_MULTIBYTE_COMMAND_PREFIX
                    and self._deque[14] == LEGACY_MULTIBYTE_COMMAND_PREFIX
                ):
                    # if dq_len > 9 and byte 3 is the Variable Command marker, go for more
                    if dq_len >= 9 and self._deque[2] == TMCC2_VARIABLE_INDEX:
                        # byte 5 contains the data word count
                        data_words = int(self._deque[5])
                        command_bytes = (5 + data_words) * 3
                        if dq_len < command_bytes:
                            continue  # wait for more
                        else:
                            last_byte = command_bytes
                    else:  # 4-digit engine/train
                        if (
                            dq_len >= 9
                            and self._deque[3] == LEGACY_MULTIBYTE_COMMAND_PREFIX
                            and self._deque[6] == LEGACY_MULTIBYTE_COMMAND_PREFIX
                        ):
                            last_byte = 9
                        else:
                            last_byte = 21
                            is_tmcc4 = True
                    for _ in range(last_byte):
                        cmd_bytes += self._deque.popleft().to_bytes(1, byteorder="big")
                elif dq_len >= 4 and self._deque[3] == LEGACY_MULTIBYTE_COMMAND_PREFIX:
                    # we could be in the middle of receiving a parameter command, wait a bit longer
                    continue
                else:
                    # assume a 3-byte command
                    for _ in range(3):
                        cmd_bytes += self._deque.popleft().to_bytes(1, byteorder="big")
                    # check for 4-digit addressing
                    dq_len -= 3
                    if dq_len >= 4 and cmd_bytes[1] in {0x00, 0x01}:
                        for _ in range(4):
                            cmd_bytes += self._deque.popleft().to_bytes(1, byteorder="big")
                        dq_len -= 4
                        is_tmcc4 = True
                if cmd_bytes:
                    try:
                        # build_req a CommandReq from the received bytes and send it to the dispatcher
                        self._dispatcher.offer(CommandReq.from_bytes(cmd_bytes, is_tmcc4=is_tmcc4))
                        is_tmcc4 = False
                    except ValueError as ve:
                        log.exception(ve)
            elif dq_len < 3:
                continue  # wait for more bytes
            else:
                # pop this byte and continue; we either received unparsable input
                # or started receiving data mid-command
                log.warning(f"Ignoring {hex(self._deque.popleft())} (deque: {len(self._deque)} bytes)")
        # shut down the dispatcher
        if self._dispatcher:
            self._dispatcher.shutdown()

    def offer(self, data: bytes) -> None:
        from .enqueue_proxy_requests import SYNC_BEGIN_RESPONSE, SYNC_COMPLETE_RESPONSE

        if data:
            with self._cv:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"TMCC CommandListener offered: {data.hex(' ')}")
                # check if these are sync start or end commands
                if data in {SYNC_BEGIN_RESPONSE, SYNC_COMPLETE_RESPONSE}:
                    if data == SYNC_BEGIN_RESPONSE:
                        self._dispatcher.offer(SYNCING)
                    else:
                        self._dispatcher.offer(SYNC_COMPLETE)
                else:
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

    def subscribe(
        self,
        listener: Subscriber,
        channel: Topic,
        address: int = None,
        command: CommandDefEnum = None,
        data: int = None,
    ) -> None:
        self._dispatcher.subscribe(listener, channel, address, command, data)

    def unsubscribe(
        self,
        listener: Subscriber,
        channel: Topic,
        address: int = None,
        command: CommandDefEnum = None,
        data: int = None,
    ) -> None:
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

    def __call__(self, message: Message) -> None: ...


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
                log.warning(f"CommandDispatcher: Error publishing {message}; see log for details")
                log.exception(e)


class CommandDispatcher(Thread, Generic[Topic, Message]):
    """
    The CommandDispatcher thread receives parsed CommandReqs from the
    CommandListener and dispatches them to subscribing listeners
    """

    _instance = None
    _lock = RLock()

    @classmethod
    def build(
        cls,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        ser2_receiver: bool = False,
        base3_receiver: bool = False,
        server_port: int = None,
    ) -> CommandDispatcher:
        """
        Factory method to create a CommandDispatcher instance
        """
        return CommandDispatcher(queue_size, ser2_receiver, base3_receiver, server_port)

    @classmethod
    def get(cls) -> CommandDispatcher:
        if cls._instance is None:
            raise AttributeError("Command Dispatcher not yet created")
        return cls._instance

    @classmethod
    def listen_for(
        cls,
        listener: Subscriber,
        channel: Topic,
        address: int = None,
        command: CommandDefEnum = None,
        data: int = None,
    ):
        cls.build().subscribe(listener, channel, address, command, data)

    @classmethod
    def is_running(cls) -> bool:
        # noinspection PyProtectedMember
        return cls._instance is not None and cls._instance._is_running is True

    @classmethod
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

    def __init__(
        self,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        ser2_receiver: bool = False,
        base3_receiver: bool = False,
        server_port: int = None,
    ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        from .enqueue_proxy_requests import EnqueueProxyRequests

        super().__init__(daemon=True, name=f"{PROGRAM_NAME} TMCC Command Dispatcher")
        self._is_ser2_receiver = ser2_receiver
        self._is_base3_receiver = base3_receiver
        self._filter_updates = base3_receiver is True and ser2_receiver is True
        self._channels: dict[Topic | Tuple[Topic, int], Channel[Message]] = defaultdict(Channel)
        self._cv = Condition()  # for queue access
        self._chanel_lock = Condition()  # for publishing
        self._client_lock = Condition()  # for updating client state
        self._is_running = True
        self._queue = Queue[CommandReq](queue_size)
        self._broadcasts = False
        self._is_server = ser2_receiver is True or base3_receiver is True
        if server_port:
            self._server_port = server_port
        elif EnqueueProxyRequests.is_built():
            self._server_port = EnqueueProxyRequests.server_port()
        elif self._is_server is True:
            self._server_port = DEFAULT_SERVER_PORT
            # TODO: this is really an error, fix tests accordingly
            # raise AttributeError("EnqueueProxyRequests not yet built")
        else:
            self._server_port = None
        self._server_ips = get_ip_address()
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
                if isinstance(cmd, CommandReq):
                    # if command is a TMCC1 Halt, send to everyone
                    if cmd.is_halt:
                        if self._filter_updates is True and cmd.is_filtered is True:
                            log.debug(f"Filtering client update: {cmd}")
                        else:
                            self.publish_all(cmd)
                    # if command is a legacy-style halt, send to engines and trains
                    elif cmd.is_system_halt:
                        self.publish_all(cmd, [CommandScope.ENGINE, CommandScope.TRAIN])
                    # otherwise, send to the interested parties
                    else:
                        if cmd.is_data:
                            self.publish((cmd.scope, cmd.address, cmd.command, cmd.data), cmd)
                        self.publish((cmd.scope, cmd.address, cmd.command), cmd)
                        self.publish((cmd.scope, cmd.address), cmd)
                        self.publish(cmd.scope, cmd)
                    if self._broadcasts:
                        self.publish(BROADCAST_TOPIC, cmd)

                    # We need to query state from the Base 3 in response to certain commands.
                    # For example, if we receive a RELATIVE SPEED command on an AMC2, we have to
                    # get the entire AMC2 config to update the new motor speed
                    self.request_command_impact(cmd)

                    # update state on all clients
                    if self._server_port is not None:
                        """
                        When we are listening to broadcasts from both the Base 3 and a Ser2, the
                        TMCC commands broadcast from the Base 3 are also sent out via the Ser2.
                        However, the command stream on the Ser2 lags the base. This can result in
                        command conflicts. For example, when sending speed change commands to the
                        Base 3 to go to speed 10, then 20, then 30, then 40, these directives
                        are echoed back almost instantly via the Base 3 and used to update the
                        LCD display. But, when the Ser2 echos the same commands a few seconds later,
                        the display can look like 10, 20, 30, 10, 40, 30, 40, because the received
                        commands from the Ser2 arrive out of sync.

                        The fix is to filter out the propagation of the Ser2 commands if an equivalent
                        command is broadcast from the Base 3, and if we are listening to both the
                        Base 3 and Ser2. Only a subset of the TMCC commands are sent out via the Base 3.
                        These commands are all marked as "filtered", and are excluded here as well as
                        in ComponentStateStore.
                        """
                        if self._filter_updates is True and cmd.is_filtered is True:
                            log.debug(f"Filtering client update: {cmd}")
                        else:
                            self.update_client_state(cmd)
            except Exception as e:
                log.warning(f"CommandDispatcher: Error publishing {cmd}; see log for details")
                log.exception(e)
            finally:
                self._queue.task_done()

    @property
    def is_ser2_receiver(self) -> bool:
        """
        Returns whether the instance is a Ser2 receiver or not.

        The SER2 receiver is a specific type of receiver characterized by the
        presence of an LCS Ser2 that is broadcasting TMCC commands.

        Returns
        -------
        bool
            True if the instance has the SER2 receiver capability, else False.
        """
        return self._is_ser2_receiver

    @property
    def is_base3_receiver(self) -> bool:
        return self._is_base3_receiver

    @property
    def is_filter_updates(self) -> bool:
        return self._filter_updates

    def signal_clients(
        self,
        option: CommandReq | TMCC1SyncCommandEnum = TMCC1SyncCommandEnum.QUIT,
        client: str = None,
        port: int = None,
    ) -> None:
        if isinstance(option, TMCC1SyncCommandEnum):
            option = CommandReq(option)
        self.update_client_state(option, client=client, port=port)

    def signal_clients_on(
        self, option: CommandReq | TMCC1SyncCommandEnum = TMCC1SyncCommandEnum.QUIT, client: str = None
    ) -> None:
        from .enqueue_proxy_requests import EnqueueProxyRequests

        if isinstance(option, TMCC1SyncCommandEnum):
            option = CommandReq(option)
        for client_ip, port in EnqueueProxyRequests.clients():
            if client_ip == client:
                node_scope = cast(SyncCommandDef, option.command_def).is_node_scope
                self.update_client_state(option, client=client, port=port)
                if node_scope:
                    return

    def signal_client(
        self,
        option: CommandReq | TMCC1SyncCommandEnum = TMCC1SyncCommandEnum.QUIT,
        client: str = None,
        port: int = None,
    ) -> None:
        if isinstance(option, TMCC1SyncCommandEnum):
            option = CommandReq(option)
        self.update_client_state(option, client=client, port=port)

    # noinspection DuplicatedCode
    def update_client_state(self, command: CommandReq, client: str = None, port: int = None):
        """
        Update all PyTrain clients with the dispatched command. Used to keep
        client states in sync with server
        """
        from .enqueue_proxy_requests import EnqueueProxyRequests

        if client is None:
            clients = EnqueueProxyRequests.clients()
        else:
            if port is None:
                port = DEFAULT_SERVER_PORT
            clients = {(client, port)}
        # noinspection PyTypeChecker
        for client, port in clients:
            if client in self._server_ips and port == self._server_port:
                print(f"Skipping update of {client}:{port} {command}")
                continue
            try:
                with self._client_lock:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((client, port))
                        s.sendall(command.as_bytes)
                        _ = s.recv(32)
                    self._client_lock.notify_all()
            except ConnectionRefusedError:
                # ignore disconnects; client will receive state update on reconnect
                pass
            except Exception as e:
                log.warning(f"Exception while sending TMCC state update {command} to {client}")
                log.exception(e)

    # noinspection PyTypeChecker
    def send_current_state(self, client_ip: str, client_port: int = None):
        """
        When a new client attaches to the server, immediately send it all know
        component states. They will be updated as needed (see update_client_state).
        """
        client_port = client_port if client_port else self._server_port
        if client_port is not None:
            from ..db.component_state_store import ComponentStateStore
            from .enqueue_proxy_requests import EnqueueProxyRequests

            # send starting state sync message
            self.send_state_packet(client_ip, client_port, EnqueueProxyRequests.sync_begin_response())
            store = ComponentStateStore.get()
            for scope in store.scopes():
                if scope == CommandScope.SYNC:
                    continue
                for address in store.addresses(scope):
                    with self._client_lock:
                        state: ComponentState = store.query(scope, address)
                        if state is not None:
                            state_bytes = state.as_bytes()
                            if isinstance(state_bytes, bytes):
                                state_bytes = [state_bytes]
                            elif isinstance(state_bytes, list):
                                pass
                            else:
                                raise TypeError(f"Invalid state type: {type(state_bytes)}")
                            do_pause = False
                            for state_packet in state_bytes:
                                if not state_packet:
                                    continue
                                if do_pause:
                                    sleep(0.01)
                                try:
                                    self.send_state_packet(client_ip, client_port, state_packet)
                                    do_pause = True
                                except Exception as e:
                                    log.warning(f"Exception sending state update {state} to {client_ip}:{client_port}")
                                    log.exception(e)
                        self._client_lock.notify_all()
            # send sync_complete message
            self.send_state_packet(client_ip, client_port, EnqueueProxyRequests.sync_complete_response())

    def send_state_packet(self, client_ip: str, client_port: int, state: ComponentState | bytes):
        client_port = client_port if client_port else self._server_port
        packet: bytes | None = None
        try:
            if isinstance(state, bytes):
                packet = state
            elif isinstance(state, ComponentState):
                # TODO: for safety, make this code handle if bytes are returned as list
                packet = state.as_bytes()
            if isinstance(packet, list):
                log.error(f"send_state_packet: Invalid state type: {type(packet)}")

            if packet:  # we can only send states for tracked conditions
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((client_ip, client_port))
                    s.sendall(packet)
                    _ = s.recv(32)
        except Exception as e:
            log.warning(f"Exception sending TMCC state update {state} to {client_ip}:{client_port}")
            log.exception(e)

    @property
    def broadcasts_enabled(self) -> bool:
        return self._broadcasts

    def offer(self, cmd: CommandReq, from_pdi: bool = False) -> None:
        """
        Receive a command from the TMCC listener thread and dispatch it to subscribers.
        We do this in a separate thread so that the listener thread doesn't fall behind.
        """
        if isinstance(cmd, CommandReq):
            with self._cv:
                self._queue.put(cmd)
                self._cv.notify_all()  # wake up receiving thread
                if from_pdi:
                    pass  # TODO: prevent receiving same command from ser2 stream

    def shutdown(self) -> None:
        with self._cv:
            self._is_running = False
            self._cv.notify_all()
        CommandDispatcher._instance = None

    @staticmethod
    def _make_channel(
        channel: Topic,
        address: int = None,
        command: CommandDefEnum = None,
        data: int = None,
    ) -> CommandScope | Tuple:
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
        with self._chanel_lock:
            if channels is None:  # send to everyone!
                for channel in self._channels:
                    self._channels[channel].publish(message)
            else:
                # only send to select channels and tuples with that channel
                for channel in self._channels.keys():
                    if channel in channels or (isinstance(channel, tuple) and channel[0] in channels):
                        self._channels[channel].publish(message)

    def publish(self, channel: Topic, message: Message) -> None:
        with self._chanel_lock:
            if channel in self._channels:  # otherwise, we would create a channel simply by referencing i
                try:
                    self._channels[channel].publish(message)
                except Exception as e:
                    log.exception(f"Exception publishing {message} to {channel}", exc_info=e)
            self._chanel_lock.notify_all()

    def subscribe(
        self,
        subscriber: Subscriber,
        channel: Topic,
        address: int = None,
        command: CommandDefEnum = None,
        data: int = None,
    ) -> None:
        with self._chanel_lock:
            if channel == BROADCAST_TOPIC:
                self.subscribe_any(subscriber)
            else:
                self._channels[self._make_channel(channel, address, command, data)].subscribe(subscriber)

    def unsubscribe(
        self,
        subscriber: Subscriber,
        channel: Topic,
        address: int = None,
        command: CommandDefEnum = None,
        data: int = None,
    ) -> None:
        with self._chanel_lock:
            if channel == BROADCAST_TOPIC:
                self.unsubscribe_any(subscriber)
            else:
                channel = self._make_channel(channel, address, command, data)
                if channel in self._channels:
                    self._channels[channel].unsubscribe(subscriber)
                    if len(self._channels[channel].subscribers) == 0:
                        del self._channels[channel]

    def subscribe_any(self, subscriber: Subscriber) -> None:
        # receive broadcasts
        with self._chanel_lock:
            self._channels[BROADCAST_TOPIC].subscribe(subscriber)
            self._broadcasts = True

    def unsubscribe_any(self, subscriber: Subscriber) -> None:
        # receive broadcasts
        with self._chanel_lock:
            self._channels[BROADCAST_TOPIC].unsubscribe(subscriber)
            if not self._channels[BROADCAST_TOPIC].subscribers:
                self._broadcasts = False

    # noinspection PyArgumentList
    @staticmethod
    def request_command_impact(cmd: CommandReq) -> None:
        action = COMMAND_IMPACTS.get(cmd.command, None)
        if action:
            from ..db.component_state_store import ComponentStateStore

            state = ComponentStateStore.get_state(cmd.scope, cmd.address, create=False)
            if state and action[0](state):
                req = action[1](state)
                req.send()
