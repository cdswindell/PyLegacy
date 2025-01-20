from __future__ import annotations

import logging
import socket
import socketserver
import threading
from threading import Thread
from typing import cast, Tuple, Set

from ..comm.comm_buffer import CommBuffer
from ..protocol.command_req import CommandReq
from ..protocol.constants import DEFAULT_SERVER_PORT, CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum

log = logging.getLogger(__name__)

REGISTER_REQUEST: bytes = int(0xFF).to_bytes(1, byteorder="big") * 6
DISCONNECT_REQUEST: bytes = int(0xFFFC).to_bytes(2, byteorder="big") * 3
SYNC_STATE_REQUEST: bytes = int(0xFFF0).to_bytes(2, byteorder="big") * 3
SYNC_BEGIN_RESPONSE: bytes = int(0xFFF1).to_bytes(2, byteorder="big") * 3
SYNC_COMPLETE_RESPONSE: bytes = int(0xFFF2).to_bytes(2, byteorder="big") * 3
UPDATE_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.UPDATE).as_bytes
UPGRADE_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.UPGRADE).as_bytes
REBOOT_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.REBOOT).as_bytes
RESTART_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.RESTART).as_bytes
SHUTDOWN_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.SHUTDOWN).as_bytes


class ProxyServer(socketserver.ThreadingTCPServer):
    __slots__ = "base3_addr", "ack"
    #
    # def __init__(self, server_address, req_handler_class):
    #     super().__init__(server_address, req_handler_class)
    #     self.allow_reuse_port = True
    #     self.allow_reuse_address = True
    #     self.server_bind()
    #     self.server_activate()

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.socket.bind(self.server_address)


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
    def client_connect(cls, client: str, port: int = DEFAULT_SERVER_PORT) -> None:
        """
        Take note of client IPs, so we can update them of component state changes
        """
        if cls._instance is not None:
            # noinspection PyProtectedMember
            cls._instance._clients.add((client, port))

    @classmethod
    def client_disconnect(cls, client: str, port: int = DEFAULT_SERVER_PORT) -> None:
        """
        Remove client so we don't send more state updates
        """
        if cls._instance is not None:
            # noinspection PyProtectedMember
            cls._instance._clients.discard((client, port))

    @classmethod
    def is_known_client(cls, ip_addr: str, port: int = DEFAULT_SERVER_PORT) -> bool:
        # noinspection PyProtectedMember
        if cls._instance and ((ip_addr, port) in cls._instance._clients):
            return True
        return False

    @classmethod
    def clients(cls) -> Set[Tuple[str, int]]:
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
    def disconnect_request(cls, port: int = DEFAULT_SERVER_PORT) -> bytes:
        if port and port != DEFAULT_SERVER_PORT:
            return DISCONNECT_REQUEST + int(port & 0xFFFF).to_bytes(2, byteorder="big")
        return DISCONNECT_REQUEST

    @classmethod
    def sync_state_request(cls, port: int = DEFAULT_SERVER_PORT) -> bytes:
        if port and port != DEFAULT_SERVER_PORT:
            return SYNC_STATE_REQUEST + int(port & 0xFFFF).to_bytes(2, byteorder="big")
        return SYNC_STATE_REQUEST

    @classmethod
    def sync_begin_response(cls) -> bytes:
        return SYNC_BEGIN_RESPONSE

    @classmethod
    def sync_complete_response(cls) -> bytes:
        return SYNC_COMPLETE_RESPONSE

    @classmethod
    def is_built(cls) -> bool:
        return cls._instance is not None

    @classmethod
    def server_port(cls) -> int:
        if cls._instance is not None:
            # noinspection PyProtectedMember
            return cls._instance._server_port
        raise AttributeError("EnqueueProxyRequests is not built yet.")

    def __init__(self, tmcc_buffer: CommBuffer, server_port: int = DEFAULT_SERVER_PORT) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Enqueue Receiver")
        self._tmcc_buffer: CommBuffer = tmcc_buffer
        self._server_port = server_port
        self._clients: Set[Tuple[str, int]] = set()
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
        with ProxyServer(("", self._server_port), EnqueueHandler) as server:
            if self._tmcc_buffer.base3_address:
                server.base3_addr = self._tmcc_buffer.base3_address
                server.ack = str.encode(server.base3_addr)
            else:
                server.ack = str.encode("ack")
            server.serve_forever()


class EnqueueHandler(socketserver.BaseRequestHandler):
    def handle(self):
        byte_stream = bytes()
        ack = cast(ProxyServer, self.server).ack
        while True:
            data = self.request.recv(128)
            if data:
                byte_stream += data
                self.request.sendall(ack)
            else:
                break
        # we use TMCC1 syntax to pass special commands to control operating nodes
        # if we know the command is not in TMCC1 format, don't take the overhead
        # of the additional checks
        if byte_stream[0] in {0xFF, 0xFE}:
            from .command_listener import CommandDispatcher

            print(f"Client: {self.client_address}")
            if byte_stream.startswith(EnqueueProxyRequests.disconnect_request()):
                client_port = self.extract_port(byte_stream, DISCONNECT_REQUEST)
                EnqueueProxyRequests.client_disconnect(self.client_address[0], client_port)
                log.info(f"Client at {self.client_address[0]}:{client_port} disconnecting...")
                return
            elif byte_stream.startswith(EnqueueProxyRequests.register_request()):
                # Appended to the register request byte sequence s the port that the server
                # must use to send state updates back to the client. Decode it here
                client_port = self.extract_port(byte_stream, REGISTER_REQUEST)
                if EnqueueProxyRequests.is_known_client(self.client_address[0], client_port) is False:
                    log.info(f"Client at {self.client_address[0]}:{client_port} connecting...")
                EnqueueProxyRequests.client_connect(self.client_address[0], client_port)
                return
            elif byte_stream.startswith(EnqueueProxyRequests.sync_state_request()):
                client_port = self.extract_port(byte_stream, SYNC_STATE_REQUEST)
                log.info(f"Client at {self.client_address[0]}:{client_port} syncing...")
                CommandDispatcher.get().send_current_state(self.client_address[0], client_port)
                return
            elif byte_stream in {
                UPDATE_REQUEST,
                UPGRADE_REQUEST,
                REBOOT_REQUEST,
                RESTART_REQUEST,
                SHUTDOWN_REQUEST,
            } and EnqueueProxyRequests.is_known_client(self.client_address[0]):
                cmd = CommandReq.from_bytes(byte_stream)
                CommandDispatcher.get().signal_client(cmd)
                CommandDispatcher.get().publish(CommandScope.SYNC, cmd)
                return
        EnqueueProxyRequests.enqueue_tmcc_packet(byte_stream)

    def finish(self):
        self.request.shutdown(socket.SHUT_RDWR)
        self.request.close()

    @staticmethod
    def extract_port(byte_stream: bytes, request: bytes) -> int:
        if len(byte_stream) > len(request):
            return int.from_bytes(byte_stream[len(request) :], "big")
        else:
            return DEFAULT_SERVER_PORT
