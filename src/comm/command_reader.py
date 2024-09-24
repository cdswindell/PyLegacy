from __future__ import annotations

import threading
from threading import Thread


from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT


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
        from .serial_reader import SerialReader
        self._serial_reader_thread = SerialReader(baudrate, port, self)
        self.start()

    def run(self) -> None:
        pass

    def offer(self, b: int) -> None:
        pass
                    