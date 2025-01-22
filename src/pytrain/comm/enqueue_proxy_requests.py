from __future__ import annotations

import logging
import socket
import socketserver
import threading
import uuid
from threading import Thread
from time import time
from typing import cast, Tuple, Set, Dict

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
KEEP_ALIVE_REQUEST: bytes = CommandReq(TMCC1SyncCommandEnum.KEEP_ALIVE).as_bytes


class ProxyServer(socketserver.ThreadingTCPServer):
    __slots__ = "base3_addr", "ack", "dispatcher", "enqueue_proxy"


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
    def clients(cls) -> Set[Tuple[str, int]]:
        if cls._instance is not None:
            return cls._instance.client_sessions
        raise AttributeError("EnqueueProxyRequests is not built yet.")

    @classmethod
    def stop(cls) -> None:
        if cls._instance is not None:
            cls._instance.shutdown()

    @classmethod
    def register_request(cls, port: int, client_id: uuid.UUID) -> bytes:
        return cls._build_request(REGISTER_REQUEST, port, client_id)

    @classmethod
    def disconnect_request(cls, port, client_id: uuid.UUID) -> bytes:
        return cls._build_request(DISCONNECT_REQUEST, port, client_id)

    @classmethod
    def sync_state_request(cls, port: int = DEFAULT_SERVER_PORT, client_id: uuid.UUID = None) -> bytes:
        return cls._build_request(SYNC_STATE_REQUEST, port, client_id)

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

    @classmethod
    def server_ip(cls) -> int:
        if cls._instance is not None:
            # noinspection PyProtectedMember
            return cls._instance._server_ip
        raise AttributeError("EnqueueProxyRequests is not built yet.")

    @classmethod
    def _build_request(cls, request: bytes, port: int, client_id: uuid.UUID = None) -> bytes:
        port = port if port else DEFAULT_SERVER_PORT
        client_id_bytes = client_id.bytes if client_id else bytes()
        return request + int(port & 0xFFFF).to_bytes(2, byteorder="big") + client_id_bytes

    def __init__(self, tmcc_buffer: CommBuffer, server_port: int = DEFAULT_SERVER_PORT) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Enqueue Receiver")
        self._tmcc_buffer: CommBuffer = tmcc_buffer
        self._server_port = server_port
        self._server_ip = None
        self._lock = threading.RLock()
        self._clients: Dict[Tuple[str, int, uuid.UUID | None], float] = dict()
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

    def client_connect(self, client_ip: str, port: int = DEFAULT_SERVER_PORT, client_id: uuid.UUID = None) -> None:
        # check if (client_ip, port) is unique, it should be unless
        # previous client on this port unexpectedly disconnected
        with self._lock:
            disconnected = set()
            for k_ip, k_port, k_uuid in self._clients.keys():
                if k_ip == client_ip and k_port == port:
                    if client_id != k_uuid:
                        disconnected.add((k_ip, k_port, k_uuid))
            # delete disconnected key
            for k in disconnected:
                log.info(f"Purging disconnected client: {k}...")
                self._clients.pop(k, None)

            # record new client
            self._clients[(client_ip, port, client_id)] = time()

    def client_disconnect(self, client_ip: str, port: int = DEFAULT_SERVER_PORT, client_id: uuid.UUID = None) -> None:
        with self._lock:
            self._clients.pop((client_ip, port, client_id), None)

    def is_client(self, client_ip: str, port: int = DEFAULT_SERVER_PORT, client_id: uuid.UUID = None) -> bool:
        with self._lock:
            return (client_ip, port, client_id) in self._clients

    def client_alive(self, client_ip: str, port: int, client_id: uuid.UUID) -> None:
        with self._lock:
            if (client_ip, port, client_id) in self._clients:
                self._clients[(client_ip, port, client_id)] = time()
            else:
                log.error(f"Client {client_ip}:{port}:{client_id} is not registered")

    def enqueue_request(self, data: bytes) -> None:
        self._tmcc_buffer.enqueue_command(data)

    @property
    def client_sessions(self) -> Set[Tuple[str, int]]:
        with self._lock:
            return {(k[0], k[1]) for k, v in self._clients.items()}

    def run(self) -> None:
        from src.pytrain.comm.command_listener import CommandDispatcher

        """
        Simplified TCP/IP Server listens for command requests from client and executes them
        on the PyTrain server.
        """
        # noinspection PyTypeChecker
        with ProxyServer(("", self._server_port), EnqueueHandler) as server:
            server.session_id = self._tmcc_buffer.session_id
            if self._tmcc_buffer.base3_address:
                server.base3_addr = self._tmcc_buffer.base3_address
                server.ack = str.encode(server.base3_addr)
            else:
                server.ack = str.encode("ack")
            server.dispatcher = CommandDispatcher.get()
            server.enqueue_proxy = self
            server.serve_forever()


