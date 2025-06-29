from __future__ import annotations

import abc
import ipaddress
import logging
import sched
import socket
import sys
import threading
import time
import uuid
from ipaddress import IPv6Address, IPv4Address
from queue import Queue, Empty
from threading import Thread, Event, Lock, Condition

from ..db.component_state import ComponentState
from ..pdi.pdi_req import PdiReq
from ..protocol.command_req import CommandReq
from ..protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum

if sys.version_info >= (3, 11):
    from typing import Self, Dict
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

import serial
from serial.serialutil import SerialException

from ..protocol.constants import (
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_QUEUE_SIZE,
    DEFAULT_VALID_BAUDRATES,
    PROGRAM_NAME,
    DEFAULT_PULSE,
)
from ..protocol.constants import DEFAULT_SER2_THROTTLE_DELAY, DEFAULT_SERVER_PORT

log = logging.getLogger(__name__)


class CommBuffer(abc.ABC):
    from ..db.component_state import ComponentState

    __metaclass__ = abc.ABCMeta

    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if CommBuffer._instance is None:
                CommBuffer._instance = super(CommBuffer, cls).__new__(cls)
                CommBuffer._instance._initialized = False
            return CommBuffer._instance

    @staticmethod
    def parse_server(
        server: str | IPv4Address | IPv6Address, port: str | int, server_port: int = 0
    ) -> tuple[IPv4Address | IPv6Address | None, str]:
        if server is not None:
            try:
                if isinstance(server, str):
                    server = ipaddress.ip_address(socket.gethostbyname(server))
                if server_port > 0:
                    port = server_port
                elif isinstance(port, str) and not port.isnumeric():
                    port = str(DEFAULT_SERVER_PORT)
            except Exception as e:
                log.error(f"Failed to resolve {server}: {e}")
                log.exception(e)
                raise e
        return server, port

    @classmethod
    def build(
        cls,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
        ser2=False,
    ) -> Self:
        if cls._instance:
            return cls._instance
        """
        We only want one or the other of these buffers per process
        """
        server, port = cls.parse_server(server, port)
        if server is None:
            return CommBufferSingleton(queue_size=queue_size, baudrate=baudrate, port=port, ser2=ser2)
        else:
            return CommBufferProxy(server, int(port))

    @classmethod
    def get(cls) -> CommBuffer:
        if cls._instance is None:
            raise AttributeError("CommBuffer has not been initialized")
        return cls._instance

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown()

    @classmethod
    def is_built(cls) -> bool:
        return cls._instance is not None

    @classmethod
    def is_server(cls) -> bool:
        if not cls.is_built():
            raise ValueError("CommBuffer is not built")
        return isinstance(cls._instance, CommBufferSingleton)

    @classmethod
    def is_client(cls) -> bool:
        return isinstance(cls._instance, CommBufferProxy)

    @classmethod
    def no_ser2(cls) -> bool:
        return True

    @classmethod
    def server_port(cls) -> int | None:
        return None

    @classmethod
    def server_ip(cls) -> str | None:
        return None

    @abc.abstractmethod
    def enqueue_command(self, command: bytes, delay: float = 0) -> None:
        """
        Enqueue the command to send to the Lionel LCS SER2
        """
        ...

    @abc.abstractmethod
    def update_state(self, state: ComponentState | CommandReq | PdiReq | bytes) -> None:
        """
        Update all nodes with the state change
        """
        ...

    @abc.abstractmethod
    def shutdown(self, immediate: bool = False) -> None: ...

    @abc.abstractmethod
    def register(self, port: int = DEFAULT_SERVER_PORT) -> None: ...

    @abc.abstractmethod
    def disconnect(self, port: int = DEFAULT_SERVER_PORT) -> None: ...

    @abc.abstractmethod
    def sync_state(self, port: int = DEFAULT_SERVER_PORT) -> None: ...

    @abc.abstractmethod
    def start_heart_beat(self, port: int = DEFAULT_SERVER_PORT): ...

    @abc.abstractmethod
    def join(self) -> None: ...

    @property
    @abc.abstractmethod
    def server_version(self) -> tuple[int, int, int]: ...

    @property
    @abc.abstractmethod
    def base3_address(self) -> str: ...

    @base3_address.setter
    @abc.abstractmethod
    def base3_address(self, value: str) -> None: ...

    @property
    @abc.abstractmethod
    def session_id(self) -> uuid.UUID: ...


