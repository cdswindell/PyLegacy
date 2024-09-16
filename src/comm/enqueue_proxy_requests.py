import socket
from threading import Thread

from src.comm.comm_buffer import CommBuffer
from src.protocol.constants import DEFAULT_SERVER_PORT


class EnqueueProxyRequests(Thread):
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
            cls._instance = super(EnqueueProxyRequests, cls).__new__(cls)
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
