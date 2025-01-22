from __future__ import annotations

import logging
import socketserver
import threading
from threading import Event

from ..comm.comm_buffer import CommBuffer
from ..comm.command_listener import CommandListener, Subscriber, Topic
from ..pdi.constants import PDI_SOP, PDI_EOP
from ..protocol.command_def import CommandDefEnum

log = logging.getLogger(__name__)


class ClientStateListener(threading.Thread):
    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(cls) -> ClientStateListener:
        return ClientStateListener()

    @classmethod
    def listen_for(
        cls, listener: Subscriber, channel: Topic, address: int = None, command: CommandDefEnum = None, data: int = None
    ):
        cls.build().subscribe(listener, channel, address, command, data)

    def __init__(self) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        from .. import PROGRAM_NAME

        super().__init__(daemon=True, name=f"{PROGRAM_NAME} ComponentStateListener")
        self._tmcc_listener = CommandListener.build(ser2_receiver=False, base3_receiver=False)
        from ..pdi.pdi_listener import PdiListener

        self._pdi_listener = PdiListener.build(build_base3_reader=False)
        self._tmcc_buffer = CommBuffer.build()
        self._port = self._tmcc_buffer.server_port()
        self._is_running = True
        self._ev = Event()
        self.start()

        # wait for socket server to be up and running
        self._ev.wait()
        self._tmcc_buffer.register(self.port)  # register this client with server to receive updates
        self._tmcc_buffer.sync_state()  # request initial state from server
        self._tmcc_buffer.start_heart_beat()

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

    @property
    def port(self) -> int:
        return self._port

    def run(self) -> None:
        while self._is_running:
            try:
                # noinspection PyTypeChecker
                with socketserver.TCPServer(("", self._port), ClientStateHandler) as server:
                    # inform main thread server is running on a valid port
                    self._ev.set()
                    server.serve_forever()
            except OSError as oe:
                if oe.errno in {48, 98}:
                    self._port += 1
                else:
                    raise oe

    def shutdown(self) -> None:
        self._is_running = False
        # noinspection PyTypeChecker
        with socketserver.TCPServer(("", self._port), ClientStateHandler) as server:
            server.shutdown()

    def offer(self, data: bytes) -> None:
        # look at first byte to determine handler
        from ..pdi.constants import PDI_SOP

        if log.isEnabledFor(logging.DEBUG):
            log.debug(f"ClientStateListener Offered: {data.hex(' ')}")
        if data and data[0] == PDI_SOP:
            self._pdi_listener.offer(data)
        else:
            self._tmcc_listener.offer(data)

    def subscribe(
        self,
        listener: Subscriber,
        channel: Topic,
        address: int = None,
        command: CommandDefEnum = None,
        data: int = None,
    ) -> None:
        self._tmcc_listener.subscribe(listener, channel, address, command, data)
        self._pdi_listener.subscribe(listener, channel, address)

    def unsubscribe(
        self,
        listener: Subscriber,
        channel: Topic,
        address: int = None,
        command: CommandDefEnum = None,
        data: int = None,
    ):
        self._tmcc_listener.unsubscribe(listener, channel, address, command, data)
        self._pdi_listener.unsubscribe(listener, channel, address)


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
        # the byte stream could be a combo of PDI AND TMCC commands; we don't
        # want to duplicate all the byte stuffing code, but if the first byte
        # is PDI_SOP, look for a PDI_EOP and just send that portion
        while byte_stream:
            command_bytes = byte_stream
            if byte_stream[0] == PDI_SOP:
                if PDI_EOP in byte_stream:
                    eop_index = byte_stream.index(PDI_EOP)
                    command_bytes = byte_stream[0 : eop_index + 1]
                    byte_stream = byte_stream[eop_index + 1 :]
            else:
                byte_stream = bytes()
            ClientStateListener.build().offer(command_bytes)
