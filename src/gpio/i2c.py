import sys
from typing import List

from smbus2 import SMBus

if sys.platform == "linux":
    try:
        DEFAULT_SMBUS = SMBus(1)
    except FileNotFoundError:
        DEFAULT_SMBUS = None
else:
    DEFAULT_SMBUS = None


class I2C:
    def __init__(self, smbus: SMBus = DEFAULT_SMBUS):
        """
        Wrapper class for a smbus
        :param smbus: the smbus to send and receive data from smbus.SMBus(1)
        """
        self.bus: SMBus = smbus

    def write_to(self, address: int, offset: int, value: int) -> None:
        self.bus.write_byte_data(address, offset, value)

    def read_from(self, address: int, offset: int = 0) -> int:
        return self.bus.read_byte_data(address, offset)

    def read(self, address: int) -> int:
        return self.bus.read_byte(address)

    def scan(self) -> List[int]:
        devices = list()
        for address in range(255):
            try:
                self.bus.read_byte(address)  # try to read byte
                devices.append(address)
            except KeyError:  # exception if read_byte fails
                pass
        return devices
