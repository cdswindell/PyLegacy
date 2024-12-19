class MBusMock:
    def __init__(self) -> None:
        self.data = {}
        for address in range(0x20, 0x28):
            self.data[address] = {}
            for offset in range(0x00, 0x16):
                self.data[address][offset] = 0x00
                if offset == 0x00 or offset == 0x01:
                    self.data[address][offset] = 0xFF

    def write_byte_data(self, address, offset, value) -> None:
        self.data[address][offset] = value

    def read_byte_data(self, address, offset) -> int:
        return self.data[address][offset]

    def read_byte(self, address) -> int:
        return next(iter(self.data[address].values()))
