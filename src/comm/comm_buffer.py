import time
from queue import Queue, Empty
from threading import Thread

import serial
from serial.serialutil import SerialException

from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_QUEUE_SIZE, DEFAULT_THROTTLE_DELAY


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
        """
            Return the current time, in milliseconds past the "epoch"
        """
        return round(time.time() * 1000)

    @property
    def port(self) -> str:
        return self._port

    @property
    def baudrate(self) -> int:
        return self._baudrate

    def run(self) -> None:
        # if the queue is empty AND _shutdown_signaled is True, then continue looping
        while not self._queue.empty() or not self._shutdown_signalled:
            try:
                data = self._queue.get(block=True, timeout=.25)
                print(f"Fire command 0x{data.hex()}")
                try:
                    with serial.Serial(self.port, self.baudrate) as ser:
                        millis_since_last_output = self._current_milli_time() - self._last_output_at
                        if millis_since_last_output < DEFAULT_THROTTLE_DELAY:
                            time.sleep((DEFAULT_THROTTLE_DELAY - millis_since_last_output)/1000.)
                        # Write the command byte sequence
                        ser.write(data)
                        self._last_output_at = self._current_milli_time()
                        print(f"Task Done: 0x{data.hex()}")
                        self._queue.task_done()
                except SerialException as se:
                    # TODO: handle serial errors
                    print(se)
                    print(f"Task Done (*** SE ***): 0x{data.hex()}")
                    self._queue.task_done()  # processing is complete, albeit unsuccessful
            except Empty:
                pass

    def enqueue_command(self, command: bytes) -> None:
        if command:
            print(f"Enqueue command 0x{command.hex()}")
            self._queue.put(command)

    def shutdown(self, immediate: bool = False) -> None:
        if immediate:
            with self._queue.mutex:
                self._queue.queue.clear()
                self._queue.all_tasks_done.notify_all()
                self._queue.unfinished_tasks = 0
        self._shutdown_signalled = True
