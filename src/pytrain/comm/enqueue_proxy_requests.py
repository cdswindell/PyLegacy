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

REGISTER_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.REGISTER).as_bytes
DISCONNECT_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.DISCONNECT).as_bytes
SYNC_STATE_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.SYNC_REQUEST).as_bytes
SYNC_BEGIN_RESPONSE: bytes = CommandReq(TMCC1SyncCommandEnum.SYNC_BEGIN).as_bytes
SYNC_COMPLETE_RESPONSE: bytes = CommandReq(TMCC1SyncCommandEnum.SYNC_COMPLETE).as_bytes
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
    def sync_begin_response(cls, port: int = DEFAULT_SERVER_PORT) -> bytes:
        if port and port != DEFAULT_SERVER_PORT:
            return SYNC_BEGIN_RESPONSE + int(port & 0xFFFF).to_bytes(2, byteorder="big")
        return SYNC_BEGIN_RESPONSE

    @classmethod
    def sync_complete_response(cls, port: int = DEFAULT_SERVER_PORT) -> bytes:
        if port and port != DEFAULT_SERVER_PORT:
            return SYNC_COMPLETE_RESPONSE + int(port & 0xFFFF).to_bytes(2, byteorder="big")
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

    @classmethod
    def server_ip(cls) -> int:
        if cls._instance is not None:
            # noinspection PyProtectedMember
            return cls._instance._server_ip
        raise AttributeError("EnqueueProxyRequests is not built yet.")

    def __init__(self, tmcc_buffer: CommBuffer, server_port: int = DEFAULT_SERVER_PORT) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Enqueue Receiver")
        self._tmcc_buffer: CommBuffer = tmcc_buffer
        self._server_port = server_port
        self._server_ip = None
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
    def __init__(self, request: socket.socket, client_address: Tuple[str, int], server: ProxyServer) -> None:
        super().__init__(request, client_address, server)

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
        # we use TMCC1 syntax to pass special commands to control operating nodes,
        # to reduce overhead, only do the special processing if necessary
        try:
            if byte_stream[0] == 0xFE and byte_stream[1] == 0xF0:
                from .command_listener import CommandDispatcher

                # Appended to the admin/sync byte sequence is the port that the server
                # must use to send state updates back to the client. Decode it here
                (client_ip, client_port) = self.extract_addendum(byte_stream)
                byte_stream = byte_stream[0:3]
                cmd = CommandReq.from_bytes(byte_stream)

                if byte_stream == DISCONNECT_REQUEST:
                    EnqueueProxyRequests.client_disconnect(self.client_address[0], client_port)
                    log.info(f"Client at {self.client_address[0]}:{client_port} disconnecting...")
                elif byte_stream == REGISTER_REQUEST:
                    if EnqueueProxyRequests.is_known_client(self.client_address[0], client_port) is False:
                        log.info(f"Client at {self.client_address[0]}:{client_port} connecting...")
                    EnqueueProxyRequests.client_connect(self.client_address[0], client_port)
                elif byte_stream == SYNC_STATE_REQUEST:
                    log.info(f"Client at {self.client_address[0]}:{client_port} syncing...")
                    CommandDispatcher.get().send_current_state(self.client_address[0], client_port)
                elif byte_stream in {
                    UPDATE_REQUEST,
                    UPGRADE_REQUEST,
                    REBOOT_REQUEST,
                    RESTART_REQUEST,
                    SHUTDOWN_REQUEST,
                }:
                    # admin request, signal all clients
                    if client_ip:
                        CommandDispatcher.get().signal_clients_on(cmd, client_ip)
                    else:
                        CommandDispatcher.get().signal_client(cmd)
                        CommandDispatcher.get().publish(CommandScope.SYNC, cmd)
                else:
                    log.error(f"*** Unhandled {cmd} received from {self.client_address[0]}:{client_port} ***")
                # do not send the special PyTrain commands to the Lionel Base 3 or Ser2
                return

            EnqueueProxyRequests.enqueue_tmcc_packet(byte_stream)
        finally:
            self.request.shutdown(socket.SHUT_RDWR)
            self.request.close()

    @staticmethod
    def extract_addendum(byte_stream: bytes) -> Tuple[str | None, int | None]:
        if len(byte_stream) > 5:
            addenda = byte_stream[3:].decode("utf-8", errors="ignore")
            parts = addenda.split(":")
            ip_addr = parts[0] if parts[0] else None
            port = int(parts[1]) if len(parts) > 1 else None
            return ip_addr, port
        elif len(byte_stream) > 3:
            return None, int.from_bytes(byte_stream[3:], "big")
        else:
            return None, DEFAULT_SERVER_PORT
