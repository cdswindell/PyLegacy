from __future__ import annotations

import select
import socket
import threading
import time

# from signal import signal, SIGPIPE, SIG_DFL
from threading import Condition, Thread

from .base_req import BaseReq
from .constants import KEEP_ALIVE_CMD, PDI_SOP, PdiCommand
from .pdi_listener import PdiListener
from .pdi_req import PdiReq, TmccReq
from ..protocol.command_req import CommandReq

from ..protocol.constants import DEFAULT_BASE3_PORT, DEFAULT_QUEUE_SIZE, DEFAULT_THROTTLE_DELAY
from ..utils.pollable_queue import PollableQueue


class Base3Buffer(Thread):
    # noinspection GrazieInspection
    """
    Send and receive PDI command packets to/from a Lionel Base 3 or LCS WiFi module.
    """

    _instance: None = None
    _lock = threading.RLock()

    @classmethod
    def stop(cls) -> None:
        if cls._instance is not None:
            cls._instance.shutdown()
            cls._instance = None

    # noinspection PyPropertyDefinition
    @classmethod
    @property
    def get(cls) -> Base3Buffer:
        if cls._instance is None:
            raise AttributeError("Base3Buffer has not been initialized")
        return cls._instance

    @classmethod
    def enqueue_command(cls, data: bytes) -> None:
        if cls._instance is not None and data:
            cls._instance.send(data)

    def __init__(
        self,
        base3_addr: str,
        base3_port: int = DEFAULT_BASE3_PORT,
        buffer_size: int = DEFAULT_QUEUE_SIZE,
        listener: PdiListener = None,
    ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name="PyLegacy Base3 Interface")
        # ip address and port to connect
        self._base3_addr = base3_addr
        self._base3_port = base3_port
        # data read from the Base 3 is sent to a PdiListener to decode and act on
        self._listener = listener
        self._is_running = True
        self._last_output_at = 0  # used to throttle writes to LCS Base3
        # data to send to the Base 3 is written into a queue, which is drained by the thread
        # created when this instance is started
        self._send_queue: PollableQueue[bytes] = PollableQueue(buffer_size)
        self._send_cv = Condition()
        # we must send a keepalive packet to the base 3 every few seconds to keep it
        # from closing the connection
        self._keep_alive = KeepAlive(self)
        self.start()

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if Base3Buffer._instance is None:
                Base3Buffer._instance = super(Base3Buffer, cls).__new__(cls)
                Base3Buffer._instance._initialized = False
            return Base3Buffer._instance

    def send(self, data: bytes) -> None:
        if data:
            with self._send_cv:
                self._send_queue.put(data)
                self._send_cv.notify_all()

    @staticmethod
    def _current_milli_time() -> int:
        """
        Return the current time, in milliseconds past the "epoch"
        """
        return round(time.time() * 1000)

    def run(self) -> None:
        # signal(SIGPIPE, SIG_DFL)
        while self._is_running:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((str(self._base3_addr), self._base3_port))
                # we want to wait on either data being available to send to the Base3 of
                # data available from the Base 3 to process
                socket_list = [s, self._send_queue]
                while self._is_running:
                    try:
                        readable, _, _ = select.select(socket_list, [], [])
                        for sock in readable:
                            if sock == self._send_queue:
                                received = None
                                sending = sock.get()
                                millis_since_last_output = self._current_milli_time() - self._last_output_at
                                if millis_since_last_output < DEFAULT_THROTTLE_DELAY:
                                    time.sleep((DEFAULT_THROTTLE_DELAY - millis_since_last_output) / 1000.0)
                                s.sendall(sending.hex().upper().encode())
                                self._last_output_at = self._current_milli_time()
                                # update base3 of new state; required if command is a tmcc_tx
                                self.sync_state(sending)
                            else:
                                sending = None
                                # we will always call s.recv, as in either case, there will
                                # be a response, either because we received an 'ack' from
                                # our send or because the select was triggered on the socket
                                # being able to be read.
                                received = bytes.fromhex(s.recv(512).decode())
                                # but there is more trickiness; The Base3 sends ascii characters
                                # so when we receive: 'D12729DF', this actually is sent as eight
                                # characters; D, 1, 2, 7, 2, 9, D, F, so we must decode the 8
                                # received bytes into 8 ASCII characters, then interpret that
                                # ASCII string as Hex representation to arrive at 0xd12729df...
                            if self._listener is not None and received:
                                self._listener.offer(received)
                    except BrokenPipeError as bpe:
                        # keep trying; unix can sometimes just hang up
                        if sending is not None:
                            print(f"Exception sending: 0x{sending.hex(':').upper()}  Exception: {bpe}")
                            self.send(sending)
                        elif received is not None:
                            print(f"Exception receiving: 0x{received.hex(':').upper()}  Exception: {bpe}")
                        else:
                            print(f"Exception: {bpe}")
                        break  # continues to outer loop

    def shutdown(self) -> None:
        with self._lock:
            self._is_running = False

    @classmethod
    def sync_state(cls, data: bytes) -> None:
        """
        Send State Update to Base 3, if it is available and if this
        command packet is relevant
        """
        if cls._instance is None:  # if no base 3, nothing to do
            return
        if data:
            tmcc_cmd = None
            if data[0] == PDI_SOP:  # it's a Base 3 cmd, we only care about TMCC TX
                if len(data) > 2 and data[1] == PdiCommand.TMCC_TX:
                    pdi_req = PdiReq.from_bytes(data)
                    if isinstance(pdi_req, TmccReq) and pdi_req.pdi_command == PdiCommand.TMCC_TX:
                        tmcc_cmd = pdi_req.tmcc_command
            else:
                # convert the byte stream into a command
                tmcc_cmd = CommandReq.from_bytes(data)
            if tmcc_cmd is None:
                return

            # is it a command that requires a state sync?
            sync_req = BaseReq.update_eng(tmcc_cmd)
            if sync_req:
                cls._instance.send(sync_req.as_bytes)


class KeepAlive(Thread):
    """
    The Base 3 needs to receive a keep-alive signal in order for the
    connection to be maintained. This class/thread sends the keep-alive
    packet every 2 seconds
    """

    def __init__(self, writer: Base3Buffer) -> None:
        super().__init__(daemon=True, name="PyLegacy Base3 Keep Alive")
        self._writer = writer
        self._is_running = True
        self.start()

    def run(self) -> None:
        while self._is_running:
            self._writer.send(KEEP_ALIVE_CMD)
            time.sleep(2.0)
