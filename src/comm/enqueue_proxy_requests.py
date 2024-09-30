from __future__ import annotations

import socketserver
import threading
from threading import Thread

from src.comm.comm_buffer import CommBuffer
from src.protocol.constants import DEFAULT_SERVER_PORT


class EnqueueHandler(socketserver.BaseRequestHandler):
    def handle(self):
        byte_stream = bytes()
        while True:
            data = self.request.recv(128)
            if data:
                byte_stream += data
                self.request.sendall(str.encode("ack"))
            else:
                break
        EnqueueProxyRequests.get_comm_buffer().enqueue_command(byte_stream)


class EnqueueProxyRequests(Thread):
    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(cls, buffer: CommBuffer, port: int = DEFAULT_SERVER_PORT) -> EnqueueProxyRequests:
        """
            Factory method to create a CommandListener instance
        """
        return EnqueueProxyRequests(buffer, port)

    @classmethod
    def stop(cls) -> None:
        if cls._instance is not None:
            cls._instance.shutdown()

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

    @classmethod
    def get_comm_buffer(cls) -> CommBuffer:
        return cls._instance.buffer if cls._instance is not None else None

    def __init__(self,
                 buffer: CommBuffer,
                 port: int = DEFAULT_SERVER_PORT
                 ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Enqueue Receiver")
        self._buffer: CommBuffer = buffer
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

    @property
    def buffer(self) -> CommBuffer:
        return self._buffer

    def run(self) -> None:
        # noinspection PyTypeChecker
        with socketserver.TCPServer(('', self._port), EnqueueHandler) as server:
            print(server)
            server.serve_forever()
        print("Server done)")

    def shutdown(self) -> None:
        # noinspection PyTypeChecker
        with socketserver.TCPServer(('', self._port), EnqueueHandler) as server:
            server.shutdown()

    # def run(self) -> None:
    #     with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
    #         s.bind(('', self._port))
    #         s.listen(1)
    #         while True:
    #             conn, addr = s.accept()
    #             try:
    #                 byte_stream = bytes()
    #                 while True:
    #                     data = conn.recv(128)
    #                     if data:
    #                         # print(f"Received data: {data.hex()}, sending ack")
    #                         byte_stream += data
    #                         conn.sendall(str.encode("ack"))
    #                     else:
    #                         # print("no more data from client")
    #                         break
    #                 # print(f"Received {byte_stream.hex()}")
    #                 self._buffer.enqueue_command(byte_stream)
    #             finally:
    #                 conn.close()
