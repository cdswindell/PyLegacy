from __future__ import annotations

import logging
import select
import socket
import threading
import time

# from signal import signal, SIGPIPE, SIG_DFL
from threading import Condition, Thread

from ..protocol.command_req import CommandReq
from ..protocol.constants import (
    DEFAULT_BASE_PORT,
    DEFAULT_QUEUE_SIZE,
    PROGRAM_NAME,
    CommandScope,
)
from ..utils.pollable_queue import PollableQueue
from .base_req import BaseReq
from .constants import KEEP_ALIVE_CMD, PDI_SOP, TMCC4_TX, TMCC_TX, PdiCommand
from .pdi_listener import PdiListener
from .pdi_req import PdiReq, TmccReq

log = logging.getLogger(__name__)


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

    @classmethod
    def get(cls) -> Base3Buffer:
        if cls._instance is None:
            raise AttributeError("Base3Buffer has not been initialized")
        return cls._instance

    @classmethod
    def base_address(cls) -> str:
        if cls._instance is None:
            raise AttributeError("Base3Buffer has not been initialized")
        # noinspection PyProtectedMember
        return cls._instance._base3_addr

    @classmethod
    def request_state_update(cls, tmcc_id: int, scope: CommandScope) -> None:
        if cls._instance is not None:
            if 1 <= tmcc_id <= 9999:
                cls.enqueue_command(BaseReq(tmcc_id, PdiCommand.BASE_MEMORY, scope=scope).as_bytes)

    @classmethod
    def enqueue_command(cls, data: bytes) -> None:
        if cls._instance is not None and data:
            cls._instance.send(data)

    def __init__(
        self,
        base3_addr: str,
        base3_port: int = DEFAULT_BASE_PORT,
        buffer_size: int = DEFAULT_QUEUE_SIZE,
        listener: PdiListener = None,
    ) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Base3 Interface")
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
        # we must send a keepalive packet to the Base 3 every few seconds to keep it
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
                # noinspection PyTypeChecker
                Base3Buffer._instance = super(Base3Buffer, cls).__new__(cls)
                Base3Buffer._instance._initialized = False
            return Base3Buffer._instance

    def send(self, data: bytes) -> None:
        if data:
            from ..protocol.multibyte.multibyte_command_req import MultiByteReq

            # If we are sending a multibyte TMCC or TMCC_4D command, we have to break
            # it down into 3-7 byte packets; this needs to be done here so sync_state
            # in the calling layer gets a complete command
            cmd_bytes = data[2:-2]
            is_mvb, is_d4 = MultiByteReq.vet_bytes(cmd_bytes, raise_exception=False)
            if data[1] in {TMCC_TX, TMCC4_TX} and is_mvb:
                tmcc_cmd = CommandReq.from_bytes(cmd_bytes)
                # This is a legacy/tmcc2 multibyte parameter command. We have to send it
                # as 3 3 byte packets, using PdiCommand.TMCC_RX
                for packet in TmccReq.as_packets(tmcc_cmd):
                    self.send(packet)  # recursive call
                    time.sleep(0.001)
                # do a sync_state on the complete command
                self.sync_state(data)
            else:
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
        keep_trying = 10  # when we can't send a packet, retry 10 times
        while self._is_running and keep_trying:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect((str(self._base3_addr), self._base3_port))
                    # we want to wait on either data being available to send to the Base3 of
                    # data available from the Base 3 to process
                    socket_list = [s, self._send_queue]
                    while self._is_running and keep_trying:
                        try:
                            readable, _, _ = select.select(socket_list, [], [])
                            for sock in readable:
                                if sock == self._send_queue:
                                    received = None
                                    sending = sock.get()
                                    # millis_since_last_output = self._current_milli_time() - self._last_output_at
                                    # if millis_since_last_output < DEFAULT_BASE_THROTTLE_DELAY:
                                    #     time.sleep((DEFAULT_BASE_THROTTLE_DELAY - millis_since_last_output) / 1000.0)
                                    s.sendall(sending.hex().upper().encode())
                                    self._last_output_at = self._current_milli_time()
                                    # update base3 with new state; required if command is a tmcc_tx
                                    try:
                                        self.sync_state(sending)
                                    except ValueError as ve:
                                        # TODO: we get exceptions here if we send a multi-byte tmcc command
                                        # TODO: because they are packet-ized into 3-byte chunks that sync-state
                                        # TODO cannot yet handle
                                        log.debug(ve)
                                    except Exception as e:
                                        log.exception(e)
                                else:
                                    sending = None
                                    received = bytes.fromhex(s.recv(512).decode(errors="ignore"))
                                    # but there is more trickiness; The Base 3 sends ascii characters
                                    # so when we receive: 'D12729DF', this actually is sent as eight
                                    # characters; D, 1, 2, 7, 2, 9, D, F, so we must decode the 8
                                    # received bytes into 8 ASCII characters, then interpret that
                                    # ASCII string as Hex representation to arrive at 0xd12729df...
                                if self._listener and received:
                                    self._listener.offer(received)
                            keep_trying = 10
                        except BrokenPipeError as bpe:
                            # keep trying; unix can sometimes just hang up
                            if sending is not None:
                                log.info(f"Exception sending: 0x{sending.hex(':').upper()}; retrying ({bpe})")
                                self.send(sending)
                            elif received is not None:
                                log.info(f"Exception receiving: 0x{received.hex(':').upper()}; retrying: {bpe}")
                            else:
                                log.exception(bpe)
                            keep_trying -= 1
                            break  # continues to outer loop
                        except ValueError as ve:
                            log.debug(ve)
                except OSError as oe:
                    log.info(
                        f"No response from Lionel Base 3 at {self._base3_addr}; is the Base 3 turned on? Retrying..."
                    )
                    log.exception(oe)
                    keep_trying -= 1
                    if keep_trying <= 0:
                        raise oe
                    else:
                        time.sleep(30 if oe.errno == 113 else 1)

    def shutdown(self) -> None:
        with self._lock:
            self._is_running = False

    @classmethod
    def sync_state(cls, data: bytes, pdi_req: PdiReq = None) -> None:
        """
        Send State Update to Base 3 if it is available and if this
        command packet is relevant
        """
        if cls._instance is None or data == KEEP_ALIVE_CMD:  # if no base 3 or ping, nothing to do
            return
        if data:
            tmcc_cmds = []
            if data[0] == PDI_SOP:  # it's a Base 3 cmd, we only care about TMCC TX/TMCC4_TX
                if len(data) > 2 and data[1] in {PdiCommand.TMCC_TX, PdiCommand.TMCC4_TX}:
                    try:
                        if pdi_req is None:
                            pdi_req = PdiReq.from_bytes(data)
                        if isinstance(pdi_req, TmccReq) and pdi_req.pdi_command in {
                            PdiCommand.TMCC_TX,
                            PdiCommand.TMCC4_TX,
                        }:
                            tmcc_cmds.append(pdi_req.tmcc_command)
                    except NotImplementedError:
                        return  # ignore exceptions; most likely it's a multibyte cmd
            else:
                # convert the byte stream into one or more commands
                command_seq = bytes()
                for b in data:
                    from ..protocol.command_req import TMCC_FIRST_BYTE_TO_INTERPRETER

                    # When we sync state, states are expressed as the byte-string representations
                    # of the command(s) that generate them. This means that the byte string we
                    # received here likely consists of multiple commands. CommandReq.from_bytes
                    # expects to receive only one command's worth of bytes at a time, so we have
                    # to break up the byte stream back into the component byte strings for each cmd.
                    if b in TMCC_FIRST_BYTE_TO_INTERPRETER and len(command_seq) >= 3:
                        if command_seq:
                            try:
                                tmcc_cmds.append(CommandReq.from_bytes(command_seq))
                                command_seq = bytes()
                            except ValueError:
                                pass
                    command_seq += b.to_bytes(1, byteorder="big")
                if command_seq:
                    tmcc_cmds.append(CommandReq.from_bytes(command_seq))
            for tmcc_cmd in tmcc_cmds:
                # is it a command that requires a state sync?
                sync_reqs = BaseReq.update_eng(tmcc_cmd)
                if sync_reqs:
                    for sync_req in sync_reqs:
                        cls._instance.send(sync_req.as_bytes)


class KeepAlive(Thread):
    """
    The Base 3 needs to receive a keep-alive signal in order for the
    connection to be maintained. This class/thread sends the keep-alive
    packet every 2 seconds
    """

    def __init__(self, writer: Base3Buffer) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Base3 Keep Alive")
        self._writer = writer
        self._is_running = True
        self.start()

    def run(self) -> None:
        while self._is_running:
            self._writer.send(KEEP_ALIVE_CMD)
            time.sleep(2.0)
