#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import logging
import socketserver
import threading
from threading import Event
from typing import cast

from ..comm.comm_buffer import CommBuffer, CommBufferProxy
from ..comm.command_listener import CommandListener, Subscriber, Topic
from ..pdi.constants import PDI_SOP, PDI_EOP, PDI_STF
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
        self._tmcc_buffer = cast(CommBufferProxy, CommBuffer.build())
        self._port = self._tmcc_buffer.server_port()
        self._is_running = True
        self._ev = Event()
        self.start()

        # wait for socket server to be up and running
        self._ev.wait()
        self._tmcc_buffer.register(self.port)  # register this client with server to receive updates

        # See if this client needs an upgrade. If it does, the actual upgrade
        # will be done by the PyTrain main program
        if self.update_client_if_needed(False) is True:
            return

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

    def update_client_if_needed(self, do_upgrade=True) -> bool:
        from .. import get_version, get_version_tuple

        # wait for client registration to happen and for the server to tell the client its version
        # if the version of the server is newer, we want to update the client
        self._tmcc_buffer.server_version_available().wait()
        server_version = self._tmcc_buffer.server_version
        client_version = get_version_tuple()  # only interested in major and minor version
        if server_version is None or server_version > client_version:
            if do_upgrade is True:
                cv = f"{get_version()}"
                sv = f" --> v{server_version[0]}.{server_version[1]}.{server_version[2]}" if server_version else ""
                log.info(f"Client needs update: {cv}{sv}")
            return True
        return False

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
        csl = ClientStateListener.build()
        byte_stream = bytes()
        while True:
            data = self.request.recv(512)
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
                    while (eop_index - 1) >= 0 and byte_stream[eop_index - 1] == PDI_STF:
                        if PDI_EOP in byte_stream[eop_index + 1 :]:
                            eop_index = byte_stream.index(PDI_EOP, eop_index + 1)
                        else:
                            break
                    command_bytes = byte_stream[0 : eop_index + 1]
                    byte_stream = byte_stream[eop_index + 1 :]
            else:
                byte_stream = bytes()
            csl.offer(command_bytes)
