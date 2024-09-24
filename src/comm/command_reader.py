from __future__ import annotations

import threading
from collections import deque
from threading import Thread

from ..protocol.command_req import TMCC_FIRST_BYTE_TO_INTERPRETER, CommandReq
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from ..protocol.tmcc2.tmcc2_constants import LEGACY_PARAMETER_COMMAND_PREFIX


class CommandReader(Thread):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in a process
        """
        with cls._lock:
            if CommandReader._instance is None:
                CommandReader._instance = super(CommandReader, cls).__new__(cls)
                CommandReader._instance._initialized = False
            return CommandReader._instance

    def __init__(self,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        super().__init__(name="PyLegacy Command Reader")
        # prep our consumer
        self._is_running = True
        self._cv = threading.Condition()
        self._deque = deque(maxlen=1024)
        self.start()
        # prep our producer
        from .serial_reader import SerialReader
        self._serial_reader_thread = SerialReader(baudrate, port, self)

    def run(self) -> None:
        while self._is_running:
            # process bytes, as long as there are any
            with self._cv:
                if not self._deque:
                    self._cv.wait()  # wait to be notified
            # check if the first bite is in the list of allowable command prefixes
            dq_len = len(self._deque)
            if self._deque[0] in TMCC_FIRST_BYTE_TO_INTERPRETER and dq_len >= 3:
                # at this point, we have some sort of command. It could be a TMCC1 or TMCC2
                # 3-byte command, or, if there are more than 3 bytes, and the 4th byte is
                # 0xf8 or 0xf9 AND the 5th byte is 0xfb, it could be a 9 byte param command
                # Try for the 9-biters first
                cmd_bytes = bytes()
                if (dq_len >= 9 and
                        self._deque[4] == LEGACY_PARAMETER_COMMAND_PREFIX and
                        self._deque[7] == LEGACY_PARAMETER_COMMAND_PREFIX):
                    for _ in range(10):
                        cmd_bytes += bytes(self._deque.popleft())
                elif dq_len >= 5 and self._deque[4] == LEGACY_PARAMETER_COMMAND_PREFIX:
                    # we could be in the middle of receiving a parameter command, wait a bit longer
                    continue
                else:
                    # assume a 3 byte command
                    for _ in range(3):
                        cmd_bytes += bytes(self._deque.popleft())
                if cmd_bytes:
                    print(cmd_bytes.hex(':'))
                    try:
                        print(CommandReq.from_bytes(cmd_bytes))
                    except ValueError as ve:
                        print(ve)
            elif len(self._deque) < 3:
                continue  # wait for more bytes
            else:
                # pop this byte and continue; we either received unparsable input
                # or started receiving data mid-command
                self._deque.popleft()

    def offer(self, data: bytes) -> None:
        if data:
            with self._cv:
                print(f"Offering: {data.hex(':')}")
                self._deque.extend(data)
                self._cv.notify()

    def shutdown(self) -> None:
        self._is_running = False
                    