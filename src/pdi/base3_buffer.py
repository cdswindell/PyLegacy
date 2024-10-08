import socket
import threading
import time

from threading import Condition, Thread

from .constants import KEEP_ALIVE_CMD
from .pdi_listener import PdiListener

from ..protocol.constants import DEFAULT_BASE3_PORT, DEFAULT_QUEUE_SIZE
from ..utils.pollable_queue import PollableQueue


class Base3Buffer(Thread):
    _instance: None = None
    _lock = threading.RLock()

    @classmethod
    def stop(cls) -> None:
        if cls._instance is not None:
            cls._instance.shutdown()

    def __init__(self,
                 base3_addr: str,
                 base3_port: int = DEFAULT_BASE3_PORT,
                 buffer_size: int = DEFAULT_QUEUE_SIZE,
                 listener: PdiListener = None) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Base3 Interface")
        # create connection to Base 3 box
        self._base3_addr = base3_addr
        self._base3_port = base3_port
        self._listener = listener
        self._is_running = True
        self._send_queue: PollableQueue[bytes] = PollableQueue(buffer_size)
        self._send_cv = Condition()
        self._keep_alive = KeepAlive(self)
        self.start()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in a process
        """
        with cls._lock:
            if Base3Buffer._instance is None:
                Base3Buffer._instance = super(Base3Buffer, cls).__new__(cls)
                Base3Buffer._instance._initialized = False
            return Base3Buffer._instance

    def send(self, data: bytes) -> None:
        if data:
            with self._send_cv:
                self._send_queue.put(data)
                self._send_cv.notify_all()

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((str(self._base3_addr), self._base3_port))
            # we want to wait on either data being available to send to the Base3 of
            # data available from the Base 3 to process
            socket_list = [s, self._send_queue]
            while self._is_running:
                for sock in socket_list:
                    if sock == self._send_queue:
                        data = sock.get()
                        s.sendall(data.hex().upper().encode())
                    # we will always call s.recv, as in either case, there will
                    # be a response, either because we received an 'ack' from
                    # our send or because the select was triggered on the socket
                    # being able to be read.
                    data = bytes.fromhex(s.recv(512).decode())
                    # but there is more trickiness; The Base3 sends ascii characters
                    # so when we receive: 'D12729DF', this actually is sent as eight
                    # characters; D, 1, 2, 7, 2, 9, D, F, so we must decode the 8
                    # received bytes into 8 ASCII characters, then interpret that
                    # ASCII string as Hex representation to arrive at 0xd12729df...
                    if self._listener is not None:
                        self._listener.offer(data)

    def shutdown(self) -> None:
        self._is_running = False


class KeepAlive(Thread):
    def __init__(self, writer: Base3Buffer) -> None:
        super().__init__(daemon=True, name="PyLegacy Base3 Keep Alive")
        self._writer = writer
        self._is_running = True
        self.start()

    def run(self) -> None:
        while self._is_running:
            self._writer.send(KEEP_ALIVE_CMD)
            time.sleep(2)
