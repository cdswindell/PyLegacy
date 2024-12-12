from __future__ import annotations

import logging
import socketserver
import threading
from threading import Thread
from typing import Dict

from ..comm.comm_buffer import CommBuffer
from ..protocol.constants import DEFAULT_SERVER_PORT

log = logging.getLogger(__name__)

REGISTER_REQUEST: bytes = int(0xFF).to_bytes(1, byteorder="big") * 6
DISCONNECT_REQUEST: bytes = int(0xFFFC).to_bytes(2, byteorder="big") * 3
SYNC_STATE_REQUEST: bytes = int(0xFFF0).to_bytes(2, byteorder="big") * 3
SYNC_BEGIN_RESPONSE: bytes = int(0xFFF1).to_bytes(2, byteorder="big") * 3
SYNC_COMPLETE_RESPONSE: bytes = int(0xFFF2).to_bytes(2, byteorder="big") * 3


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
    def record_client(cls, client: str, port: int = DEFAULT_SERVER_PORT) -> None:
        """
        Take note of client IPs, so we can update them of component state changes
        """
        if cls._instance is not None:
            # noinspection PyProtectedMember
            cls._instance._clients[client] = port

    @classmethod
    def client_disconnect(cls, client: str) -> None:
        """
        Remove client so we don't send more state updates
        """
        if cls._instance is not None:
            # noinspection PyProtectedMember
            cls._instance._clients.pop(client, None)

    # noinspection PyPropertyDefinition
    @classmethod
    def is_known_client(cls, ip_addr: str) -> bool:
        # noinspection PyProtectedMember
        if cls._instance and (ip_addr in cls._instance._clients):
            return True
        return False

    @classmethod
    def clients(cls) -> Dict[str, int]:
        # noinspection PyProtectedMember
        return cls._instance._clients.copy()

    @classmethod
    def get_comm_buffer(cls) -> CommBuffer:
        # noinspection PyProtectedMember
        return cls._instance._tmcc_buffer if cls._instance is not None else None

    @classmethod
    def stop(cls) -> None:
        if cls._instance is not None:
            cls._instance.shutdown()

    @classmethod
    def register_request(cls, port: int = DEFAULT_SERVER_PORT) -> bytes:
        if port and port != DEFAULT_SERVER_PORT:
            return REGISTER_REQUEST + int(port & 0xFFFF).to_bytes(2, byteorder="big")
        return REGISTER_REQUEST

    @classmethod
    def disconnect_request(cls) -> bytes:
        return DISCONNECT_REQUEST

    @classmethod
    def sync_state_request(cls) -> bytes:
        return SYNC_STATE_REQUEST

    @classmethod
    def sync_begin_response(cls) -> bytes:
        return SYNC_BEGIN_RESPONSE

    @classmethod
    def sync_complete_response(cls) -> bytes:
        return SYNC_COMPLETE_RESPONSE

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def is_built(cls) -> bool:
        return cls._instance is not None

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
        self._clients: Dict[str, int] = dict()
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
        from ..comm.command_listener import CommandDispatcher

        byte_stream = bytes()
        while True:
            data = self.request.recv(128)
            if data:
                byte_stream += data
                self.request.sendall(str.encode("ack"))
            else:
                break

        if byte_stream == EnqueueProxyRequests.disconnect_request():
            EnqueueProxyRequests.client_disconnect(self.client_address[0])
            log.info(f"Client at {self.client_address[0]} disconnecting...")
            return
        elif byte_stream.startswith(EnqueueProxyRequests.register_request()):
            if EnqueueProxyRequests.is_known_client(self.client_address[0]) is False:
                log.info(f"Client at {self.client_address[0]} connecting...")
            client_port = DEFAULT_SERVER_PORT
            if len(byte_stream) > len(REGISTER_REQUEST):
                client_port = int.from_bytes(byte_stream[len(REGISTER_REQUEST) :], "big")
            EnqueueProxyRequests.record_client(self.client_address[0], client_port)
        elif byte_stream == EnqueueProxyRequests.sync_state_request():
            log.info(f"Client at {self.client_address[0]} syncing...")
            port = EnqueueProxyRequests.clients().get(self.client_address[0], DEFAULT_SERVER_PORT)
            CommandDispatcher.build().send_current_state(self.client_address[0], port)
        else:
            EnqueueProxyRequests.enqueue_tmcc_packet(byte_stream)
