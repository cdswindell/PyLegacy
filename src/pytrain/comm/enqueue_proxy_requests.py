from __future__ import annotations

import logging
import socketserver
import threading
from threading import Thread
from typing import Dict, cast

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

            if byte_stream == EnqueueProxyRequests.disconnect_request():
                EnqueueProxyRequests.client_disconnect(self.client_address[0])
                log.info(f"Client at {self.client_address[0]} disconnecting...")
                return
            elif byte_stream.startswith(EnqueueProxyRequests.register_request()):
                if EnqueueProxyRequests.is_known_client(self.client_address[0]) is False:
                    log.info(f"Client at {self.client_address[0]} connecting...")
                # Appended to the register request byte sequence s the port that the server
                # must use to send state updates back to the client. Decode it here
                client_port = DEFAULT_SERVER_PORT
                if len(byte_stream) > len(REGISTER_REQUEST):
                    client_port = int.from_bytes(byte_stream[len(REGISTER_REQUEST) :], "big")
                EnqueueProxyRequests.record_client(self.client_address[0], client_port)
                return
            elif byte_stream == EnqueueProxyRequests.sync_state_request():
                log.info(f"Client at {self.client_address[0]} syncing...")
                port = EnqueueProxyRequests.clients().get(self.client_address[0], DEFAULT_SERVER_PORT)
                CommandDispatcher.get().send_current_state(self.client_address[0], port)
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
