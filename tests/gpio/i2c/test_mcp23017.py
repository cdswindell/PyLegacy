import unittest

from src.pytrain.gpio.i2c.mcp23017 import *
from .smbusmock import MBusMock


class TestMCP23017(unittest.TestCase):
    # noinspection PyTypeChecker
    i2c = I2C(MBusMock())
    mockAddress = 0x20

    def test_mcp23017_init(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        self.assertEqual(mcp.address, 0x20)

    def test_get_offset_pin_pair(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        pair = mcp.get_offset_gpio_tuple([GPINTENA, GPINTENB], GPA2)
        self.assertEqual(pair[0], GPINTENA)
        self.assertEqual(pair[1], GPA2)

        pair = mcp.get_offset_gpio_tuple([INTCONA, INTCONB], GPB0)
        self.assertEqual(pair[0], INTCONB)
        self.assertEqual(pair[1], GPB0 % 8)

    def test_get_offset_pin_pair_type_error(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        with self.assertRaises(TypeError):
            mcp.get_offset_gpio_tuple([INTCONA, INTCONB], 18)

        with self.assertRaises(TypeError):
            mcp.get_offset_gpio_tuple([INTCONA, INTCONB], -1)

        with self.assertRaises(TypeError):
            mcp.get_offset_gpio_tuple([0xFF, INTCONB], 1)

        with self.assertRaises(TypeError):
            mcp.get_offset_gpio_tuple([INTCONB, 0xFF], 1)

    def test_set_all_output(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        mcp.set_all_output()
        self.assertEqual(mcp.read(IODIRA), 0b00000000)
        self.assertEqual(mcp.read(IODIRB), 0b00000000)

    def test_set_all_input(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        mcp.set_all_input()
        self.assertEqual(mcp.read(IODIRA), 0b11111111)
        self.assertEqual(mcp.read(IODIRB), 0b11111111)

    def test_pin_mode(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        mcp.set_all_output()
        mcp.set_pin_mode(GPA0, INPUT)
        self.assertEqual(mcp.read(IODIRA), 0b00000001)
        mcp.set_pin_mode(GPA7, INPUT)
        self.assertEqual(mcp.read(IODIRA), 0b10000001)
        mcp.set_pin_mode(GPB7, INPUT)
        self.assertEqual(mcp.read(IODIRA), 0b10000001)
        self.assertEqual(mcp.read(IODIRB), 0b10000000)
        mcp.set_pin_mode(GPA0, OUTPUT)
        mcp.set_pin_mode(GPA7, OUTPUT)
        self.assertEqual(mcp.read(IODIRA), 0b00000000)

    def test_digital_write(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        mcp.set_all_output()
        self.assertEqual(mcp.read(OLATA), 0b00000000)
        self.assertEqual(mcp.read(OLATB), 0b00000000)

        mcp.digital_write(GPA0, HIGH)
        self.assertEqual(mcp.read(OLATA), 0b00000001)
        mcp.digital_write(GPA0, LOW)
        self.assertEqual(mcp.read(OLATA), 0b00000000)
        mcp.digital_write(GPA7, HIGH)
        self.assertEqual(mcp.read(OLATA), 0b10000000)

        mcp.digital_write(GPB0, HIGH)
        self.assertEqual(mcp.read(OLATA), 0b10000000)
        self.assertEqual(mcp.read(OLATB), 0b00000001)
        mcp.digital_write(GPB0, LOW)
        self.assertEqual(mcp.read(OLATA), 0b10000000)
        self.assertEqual(mcp.read(OLATB), 0b00000000)

    def test_set_interrupt(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        mcp.set_all_input()
        mcp.enable_interrupt(GPA0)
        self.assertEqual(mcp.read(GPINTENA), 0b00000001)
        mcp.enable_interrupt(GPA6)
        self.assertEqual(mcp.read(GPINTENA), 0b01000001)
        mcp.disable_interrupt(GPA0)
        self.assertEqual(mcp.read(GPINTENA), 0b01000000)
        mcp.enable_interrupt(GPB0)
        self.assertEqual(mcp.read(GPINTENB), 0b00000001)

    def test_set_all_interrupt(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        mcp.set_all_input()
        mcp.enable_interrupts()
        self.assertEqual(mcp.read(GPINTENA), 0b11111111)
        self.assertEqual(mcp.read(GPINTENB), 0b11111111)
        mcp.disable_interrupts()
        self.assertEqual(mcp.read(GPINTENA), 0b00000000)
        self.assertEqual(mcp.read(GPINTENB), 0b00000000)

    def test_interrupt_mirror(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        mcp.set_all_input()
        mcp.set_interrupt_mirror(True)
        self.assertEqual(mcp.read(IOCONA), 0b01000000)
        self.assertEqual(mcp.read(IOCONB), 0b01000000)
        mcp.set_interrupt_mirror(False)
        self.assertEqual(mcp.read(IOCONA), 0b00000000)
        self.assertEqual(mcp.read(IOCONB), 0b00000000)

    def test_read_interrupt_captures(self):
        mcp = Mcp23017(self.mockAddress, self.i2c)
        mcp.set_all_output()
        self.assertEqual(mcp.read(INTCAPA), 0b00000000)
        self.assertEqual(mcp.read(INTCAPB), 0b00000000)
        mcp.write(INTCAPA, 0x01)
        interrupt_captures = mcp.read_interrupt_captures()
        self.assertEqual(interrupt_captures[0][0], "1")
