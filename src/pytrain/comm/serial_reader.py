import logging
import time
from threading import Thread

import serial

from .command_listener import CommandListener
from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT, PROGRAM_NAME

log = logging.getLogger(__name__)


class SerialReader(Thread):
    def __init__(
        self, baudrate: int = DEFAULT_BAUDRATE, port: str = DEFAULT_PORT, consumer: CommandListener = None
    ) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Serial Port Reader")
        self._consumer = consumer
        self._baudrate = baudrate
        self._port = port
        self._is_running = True
        self.start()

    def run(self) -> None:
        with serial.Serial(
            self._port,
            self._baudrate,
            bytesize=serial.EIGHTBITS,
            exclusive=True,
            timeout=1.0,
        ) as ser:
            while self._is_running:
                try:
                    in_waiting = ser.in_waiting
                    if in_waiting > 0:
                        ser2_bytes = ser.read(256)
                        if ser2_bytes:
                            if self._consumer:
                                self._consumer.offer(ser2_bytes)
                            else:
                                log.warning(f"No serial consumer for: {ser2_bytes.hex(':')}")
                    # give the CPU a break
                    time.sleep(0.05)
                except serial.SerialException as se:
                    if se.errno is None:
                        pass
                    else:
                        log.exception(se)
                except Exception as e:
                    log.exception(e)

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @property
    def port(self) -> str:
        return self._port

    @property
    def is_consumer(self) -> bool:
        return self._consumer is not None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def shutdown(self) -> None:
        self._is_running = False
