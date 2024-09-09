import time
from queue import Queue
from threading import Thread

import serial
from serial.serialutil import SerialException

from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_QUEUE_SIZE


class CommBuffer(Thread):
    _instance = None

    def __init__(self,
                 queue_size: int = DEFAULT_QUEUE_SIZE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT
                 ) -> None:
        super().__init__(daemon=False, name="PyLegacy Comm Buffer")
        self._baudrate = baudrate
        self._port = port
        self._queue_size = queue_size
        self._queue = Queue(queue_size)
        self._shutdown_signalled = False
        self._last_output_at = 0  # used to throttle writes to LCS SER2
        # start the consumer thread
        self.start()

    def __new__(cls, *args, **kwargs):
        """
            Provides singleton functionality. We only want one instance
            of this class in the system
        """
        if not cls._instance:
            cls._instance = super(CommBuffer, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def _current_milli_time() -> int:
        return round(time.time() * 1000)

    @property
    def port(self) -> str:
        return self._port

    @property
    def baudrate(self) -> int:
        return self._baudrate

    def run(self) -> None:
        while self._queue.qsize() or not self._shutdown_signalled:
            data = self._queue.get()
            print(f"Fire command {data.hex()}")
            try:
                with serial.Serial(self.port, self.baudrate) as ser:
                    # Write the byte sequence
                    ser.write(data)
                    self._last_output_at = self._current_milli_time()
            except SerialException as se:
                # TODO: handle serial errors
                print(se)
            self._queue.task_done()
        print(f"Queue size {self._queue.qsize()}")

    def enqueue_command(self, command: bytes) -> None:
        if command:
            self._queue.put(command)

    def shutdown(self) -> None:
        self._shutdown_signalled = True