class EnqueueHandler(socketserver.BaseRequestHandler):
    def __init__(self, request: socket.socket, client_address: Tuple[str, int], server: ProxyServer) -> None:
        super().__init__(request, client_address, server)

    def handle(self):
        from src.pytrain.comm.command_listener import CommandDispatcher

        byte_stream = bytes()
        ack = cast(ProxyServer, self.server).ack
        dispatcher: CommandDispatcher = cast(ProxyServer, self.server).dispatcher
        enqueue_proxy: EnqueueProxyRequests = cast(ProxyServer, self.server).enqueue_proxy
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
                (client_ip, client_port, client_id) = self.extract_addendum(byte_stream)
                client_ip = client_ip if client_ip else self.client_address[0]
                byte_stream = byte_stream[0:3]
                cmd = CommandReq.from_bytes(byte_stream)

                if byte_stream == DISCONNECT_REQUEST:
                    enqueue_proxy.client_disconnect(client_ip, client_port, client_id)
                    log.info(f"Client at {client_ip}:{client_port} disconnecting...")
                elif byte_stream == REGISTER_REQUEST:
                    if enqueue_proxy.is_client(client_ip, client_port, client_id) is False:
                        log.info(f"Client at {client_ip}:{client_port} connecting...")
                    enqueue_proxy.client_connect(client_ip, client_port, client_id)
                elif byte_stream == SYNC_STATE_REQUEST:
                    log.info(f"Client at {client_ip}:{client_port} syncing...")
                    dispatcher.send_current_state(client_ip, client_port)
                elif byte_stream == KEEP_ALIVE_REQUEST:
                    enqueue_proxy.client_alive(client_ip, client_port, client_id)
                elif byte_stream in {
                    UPDATE_REQUEST,
                    UPGRADE_REQUEST,
                    REBOOT_REQUEST,
                    RESTART_REQUEST,
                    SHUTDOWN_REQUEST,
                }:
                    # admin request, signal all clients
                    if client_ip:
                        dispatcher.signal_clients_on(cmd, client_ip)
                    else:
                        dispatcher.signal_clients(cmd)
                        dispatcher.publish(CommandScope.SYNC, cmd)
                else:
                    log.error(f"Unhandled {cmd} received from {client_ip}:{client_port}")
                # do not send the special PyTrain commands to the Lionel Base 3 or Ser2
                return
            # with the handling of the admin cmds out of the way, queue the bytes
            # received from the client for processing by the Lionel Base 3
            enqueue_proxy.enqueue_request(byte_stream)
        finally:
            self.request.shutdown(socket.SHUT_RDWR)
            self.request.close()

    @staticmethod
    def extract_addendum(byte_stream: bytes) -> Tuple[str | None, int | None, uuid.UUID | None]:
        client_uuid: uuid.UUID | None = None
        client_ip: str | None = None
        client_port: int = DEFAULT_SERVER_PORT
        try:
            if len(byte_stream) > 18:  # port and UUID as bytes
                client_port = int.from_bytes(byte_stream[3:5], "big")
                client_uuid = uuid.UUID(bytes=byte_stream[5:])
            elif len(byte_stream) > 5:
                addenda = byte_stream[3:].decode("utf-8", errors="ignore")
                parts = addenda.split(":")
                client_ip = parts[0] if parts[0] else None
                client_port = int(parts[1]) if len(parts) > 1 else None
            elif len(byte_stream) > 3:
                client_port = int.from_bytes(byte_stream[3:], "big")
        except Exception as e:
            log.exception(e)
        return client_ip, client_port, client_uuid
