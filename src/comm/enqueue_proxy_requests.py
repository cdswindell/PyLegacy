import socket
import threading
from threading import Thread

from src.comm.comm_buffer import CommBuffer
from src.protocol.constants import DEFAULT_SERVER_PORT


class EnqueueProxyRequests(Thread):
    _instance = None
    _lock = threading.RLock()

    def __init__(self,
                 buffer: CommBuffer,
                 port: int = DEFAULT_SERVER_PORT
                 ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Enqueue Receiver")
        self._buffer = buffer
        self._port = port
        self.start()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in the system
        """
        with cls._lock:
            if EnqueueProxyRequests._instance is None:
                EnqueueProxyRequests._instance = super(EnqueueProxyRequests, cls).__new__(cls)
                EnqueueProxyRequests._instance._initialized = False
            return EnqueueProxyRequests._instance

    def run(self) -> None:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(('', self._port))
            s.listen(1)
            while True:
                conn, addr = s.accept()
                try:
                    print(f"Connected {conn} {addr}")
                    byte_stream = bytes()
                    while True:
                        data = conn.recv(128)
                        if data:
                            # print(f"Received data: {data.hex()}, sending ack")
                            byte_stream += data
                            conn.sendall(str.encode("ack"))
                        else:
                            # print("no more data from client")
                            break
                    # print(f"Received {byte_stream.hex()}")
                    self._buffer.enqueue_command(byte_stream)
                finally:
                    conn.close()
