import time
from threading import Thread

import serial

from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT


class SerialReader(Thread):
    from .command_listener import CommandListener

    def __init__(self,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT,
                 consumer: CommandListener = None) -> None:
        super().__init__(name="PyLegacy Serial Port Reader")
        self._consumer = consumer
        self._baudrate = baudrate
        self._port = port
        self._is_running = True
        self.start()

    def run(self) -> None:
        try:
            with serial.Serial(self._port, self._baudrate, timeout=1.0) as ser:
                while self._is_running:
                    if ser.in_waiting:
                        ser2_bytes = ser.read(256)
                        if ser2_bytes:
                            if self._consumer:
                                self._consumer.offer(ser2_bytes)
                            else:
                                print(ser2_bytes.hex(':'))
                    # give the CPU a break
                    time.sleep(0.01)
        except Exception as e:
            print(e)

    def shutdown(self) -> None:
        self._is_running = False
                    