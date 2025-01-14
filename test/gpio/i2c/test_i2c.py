from src.pytrain.gpio.i2c.i2c import I2C
from test.test_base import TestBase
from .smbusmock import MBusMock


class TestI2c(TestBase):
    def test_i2c_init(self) -> None:
        smbus = MBusMock()
        # noinspection PyTypeChecker
        i2c = I2C(smbus)
        assert i2c.bus == smbus

    def test_write_read_data(self) -> None:
        # noinspection PyTypeChecker
        i2c = I2C(MBusMock())
        assert i2c.read_from(0x20, 0x01) == 0xFF
        i2c.write_to(0x20, 0x01, 0x00)
        assert i2c.read_from(0x20, 0x01) == 0x00

    def test_read(self) -> None:
        # noinspection PyTypeChecker
        i2c = I2C(MBusMock())
        assert i2c.read(0x20) == 0xFF

    def test_scan(self) -> None:
        # noinspection PyTypeChecker
        i2c = I2C(MBusMock())
        devices = i2c.scan()
        assert len(devices) == 8