class CommBufferSingleton(CommBuffer, Thread):
    def __init__(
        self,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        ser2: bool = False,
    ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        if baudrate not in DEFAULT_VALID_BAUDRATES:
            raise ValueError(f"Invalid baudrate: {baudrate}")
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} TMCC Command Buffer")
        self._baudrate = baudrate
        self._port = port
        self._queue_size = queue_size
        self._ser2 = ser2
        if queue_size:
            self._queue = Queue(queue_size)
        else:
            self._queue = None
        self._base3_address = None
        self._shutdown_signalled = False
        self._last_output_at = 0  # used to throttle writes to LCS SER2
        # if there is no Ser2, send commands via Base 3
        from ..pdi.base3_buffer import Base3Buffer

        self._base3: Base3Buffer | None = None
        self._use_base3 = False
        self._tmcc_dispatcher = None
        self._uuid: uuid.UUID = uuid.uuid4()  # uniquely identify this instance of the server

        # start the consumer threads
        self._scheduler = DelayHandler(self)
        self.start()

    def update_state(self, state: ComponentState | CommandReq | PdiReq | bytes) -> None:
        """
        Force a state update thru the system. Used to handle
        non-Lionel actors, like automatic train control blocks.
        """
        from .command_listener import CommandDispatcher
        from ..pdi.pdi_listener import PdiDispatcher
        from ..pdi.constants import PDI_SOP, PDI_EOP

        # if we got a state, remember it, otherwise, we have to
        # parse the byte stream and convert
        if isinstance(state, ComponentState):
            state = state.as_bytes
            if isinstance(state, list):
                state = b"".join(state)

        state_cmds = []
        if isinstance(state, bytes):
            # this is the hard one, the byte stream could be a mixture of PDI and TMCC
            # commands; we have to go thru and dispatch to the correct listener. With
            # that said, as a simplification, we will assume that the methods that call
            # this function are not mixed modal and the byte stream will either be a
            # CommandReq or a PdiReq
            # TODO: parse mixed modal stream
            if state[0] == PDI_SOP and state[-1] == PDI_EOP:
                state_cmds.append(PdiReq.from_bytes(state))
            else:
                state_cmds.append(CommandReq.from_bytes(state))
        elif isinstance(state, CommandReq):
            state_cmds.append(state)
        elif isinstance(state, PdiReq):
            state_cmds.append(state)
        else:
            raise AttributeError(f"Invalid state: {state}")
        for state_cmd in state_cmds:
            if isinstance(state_cmd, CommandReq):
                CommandDispatcher.get().offer(state_cmd)
            elif isinstance(state_cmd, PdiReq):
                PdiDispatcher.get().offer(state_cmd)

    def start_heart_beat(self, port: int = DEFAULT_SERVER_PORT):
        raise NotImplementedError

    @property
    def server_version(self) -> tuple[int, int, int]:
        from .. import get_version_tuple

        return get_version_tuple()

    @property
    def base3_address(self) -> str:
        return self._base3_address

    @base3_address.setter
    def base3_address(self, value: str) -> None:
        self._base3_address = value

    @property
    def session_id(self) -> uuid.UUID:
        return self._uuid

    @staticmethod
    def _current_milli_time() -> int:
        """
        Return the current time, in milliseconds past the "epoch"
        """
        return round(time.time() * 1000)

    @property
    def port(self) -> str:
        return self._port

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def is_ser2(self) -> bool:
        return self._ser2

    @property
    def is_use_base3(self) -> bool:
        return self._use_base3

    @is_use_base3.setter
    def is_use_base3(self, value: bool) -> None:
        from ..pdi.base3_buffer import Base3Buffer
        from .command_listener import CommandDispatcher

        self._use_base3 = value
        if value is True and self._base3 is None:
            with self._lock:
                if self._base3 is None:
                    self._base3 = Base3Buffer.get()
                if self._tmcc_dispatcher is None:
                    self._tmcc_dispatcher = CommandDispatcher.get()

    def enqueue_command(self, command: bytes, delay: float = 0) -> None:
        from ..pdi.constants import PDI_SOP

        if command:
            log.debug(f"Enqueue command 0x{command.hex()}")
            if delay > 0:
                self._scheduler.schedule(delay, command)
            else:
                if command[0] == PDI_SOP:
                    # send to Base 3 if one is available
                    if self._base3:
                        self._base3.send(command)
                    else:
                        log.error(f"Request to send packet to Base 3, but no Base 3 available: {command.hex()}")
                else:
                    self._queue.put(command)

    def shutdown(self, immediate: bool = False) -> None:
        if immediate:
            with self._queue.mutex:
                self._queue.queue.clear()
                self._queue.all_tasks_done.notify_all()
                self._queue.unfinished_tasks = 0
        self._shutdown_signalled = True

    def join(self) -> None:
        super().join()

    def register(self, port: int = DEFAULT_SERVER_PORT) -> None:
        pass  # noop; used to register client

    def disconnect(self, port: int = DEFAULT_SERVER_PORT) -> None:
        pass  # noop; used to disconnect client

    def sync_state(self, port: int = DEFAULT_SERVER_PORT) -> None:
        pass  # noop; used by client to request server state

    def run(self) -> None:
        # if the queue is not empty AND _shutdown_signaled is False, then exit
        while not self._queue.empty() or not self._shutdown_signalled:
            data = None
            try:
                data = self._queue.get(block=True, timeout=0.25)
                if self.is_use_base3 is True or self.is_ser2 is False:
                    self.base3_send(data)
                else:
                    self.ser2_send(data)
            except Empty:
                pass
            except Exception as e:
                log.error(f"Error sending {data.hex()}")
                log.exception(e)
            finally:
                if data is not None:
                    self._queue.task_done()

    def ser2_send(self, data):
        try:
            with serial.Serial(self.port, self.baudrate) as ser:
                millis_since_last_output = self._current_milli_time() - self._last_output_at
                if millis_since_last_output < DEFAULT_SER2_THROTTLE_DELAY:
                    time.sleep((DEFAULT_SER2_THROTTLE_DELAY - millis_since_last_output) / 1000.0)
                # Write the command byte sequence
                ser.write(data)
                self._last_output_at = self._current_milli_time()
                # inform Base 3 of state change, if available
                from ..pdi.base3_buffer import Base3Buffer

                Base3Buffer.sync_state(data)
        except SerialException as se:
            # TODO: handle serial errors
            log.exception(se)

    def base3_send(self, data: bytes):
        from ..pdi.constants import PdiCommand
        from ..pdi.pdi_req import TmccReq

        tmcc_cmd = CommandReq.from_bytes(data)
        if tmcc_cmd.address > 99:
            pdi_cmd = TmccReq(tmcc_cmd, PdiCommand.TMCC4_TX)
        else:
            pdi_cmd = TmccReq(tmcc_cmd, PdiCommand.TMCC_TX)
        self._base3.send(pdi_cmd.as_bytes)
        # also inform CommandDispatcher to update system state
        if self.is_ser2 is False or tmcc_cmd.is_force_state_update is True:
            self._tmcc_dispatcher.offer(tmcc_cmd)


