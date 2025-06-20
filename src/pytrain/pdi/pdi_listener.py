from __future__ import annotations

import logging
import socket
import threading
from collections import defaultdict, deque
from queue import Queue
from threading import Thread
from typing import Generic, Tuple

from ..comm.command_listener import SYNC_COMPLETE, Channel, CommandDispatcher, Message, Subscriber, Topic
from ..comm.enqueue_proxy_requests import EnqueueProxyRequests
from ..protocol.constants import BROADCAST_TOPIC, DEFAULT_BASE_PORT, DEFAULT_QUEUE_SIZE, PROGRAM_NAME, CommandScope
from ..utils.ip_tools import get_ip_address
from .base_req import BaseReq
from .constants import PDI_EOP, PDI_SOP, PDI_STF, PdiAction, PdiCommand
from .pdi_req import PdiReq, TmccReq

log = logging.getLogger(__name__)


class PdiListener(Thread):
    _instance: None = None
    _lock = threading.RLock()

    @classmethod
    def build(
        cls,
        base3: str = None,
        base3_port: int = DEFAULT_BASE_PORT,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        build_base3_reader: bool = True,
    ) -> PdiListener:
        """
        Factory method to create a CommandListener instance
        """
        if base3 is None:
            build_base3_reader = False
        return PdiListener(base3, base3_port, queue_size, build_base3_reader)

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

    @classmethod
    def enqueue_command(cls, data: bytes | PdiReq) -> None:
        if cls._instance is not None and data:
            if isinstance(data, PdiReq):
                data = data.as_bytes
            # noinspection PyProtectedMember
            cls._instance._base3.send(data)

    @classmethod
    def listen_for(cls, listener: Subscriber, channel: Topic, address: int = None, action: PdiAction = None):
        if cls._instance is not None:
            cls._instance.dispatcher.subscribe(listener, channel, address, action)
        else:
            raise AttributeError("Pdi Listener not initialized")

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if PdiListener._instance is None:
                # noinspection PyTypeChecker
                PdiListener._instance = super(PdiListener, cls).__new__(cls)
                PdiListener._instance._initialized = False
            return PdiListener._instance

    def __init__(
        self,
        base3_addr: str,
        base3_port: int = DEFAULT_BASE_PORT,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        build_base3_reader: bool = True,
    ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        self._base3_addr = base3_addr
        self._base3_port = base3_port
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} PDI Listener {base3_addr}:{base3_port}")

        # open a connection to our Base 3
        if build_base3_reader:
            from .base3_buffer import Base3Buffer

            self._base3 = Base3Buffer(base3_addr, base3_port, queue_size, self)
        else:
            self._base3 = None

        # prep our consumer(s)
        self._cv = threading.Condition()
        self._deque = deque(maxlen=DEFAULT_QUEUE_SIZE)
        self._is_running = True
        self._dispatcher = PdiDispatcher.build(queue_size)

        # start listener thread
        self.start()

    @property
    def dispatcher(self) -> PdiDispatcher:
        return self._dispatcher

    def run(self) -> None:
        eop_pos = -1
        while self._is_running:
            # process bytes, as long as there are any
            with self._cv:
                if not self._deque:
                    self._cv.wait()  # wait to be notified
            # check if the first bite is in the list of allowable command prefixes
            dq_len = len(self._deque)
            while dq_len > 0 and self._is_running:  # may indicate thread is exiting
                # We now begin a state machine where we look for an SOP/EOP pair. Throw away
                # bytes until we see an SOP
                if self._deque[0] == PDI_SOP:
                    # We've found the possible start of a PDI command sequence. Check if we've found
                    # a PDI_EOP byte, or a "stuff" byte; we handle each situation separately
                    # if eop_pos != -1, we have to look past eop_pos for the next possible eop
                    try:
                        eop_pos = self._deque.index(PDI_EOP, eop_pos + 1)
                    except ValueError:
                        # no luck, wait for more bytes; should we impose a maximum byte count?
                        dq_len = -1  # to bypass inner while loop; we need more data
                        continue
                    # make sure the preceding byte isn't a stuff byte
                    if eop_pos - 1 > 0:
                        if self._deque[eop_pos - 1] == PDI_STF:
                            continue  # this EOP is part of the data stream; preceded by STF
                        # we found a complete PDI packet! Queue it for processing
                        req_bytes = bytes()
                        for _ in range(eop_pos + 1):
                            req_bytes += self._deque.popleft().to_bytes(1, byteorder="big")
                            dq_len -= 1
                        try:
                            if log.isEnabledFor(logging.DEBUG):
                                log.debug(f"Offering->0x{req_bytes.hex(':')}")
                            self._dispatcher.offer(PdiReq.from_bytes(req_bytes))
                        except Exception as e:
                            log.error(f"Failed to dispatch request: {req_bytes.hex(':')}")
                            log.exception(e)
                        finally:
                            eop_pos = -1
                        continue  # with while dq_len > 0 loop
                # pop this byte and continue; we either received unparsable input
                # or started receiving data mid-command
                log.warning(f"PdiListener Ignoring {hex(self._deque.popleft())}")
                dq_len -= 1
                eop_pos = -1
        # shut down the dispatcher
        if self._dispatcher:
            self._dispatcher.shutdown()

    def offer(self, data: bytes) -> None:
        if data:
            with self._cv:
                self._deque.extend(data)
                self._cv.notify()

    def shutdown(self) -> None:
        if hasattr(self, "_cv"):
            with self._cv:
                self._is_running = False
                self._cv.notify()
        if hasattr(self, "_dispatcher"):
            if self._dispatcher:
                self._dispatcher.shutdown()
        if hasattr(self, "_base3"):
            if self._base3:
                self._base3.shutdown()
        PdiListener._instance = None

    def subscribe(self, listener: Subscriber, channel: Topic, address: int = None, action: PdiAction = None) -> None:
        self._dispatcher.subscribe(listener, channel, address, action)

    def unsubscribe(self, listener: Subscriber, channel: Topic, address: int = None, action: PdiAction = None) -> None:
        self._dispatcher.unsubscribe(listener, channel, address, action)

    def subscribe_any(self, subscriber: Subscriber) -> None:
        self._dispatcher.subscribe_any(subscriber)

    def unsubscribe_any(self, subscriber: Subscriber) -> None:
        self._dispatcher.unsubscribe_any(subscriber)


