from __future__ import annotations

import logging
import socketserver
import threading
from threading import Thread
from typing import List

from ..comm.comm_buffer import CommBuffer
from ..protocol.constants import DEFAULT_SERVER_PORT

log = logging.getLogger(__name__)

REGISTER_REQUEST: bytes = int(0xFF).to_bytes(1, byteorder="big") * 6
DISCONNECT_REQUEST: bytes = int(0xFFFC).to_bytes(2, byteorder="big") * 3
SYNC_STATE_REQUEST: bytes = int(0xFFF0).to_bytes(2, byteorder="big") * 3


class EnqueueProxyRequests(Thread):
    """
    Receives requests from PyTrain clients over TCP/IP and queues them for
    dispatch to the LCS SER2.
    """

    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(cls, buffer: CommBuffer, port: int = DEFAULT_SERVER_PORT) -> EnqueueProxyRequests:
        """
        Factory method to create a EnqueueProxyRequests instance
        """
        return EnqueueProxyRequests(buffer, port)

    @classmethod
    def enqueue_tmcc_packet(cls, data: bytes) -> None:
        EnqueueProxyRequests.get_comm_buffer().enqueue_command(data)

    @classmethod
    def note_client_addr(cls, client: str) -> None:
        """
        Take note of client IPs, so we can update them of component state changes
        """
        if cls._instance is not None:
            # noinspection PyProtectedMember
            cls._instance._clients.add(client)

    @classmethod
    def client_disconnect(cls, client: str) -> None:
        """
        Remove client so we don't send more state updates
        """
        if cls._instance is not None:
            # noinspection PyProtectedMember
            if client in cls._instance._clients:
                # noinspection PyProtectedMember
                cls._instance._clients.remove(client)

    # noinspection PyPropertyDefinition
    @classmethod
    def is_known_client(cls, ip_addr: str) -> bool:
        # noinspection PyProtectedMember
        if cls._instance and ip_addr in cls._instance._clients:
            return True
        return False

    @classmethod
    def get_comm_buffer(cls) -> CommBuffer:
        # noinspection PyProtectedMember
        return cls._instance._tmcc_buffer if cls._instance is not None else None

    @classmethod
    def stop(cls) -> None:
        if cls._instance is not None:
            cls._instance.shutdown()

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def register_request(cls) -> bytes:
        return REGISTER_REQUEST

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def disconnect_request(cls) -> bytes:
        return DISCONNECT_REQUEST

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def sync_state_request(cls) -> bytes:
        return SYNC_STATE_REQUEST

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def clients(cls) -> List[str]:
        # noinspection PyProtectedMember
        return list(cls._instance._clients)

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def port(cls) -> int:
        if cls._instance is not None:
            # noinspection PyProtectedMember
            return cls._instance._port
        raise AttributeError("EnqueueProxyRequests is not built yet.")

    def __init__(self, tmcc_buffer: CommBuffer, port: int = DEFAULT_SERVER_PORT) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Enqueue Receiver")
        self._tmcc_buffer: CommBuffer = tmcc_buffer
        self._port = port
        self._clients: set[str] = set()
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
        """
        Simplified TCP/IP Server listens for command requests from client and executes them
        on the PyTrain server.
        """
        # noinspection PyTypeChecker
        with socketserver.TCPServer(("", self._port), EnqueueHandler) as server:
            server.serve_forever()

    def shutdown(self) -> None:
        # noinspection PyTypeChecker
        with socketserver.TCPServer(("", self._port), EnqueueHandler) as server:
            server.shutdown()


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
        if byte_stream == EnqueueProxyRequests.register_request:
            if EnqueueProxyRequests.is_known_client(self.client_address[0]) is False:
                log.info(f"Client at {self.client_address[0]} connecting...")
        elif byte_stream == EnqueueProxyRequests.sync_state_request:
            from ..comm.command_listener import CommandDispatcher

            CommandDispatcher.build().send_current_state(self.client_address[0])
        elif byte_stream == EnqueueProxyRequests.disconnect_request:
            EnqueueProxyRequests.client_disconnect(self.client_address[0])
        else:
            EnqueueProxyRequests.enqueue_tmcc_packet(byte_stream)
        EnqueueProxyRequests.note_client_addr(self.client_address[0])