COMM_ERROR_CODES: Dict[int, str] = {
    48: "ADDRESS IN USE",
    60: "TIMEOUT",
    61: "REFUSED",
    64: "HOST DOWN",
    65: "NO ROUTE",
    113: "NO ROUTE",
    120: "CONN ERR",
}


class CommBufferProxy(CommBuffer):
    """
    Allows a Raspberry Pi to "slave" to another so only one serial connection is needed
    """

    from ..db.component_state import ComponentState

    @classmethod
    def server_port(cls) -> int | None:
        # noinspection PyProtectedMember
        if cls.is_built() is True and cls.is_client() is True:
            # noinspection PyProtectedMember
            return cls._instance._port
        raise AttributeError("CommBufferProxy must be built first")

    # noinspection PyProtectedMember
    @classmethod
    def server_ip(cls) -> str:
        if cls.is_built() is True and cls.is_client() is True and cls._instance._ephemeral_port:
            return cls._instance._ephemeral_port[0]
        raise AttributeError("CommBufferProxy must be built first")

    def __init__(self, server: IPv4Address | IPv6Address = None, port: int = DEFAULT_SERVER_PORT) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__()
        self._scheduler = DelayHandler(self)
        self._server = server
        self._port = port
        self._ephemeral_port = None
        self._client_port = None
        self._base3_address = None
        self._server_version = None
        self._uuid: uuid.UUID = uuid.uuid4()
        self._server_version_available = Event()
        self._heart_beat_thread = None

    def start_heart_beat(self, port: int = DEFAULT_SERVER_PORT):
        self._heart_beat_thread = ClientHeartBeat(self)

    @property
    def server_version(self) -> tuple[int, int, int]:
        return self._server_version

    @property
    def base3_address(self) -> str:
        return self._base3_address

    @base3_address.setter
    def base3_address(self, value: str) -> None:
        pass

    @property
    def session_id(self) -> uuid.UUID:
        return self._uuid

    @property
    def client_port(self) -> int:
        return self._client_port

    def server_version_available(self) -> Event:
        return self._server_version_available

    def enqueue_command(self, command: bytes, delay: float = 0) -> None:
        if delay > 0:
            self._scheduler.schedule(delay, command)
        else:
            retries = 0
            while True:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(5.0)
                        s.connect((str(self._server), self._port))
                        s.settimeout(None)
                        s.sendall(command)
                        resp = s.recv(32)  # response contains Base 3 Addr as well as the server version
                        if self._server_version is None and len(resp) >= 3:
                            self._server_version = (resp[0], resp[1], resp[2])
                            self._server_version_available.set()
                        resp = resp[3:] if len(resp) > 3 else resp
                        if self._base3_address is None:
                            self._base3_address = resp.decode("utf-8", "ignore")
                        if self._ephemeral_port is None:
                            self._ephemeral_port = s.getsockname()
                    return
                except OSError as oe:
                    if retries < 90:
                        retries += 1
                        if retries % 5 == 0:
                            e_msg = COMM_ERROR_CODES.get(oe.errno, f"UNKNOWN ({oe.errno})")
                            log.info(f"Looking for {PROGRAM_NAME} server at {self._server}... [{e_msg}]")
                        if not isinstance(oe, TimeoutError):
                            time.sleep(1)
                        continue
                    raise oe

    def update_state(self, state: ComponentState | CommandReq | PdiReq | bytes) -> None:
        """
        Allow a state update to be sent to server and all clients.
        Implemented to support automatic train control Blocks
        but could support other IPC state updates that are not of
        Lionel origin in the future.
        """
        from .enqueue_proxy_requests import SENDING_STATE_REQUEST

        if state:
            if isinstance(state, ComponentState) or isinstance(state, CommandReq) or isinstance(state, PdiReq):
                state_bytes = state.as_bytes
            elif isinstance(state, bytes):
                state_bytes = state
            else:
                raise ValueError(f"Invalid state: {state}")
            if isinstance(state_bytes, bytes):
                state_bytes = [state_bytes]
            elif isinstance(state_bytes, list):
                pass
            else:
                raise ValueError(f"Invalid state bytes format: {state}: {type(state_bytes)}")
            for packet in state_bytes:
                self.enqueue_command(SENDING_STATE_REQUEST + packet)

    def register(self, port: int = DEFAULT_SERVER_PORT) -> None:
        from ..comm.enqueue_proxy_requests import EnqueueProxyRequests

        self._client_port = port
        while True:
            from .. import get_version_tuple

            self.enqueue_command(
                EnqueueProxyRequests.register_request(
                    port,
                    self.session_id,
                    get_version_tuple(),
                )
            )
            return

    def disconnect(self, port: int = None) -> None:
        port = self._client_port if port is None else port
        try:
            from ..comm.enqueue_proxy_requests import EnqueueProxyRequests

            if self._heart_beat_thread:
                self._heart_beat_thread.shutdown()
            self.enqueue_command(EnqueueProxyRequests.disconnect_request(port, self.session_id))
            return
        except ConnectionError as ce:
            raise ce

    def sync_state(self, port: int = None) -> None:
        port = self._client_port if port is None else port
        try:
            from ..comm.enqueue_proxy_requests import EnqueueProxyRequests

            # noinspection PyTypeChecker
            self.enqueue_command(EnqueueProxyRequests.sync_state_request(port, self.session_id))
        except ConnectionError as ce:
            raise ce

    def shutdown(self, immediate: bool = False) -> None:
        pass

    def join(self):
        pass


