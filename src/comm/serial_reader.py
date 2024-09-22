import serial

from ..protocol.constants import DEFAULT_BAUDRATE, DEFAULT_PORT


class SerialReader:
    def __init__(self,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        self._baudrate = baudrate
        self._port = port

    def read_bytes(self) -> None:
        with serial.Serial(self._port, self._baudrate, timeout=1.0) as ser:
            while True:
                ser2_bytes = ser.read(1024)
                if ser2_bytes:
                    print(ser2_bytes.hex(':'))
                    