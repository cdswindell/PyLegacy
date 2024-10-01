import abc
import ipaddress
import sched
import socket
import threading
import time
from ipaddress import IPv6Address, IPv4Address
from queue import Queue, Empty
from threading import Thread
from typing import Self

import serial
from serial.serialutil import SerialException

from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_QUEUE_SIZE, DEFAULT_VALID_BAUDRATES
from ..protocol.constants import DEFAULT_THROTTLE_DELAY, DEFAULT_SERVER_PORT


class CommBuffer(abc.ABC):
    __metaclass__ = abc.ABCMeta

    _instance = None
    _lock = threading.Lock()

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
    def parse_server(server: str | IPv4Address | IPv6Address,
                     port: str | int,
                     server_port: int = 0) -> tuple[IPv4Address | IPv6Address | None, str]:
        if server is not None:
            try:
                if isinstance(server, str):
                    server = ipaddress.ip_address(socket.gethostbyname(server))
                if server_port > 0:
                    port = server_port
                elif isinstance(port, str) and not port.isnumeric():
                    port = str(DEFAULT_SERVER_PORT)
            except Exception as e:
                print(f"Failed to resolve {server}: {e} ({type(e)})")
                raise e
        return server, port

    @classmethod
    def build(cls, queue_size: int = DEFAULT_QUEUE_SIZE,
              baudrate: int = DEFAULT_BAUDRATE,
              port: str = DEFAULT_PORT,
              server: str = None
              ) -> Self:
        """
            We only want one or the other of these buffers per process
        """
        server, port = cls.parse_server(server, port)
        if server is None:
            return CommBufferSingleton(queue_size=queue_size, baudrate=baudrate, port=port)
        else:
            return CommBufferProxy(server, int(port))

    @classmethod
    def stop(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.shutdown()

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_server(cls) -> bool:
        if cls.is_built is False:
            raise ValueError("CommBuffer is not built")
        return isinstance(cls._instance, CommBufferSingleton)

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_client(cls) -> bool:
        return isinstance(cls._instance, CommBufferProxy)

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def server_port(cls) -> int | None:
        return None

    @abc.abstractmethod
    def enqueue_command(self, command: bytes, delay: float = 0) -> None:
        """
            Enqueue the command to send to the Lionel LCS SER2
        """
        ...

    @abc.abstractmethod
    def shutdown(self, immediate: bool = False) -> None:
        ...

    @abc.abstractmethod
    def register(self) -> None:
        ...

    @abc.abstractmethod
    def join(self) -> None:
        ...


class CommBufferSingleton(CommBuffer, Thread):
    def __init__(self,
                 queue_size: int = DEFAULT_QUEUE_SIZE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT,
                 ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        if baudrate not in DEFAULT_VALID_BAUDRATES:
            raise ValueError(f"Invalid baudrate: {baudrate}")
        super().__init__(daemon=False, name="PyLegacy Comm Buffer")
        self._baudrate = baudrate
        self._port = port
        self._queue_size = queue_size
        if queue_size:
            self._queue = Queue(queue_size)
        else:
            self._queue = None
        self._shutdown_signalled = False
        self._last_output_at = 0  # used to throttle writes to LCS SER2
        # start the consumer threads
        self._scheduler = DelayHandler(self)
        self.start()

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

    def enqueue_command(self, command: bytes, delay: float = 0) -> None:
        if command:
            # print(f"Enqueue command 0x{command.hex()}")
            if delay > 0:
                self._scheduler.schedule(delay, command)
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

    def register(self) -> None:
        pass  # noop; used to register client

    def run(self) -> None:
        # if the queue is empty AND _shutdown_signaled is True, then continue looping
        while not self._queue.empty() or not self._shutdown_signalled:
            try:
                data = self._queue.get(block=True, timeout=.25)
                # print(f"Fire command 0x{data.hex()}")
                try:
                    with serial.Serial(self.port, self.baudrate) as ser:
                        millis_since_last_output = self._current_milli_time() - self._last_output_at
                        if millis_since_last_output < DEFAULT_THROTTLE_DELAY:
                            time.sleep((DEFAULT_THROTTLE_DELAY - millis_since_last_output) / 1000.)
                        # Write the command byte sequence
                        ser.write(data)
                        self._last_output_at = self._current_milli_time()
                        # print(f"Task Done: 0x{data.hex()}")
                        self._queue.task_done()
                except SerialException as se:
                    # TODO: handle serial errors
                    self._queue.task_done()  # processing is complete, albeit unsuccessful
                    print(f"Task Done (*** SE ***): 0x{data.hex()} {se}")
            except Empty:
                pass


class CommBufferProxy(CommBuffer):
    """
        Allows a Raspberry Pi to "slave" to another so only one serial connection is needed
    """
    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def server_port(cls) -> int | None:
        # noinspection PyProtectedMember
        if cls.is_built is True and cls.is_client is True:
            # noinspection PyProtectedMember
            return cls._instance._port
        raise AttributeError("CommBufferProxy must be built first")

    def __init__(self,
                 server: IPv4Address | IPv6Address,
                 port: int = DEFAULT_SERVER_PORT) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__()
        self._scheduler = DelayHandler(self)
        self._server = server
        self._port = port

    def enqueue_command(self, command: bytes, delay: float = 0) -> None:
        if delay > 0:
            self._scheduler.schedule(delay, command)
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((str(self._server), self._port))
                s.sendall(command)
                _ = s.recv(16)  # we don't care about the response

    def register(self) -> None:
        from src.comm.enqueue_proxy_requests import EnqueueProxyRequests
        # noinspection PyTypeChecker
        self.enqueue_command(EnqueueProxyRequests.register_request)

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
        super().__init__(daemon=True, name="PyLegacy Delay Handler")
        self._buffer = buffer
        self._cv = threading.Condition()
        self._ev = threading.Event()
        self._scheduler = sched.scheduler(time.time, self._ev.wait)
        self.start()

    def run(self) -> None:
        while True:
            with self._cv:
                while self._scheduler.empty():
                    self._cv.wait()
            # run the scheduler outside the cv lock, otherwise,
            #  we couldn't schedule more commands
            self._scheduler.run()
            self._ev.clear()

    def schedule(self, delay: float, command: bytes) -> None:
        with self._cv:
            self._scheduler.enter(delay, 1, self._buffer.enqueue_command, (command, ))
            # this interrupts the running scheduler
            self._ev.set()
            # and this notifies the main thread to restart, as there is a new
            # request in the sched queue
            self._cv.notify()