class DelayHandler(Thread):
    """
    Handle delayed (scheduled) requests. Implementation uses Python's lightweight
    sched module to keep a list of requests to issue in the future. We use
    threading.Event.wait() as the sleep function, as it is interruptable. This
    allows us to schedule requests in any order and still have them fire at the
    appropriate time.
    """

    def __init__(self, buffer: CommBuffer) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Command Delay Handler")
        self._buffer = buffer
        self._cv = Condition()
        self._ev = Event()
        self._scheduler = sched.scheduler(time.time, self._ev.wait)
        self.start()

    def run(self) -> None:
        while True:
            with self._cv:
                while self._scheduler.empty():
                    self._cv.wait()
            # run the scheduler outside the cv lock; otherwise,
            # we couldn't schedule more commands
            self._scheduler.run()
            self._ev.clear()

    def schedule(self, delay: float, command: bytes) -> None:
        with self._cv:
            self._scheduler.enter(delay, 1, self._buffer.enqueue_command, (command,))
            # this interrupts the running scheduler
            self._ev.set()
            # and this notifies the main thread to restart, as there is a new
            # request in the sched queue
            self._cv.notify()


class ClientHeartBeat(Thread):
    def __init__(self, tmcc_buffer: CommBufferProxy) -> None:
        from .. import CommandReq

        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Client Heart Beat")
        self._tmcc_buffer = tmcc_buffer
        self._client_port = tmcc_buffer.client_port
        heartbeat = CommandReq(TMCC1SyncCommandEnum.KEEP_ALIVE).as_bytes
        self._heartbeat_bytes = (
            heartbeat + int(self._client_port & 0xFFFF).to_bytes(2, byteorder="big") + tmcc_buffer.session_id.bytes
        )
        self._ev = threading.Event()
        self._is_running = True
        self.start()

    def shutdown(self) -> None:
        self._is_running = False
        self._ev.set()

    def run(self) -> None:
        while self._is_running:
            self._ev.wait(DEFAULT_PULSE)
            if self._is_running:
                self._tmcc_buffer.enqueue_command(self._heartbeat_bytes)
