import abc
import ipaddress
import socket
import time
from abc import ABC
from ipaddress import IPv6Address, IPv4Address
from queue import Queue, Empty
from threading import Thread
from typing import Self

import serial
from serial.serialutil import SerialException

from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_QUEUE_SIZE, DEFAULT_THROTTLE_DELAY, \
    DEFAULT_SERVER_PORT


class CommBuffer(ABC):
    __metaclass__ = abc.ABCMeta

    @staticmethod
    def parse_server(server: str, port: str) -> tuple[IPv4Address | IPv6Address | None, str]:
        if server is not None:
            try:
                server = ipaddress.ip_address(socket.gethostbyname(server))
                if not port.isnumeric():
                    port = str(DEFAULT_SERVER_PORT)
                print(f"Server {server} IP: {server} Port: {port}")
            except Exception as e:
                print(f"Failed to resolve {server}: {e} ({type(e)})")
                raise e
        return server, port

    @classmethod
    def build(cls, queue_size: int = DEFAULT_QUEUE_SIZE,
              baudrate: int = DEFAULT_BAUDRATE,
              port: str = DEFAULT_PORT,
              server: IPv4Address | IPv6Address = None
              ) -> Self:
        if server is None:
            print("Sending commands directly to LCS Ser2...")
            return CommBufferSingleton(queue_size=queue_size, baudrate=baudrate, port=port)
        else:
            print(f"Sending commands to Proxy at {server}:{port}...")
            return CommBufferProxy(server, int(port))

    @abc.abstractmethod
    def enqueue_command(self, command: bytes) -> None:
        """
            Enqueue the command to send to the Lionel LCS SER2
        """
        pass

    @abc.abstractmethod
    def shutdown(self, immediate: bool = False) -> None:
        pass

    @abc.abstractmethod
    def join(self):
        pass


class CommBufferSingleton(CommBuffer, Thread):
    _instance = None

    def __init__(self,
                 queue_size: int = DEFAULT_QUEUE_SIZE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT,
                 ) -> None:
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
        self.start()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in the system
        """
        if not cls._instance:
            cls._instance = super(CommBufferSingleton, cls).__new__(cls)
        return cls._instance

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

    def enqueue_command(self, command: bytes) -> None:
        if command:
            print(f"Enqueue command 0x{command.hex()}")
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

    def run(self) -> None:
        # if the queue is empty AND _shutdown_signaled is True, then continue looping
        while not self._queue.empty() or not self._shutdown_signalled:
            try:
                data = self._queue.get(block=True, timeout=.25)
                print(f"Fire command 0x{data.hex()}")
                try:
                    with serial.Serial(self.port, self.baudrate) as ser:
                        millis_since_last_output = self._current_milli_time() - self._last_output_at
                        if millis_since_last_output < DEFAULT_THROTTLE_DELAY:
                            time.sleep((DEFAULT_THROTTLE_DELAY - millis_since_last_output) / 1000.)
                        # Write the command byte sequence
                        ser.write(data)
                        self._last_output_at = self._current_milli_time()
                        print(f"Task Done: 0x{data.hex()}")
                        self._queue.task_done()
                except SerialException as se:
                    # TODO: handle serial errors
                    print(se)
                    print(f"Task Done (*** SE ***): 0x{data.hex()}")
                    self._queue.task_done()  # processing is complete, albeit unsuccessful
            except Empty:
                pass


class EnqueueReceiver(Thread):
    _instance = None

    def __init__(self,
                 buffer: CommBuffer,
                 port: int = DEFAULT_SERVER_PORT
                 ) -> None:
        super().__init__(daemon=True, name="PyLegacy Enqueue Receiver")
        self._buffer = buffer
        self._port = port
        self.start()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in the system
        """
        if not cls._instance:
            cls._instance = super(EnqueueReceiver, cls).__new__(cls)
        return cls._instance

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", self._port))
            s.listen(1)
            while True:
                conn, addr = s.accept()
                try:
                    print(f"Connected {conn} {addr}")
                    byte_stream = bytes()
                    while True:
                        data = conn.recv(128)
                        if data:
                            print(f"Received data: {data.hex()}, sending ack")
                            byte_stream += data
                            conn.sendall(str.encode("ack"))
                        else:
                            print("no more data from client")
                            break
                    print(f"Received {byte_stream.hex()}")
                    self._buffer.enqueue_command(byte_stream)
                finally:
                    conn.close()


class CommBufferProxy(CommBuffer):
    """
        Allows a Raspberry Pi to "slave" to another so only one serial connection is needed
    """

    def __init__(self,
                 server: IPv4Address | IPv6Address,
                 port: int = DEFAULT_SERVER_PORT) -> None:
        super().__init__()
        self._server = server
        self._port = port

    def enqueue_command(self, command: bytes) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((str(self._server), self._port))
        try:
            print(f"sending command 0x{command.hex()}")
            s.sendall(command)
            print("Waiting for ACK...")
            data = s.recv(1024)
            print(f"CommBufferProxy.enqueue_command({command}) {data}")
        finally:
            s.close()

    def shutdown(self, immediate: bool = False) -> None:
        pass

    def join(self):
        pass
