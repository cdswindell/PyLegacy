from __future__ import annotations

import socketserver
import threading

from ..comm.comm_buffer import CommBuffer
from ..comm.command_listener import CommandListener, Subscriber, Topic
from ..protocol.command_def import CommandDefEnum


class ClientStateListener(threading.Thread):
    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(cls) -> ClientStateListener:
        return ClientStateListener()

    @classmethod
    def listen_for(cls,
                   listener: Subscriber,
                   channel: Topic,
                   address: int = None,
                   command: CommandDefEnum = None,
                   data: int = None):
        cls.build().subscribe(listener, channel, address, command, data)

    def __init__(self) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy ComponentStateListener")
        self._command_listener = CommandListener.build(build_serial_reader=False)
        self._buffer = CommBuffer.build()
        self._port = self._buffer.server_port
        self.start()
        self._buffer.register()  # register this client with server to receive updates
        self._buffer.sync_state()  # request initial state from server

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in the system
        """
        with cls._lock:
            if ClientStateListener._instance is None:
                ClientStateListener._instance = super(ClientStateListener, cls).__new__(cls)
                ClientStateListener._instance._initialized = False
            return ClientStateListener._instance

    def run(self) -> None:
        # noinspection PyTypeChecker
        with socketserver.TCPServer(('', self._port), ClientStateHandler) as server:
            server.serve_forever()

    def offer(self, data: bytes) -> None:
        self._command_listener.offer(data)

    def subscribe(self,
                  listener: Subscriber,
                  channel: Topic,
                  address: int = None,
                  command: CommandDefEnum = None,
                  data: int = None) -> None:
        self._command_listener.subscribe(listener, channel, address, command, data)

    def unsubscribe(self,
                    listener: Subscriber,
                    channel: Topic,
                    address: int = None,
                    command: CommandDefEnum = None,
                    data: int = None):
        self._command_listener.unsubscribe(listener, channel, address, command, data)


class ClientStateHandler(socketserver.BaseRequestHandler):
    def handle(self):
        byte_stream = bytes()
        while True:
            data = self.request.recv(128)
            if data:
                byte_stream += data
                self.request.sendall(str.encode("ack"))
            else:
                break
        ClientStateListener.build().offer(byte_stream)