class PdiDispatcher(Thread, Generic[Topic, Message]):
    """
    The PdiDispatcher thread receives parsed PdiReqs from the
    PdiListener and dispatches them to subscribing listeners
    """

    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(cls, queue_size: int = DEFAULT_QUEUE_SIZE) -> PdiDispatcher:
        """
        Factory method to create a CommandDispatcher instance
        """
        return PdiDispatcher(queue_size)

    @classmethod
    def is_built(cls) -> bool:
        return cls._instance is not None

    @classmethod
    def get(cls) -> PdiDispatcher:
        if cls._instance is None:
            raise AttributeError("PdiDispatcher has not been initialized")
        return cls._instance

    @classmethod
    def is_running(cls) -> bool:
        # noinspection PyProtectedMember
        return cls._instance is not None and cls._instance._is_running is True

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if PdiDispatcher._instance is None:
                PdiDispatcher._instance = super(PdiDispatcher, cls).__new__(cls)
                PdiDispatcher._instance._initialized = False
            return PdiDispatcher._instance

    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Pdi Dispatcher")
        self._channels: dict[Topic | Tuple[Topic, int], Channel[Message]] = defaultdict(Channel)
        self._cv = threading.Condition()
        self._is_running = True
        self._broadcasts = False
        self._queue = Queue[PdiReq](queue_size)
        self._tmcc_dispatcher = CommandDispatcher.build(queue_size)
        self._server_port = EnqueueProxyRequests.server_port() if EnqueueProxyRequests.is_built() else None
        self._server_ips = get_ip_address()
        self.start()

    @property
    def is_broadcasts_enabled(self) -> bool:
        return self._broadcasts

    def run(self) -> None:
        while self._is_running:
            with self._cv:
                if self._queue.empty():
                    self._cv.wait()
            if self._queue.empty():  # we need to do a second check in the event we're being shutdown
                continue
            cmd: PdiReq = self._queue.get()
            try:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(cmd)
                # update broadcast channels, mostly used for command echoing
                if self._broadcasts:
                    self.publish(BROADCAST_TOPIC, cmd)

                # publish dispatched pdi commands to listeners
                if isinstance(cmd, PdiReq):
                    if isinstance(cmd, BaseReq):
                        # on the PyTrain server, we need to know when the initial
                        # roster sync is complete; we do this by looking for the
                        # response to the request for info on Train 98...
                        if cmd.pdi_command == PdiCommand.BASE_TRAIN and cmd.tmcc_id == 98:
                            CommandDispatcher.get().offer(SYNC_COMPLETE)
                        if cmd.is_ack is True or cmd.is_active is False:
                            continue
                    # for TMCC requests, forward to TMCC Command Dispatcher
                    if isinstance(cmd, TmccReq):
                        self._tmcc_dispatcher.offer(cmd.tmcc_command, from_pdi=True)
                    elif (1 <= cmd.tmcc_id <= 9999) or (cmd.scope == CommandScope.BASE and cmd.tmcc_id == 0):
                        if hasattr(cmd, "action"):
                            self.publish((cmd.scope, cmd.tmcc_id, cmd.action), cmd)
                        self.publish((cmd.scope, cmd.tmcc_id), cmd)
                        self.publish(cmd.scope, cmd)

                        # Update clients of state change. Note that we DO NOT do this
                        # if the command is TMCC command received from the Base, as it
                        # has been handled via the call to tmcc_dispatcher.offer above
                        if self._server_port is not None:
                            self.update_client_state(cmd)
            except Exception as e:
                log.error(f"PdiDispatcher: Error publishing {cmd}")
                log.exception(e)
            finally:
                self._queue.task_done()

    # noinspection DuplicatedCode
    def update_client_state(self, command: PdiReq):
        """
        Update all PyTrain clients with the dispatched command. Used to keep
        client states in sync with serve
        """
        for client, port in EnqueueProxyRequests.clients():
            if client in self._server_ips and port == self._server_port:
                continue  # don't notify ourself
            try:
                with self._lock:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((client, port))
                        s.sendall(command.as_bytes)
                        _ = s.recv(32)
            except ConnectionRefusedError:
                # ignore disconnects; client will receive state update on reconnect
                pass
            except Exception as e:
                log.warning(f"Exception while sending PDI state update {command} to {client}")
                log.exception(e)

    def offer(self, pdi_req: PdiReq | bytes) -> None:
        """
        Receive a command from the listener thread and dispatch it to subscribers.
        We do this in a separate thread so that the listener thread doesn't fall behind
        """
        try:
            if isinstance(pdi_req, bytes):
                pdi_req = PdiReq.from_bytes(pdi_req)
            if isinstance(pdi_req, PdiReq) and not pdi_req.is_ping and not pdi_req.is_ack:
                with self._cv:
                    self._queue.put(pdi_req)
                    self._cv.notify()  # wake up receiving thread
        except Exception as e:
            log.error(e)

    def shutdown(self) -> None:
        with self._cv:
            self._is_running = False
            self._cv.notify()
        PdiDispatcher._instance = None

    @staticmethod
    def _make_channel(channel: Topic, address: int = None, action: PdiAction = None) -> Topic | Tuple:
        if channel is None:
            raise ValueError("Channel required")
        elif address is None:
            return channel
        elif action is None:
            return channel, address
        else:
            return channel, address, action

    def publish(self, channel: Topic, message: Message) -> None:
        if channel in self._channels:  # otherwise, we would create a channel simply by referencing i
            self._channels[channel].publish(message)

    def subscribe(self, subscriber: Subscriber, channel: Topic, address: int = None, action: PdiAction = None) -> None:
        if channel == BROADCAST_TOPIC:
            self.subscribe_any(subscriber)
        else:
            self._channels[self._make_channel(channel, address, action)].subscribe(subscriber)

    def unsubscribe(
        self, subscriber: Subscriber, channel: Topic, address: int = None, command: PdiAction = None
    ) -> None:
        if channel == BROADCAST_TOPIC:
            self.unsubscribe_any(subscriber)
        else:
            channel = self._make_channel(channel, address, command)
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
