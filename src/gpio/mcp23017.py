import sys
import threading
from typing import List, Tuple, Dict, Set

from gpiozero import GPIOPinInUse, PinInvalidPin, Button

from src.gpio.i2c import I2C

IODIRA = 0x00  # Pin direction register
IODIRB = 0x01  # Pin direction register
IPOLA = 0x02
IPOLB = 0x03
GPINTENA = 0x04
GPINTENB = 0x05
DEFVALA = 0x06
DEFVALB = 0x07
INTCONA = 0x08
INTCONB = 0x09
IOCONA = 0x0A
IOCONB = 0x0B
GPPUA = 0x0C
GPPUB = 0x0D

INTFA = 0x0E
INTFB = 0x0F
INTCAPA = 0x10
INTCAPB = 0x11
GPIOA = 0x12
GPIOB = 0x13
OLATA = 0x14
OLATB = 0x15
ALL_OFFSET = [
    IODIRA,
    IODIRB,
    IPOLA,
    IPOLB,
    GPINTENA,
    GPINTENB,
    DEFVALA,
    DEFVALB,
    INTCONA,
    INTCONB,
    IOCONA,
    IOCONB,
    GPPUA,
    GPPUB,
    GPIOA,
    GPIOB,
    OLATA,
    OLATB,
]

BANK_BIT = 7
MIRROR_BIT = 6
SEQOP_BIT = 5
DISSLW_BIT = 4
HAEN_BIT = 3
ODR_BIT = 2
INTPOL_BIT = 1

GPA0 = 0
GPA1 = 1
GPA2 = 2
GPA3 = 3
GPA4 = 4
GPA5 = 5
GPA6 = 6
GPA7 = 7
GPB0 = 8
GPB1 = 9
GPB2 = 10
GPB3 = 11
GPB4 = 12
GPB5 = 13
GPB6 = 14
GPB7 = 15
ALL_GPIO = [GPA0, GPA1, GPA2, GPA3, GPA4, GPA5, GPA6, GPA7, GPB0, GPB1, GPB2, GPB3, GPB4, GPB5, GPB6, GPB7]

HIGH = 0xFF
LOW = 0x00

INPUT = 0xFF
OUTPUT = 0x00

ADDRESS_MAP = {
    0x00: "IODIRA",
    0x01: "IODIRB",
    0x02: "IPOLA",
    0x03: "IPOLB",
    0x04: "GPINTENA",
    0x05: "GPINTENB",
    0x06: "DEFVALA",
    0x07: "DEVFALB",
    0x08: "INTCONA",
    0x09: "INTCONB",
    0x0A: "IOCON",
    0x0B: "IOCON",
    0x0C: "GPPUA",
    0x0D: "GPPUB",
    0x0E: "INTFA",
    0x0F: "INTFB",
    0x10: "INTCAPA",
    0x11: "INTCAPB",
    0x12: "GPIOA",
    0x13: "GPIOB",
    0x14: "OLATA",
    0x15: "OLATB",
}
REGISTER_MAP = {value: key for key, value in ADDRESS_MAP.items()}


class Mcp23017:
    """
    Mcp23017 class to handle ICs register setup
    """

    def __init__(self, address: int = 0x23, i2c: I2C = None) -> None:
        self.address = address
        self.i2c = i2c if i2c else I2C()
        self._gpintena_pin = self._gpintenb_pin = None
        self._gpintena_btn = self._gpintenb_btn = None

    @property
    def gpintena_pin(self) -> int:
        return self._gpintena_pin

    @property
    def gpintenb_pin(self) -> int:
        return self._gpintenb_pin

    @property
    def gpintena_btn(self) -> Button:
        return self._gpintena_btn

    @property
    def gpintenb_btn(self) -> Button:
        return self._gpintenb_btn

    def interrupt_pin_range(self, pin: int) -> range | None:
        """
        Returns the range of DGPIO pins this interrupt pin services
        """
        if pin == self._gpintena_pin:
            return range(0, 8)
        elif pin == self._gpintenb_pin:
            return range(8, 16)
        return None

    def get_interrupt_pin(self, gpio) -> int:
        if 0 <= gpio <= 7:
            return self._gpintena_pin
        elif 8 <= gpio <= 15:
            return self._gpintenb_pin
        else:
            raise TypeError("pin must be one of GPAn or GPBn. See description for help")

    def set_all_output(self) -> None:
        """sets all GPIOs as OUTPUT"""
        self.i2c.write_to(self.address, IODIRA, OUTPUT)
        self.i2c.write_to(self.address, IODIRB, OUTPUT)

    def set_all_input(self) -> None:
        """sets all GPIOs as INPUT"""
        self.i2c.write_to(self.address, IODIRA, INPUT)
        self.i2c.write_to(self.address, IODIRB, INPUT)

    def set_all_pull_up(self) -> None:
        """turn on all pull-up resistors"""
        self.i2c.write_to(self.address, REGISTER_MAP["GPPUA"], HIGH)
        self.i2c.write_to(self.address, REGISTER_MAP["GPPUB"], HIGH)

    def get_all_pull_up(self) -> List[int]:
        """get all pull-up resistors state"""
        return [
            self.i2c.read_from(self.address, REGISTER_MAP["GPPUA"]),
            self.i2c.read_from(self.address, REGISTER_MAP["GPPUB"]),
        ]

    def unset_all_pull_up(self) -> None:
        """turn on all pull-up resistors"""
        self.i2c.write_to(self.address, REGISTER_MAP["GPPUA"], LOW)
        self.i2c.write_to(self.address, REGISTER_MAP["GPPUB"], LOW)

    def set_pull_up(self, gpio: int, mode: int | bool = True) -> None:
        """
        Sets the given GPIO to the given mode INPUT or OUTPUT
        :param gpio: the GPIO to set the mode to
        :param mode: one of INPUT or OUTPUT
        """
        pair = self.get_offset_gpio_tuple([GPPUA, GPPUA], gpio)
        if isinstance(mode, bool):
            mode = HIGH if mode is True else LOW
        self.set_bit_enabled(pair[0], pair[1], True if mode is HIGH else False)

    def get_pull_up(self, gpio: int) -> bool:
        pair = self.get_offset_gpio_tuple([GPPUA, GPPUA], gpio)
        return self.get_bit_enabled(pair[0], pair[1]) != 0

    def set_pin_mode(self, gpio, mode) -> None:
        """
        Sets the given GPIO to the given mode INPUT or OUTPUT
        :param gpio: the GPIO to set the mode to
        :param mode: one of INPUT or OUTPUT
        """
        pair = self.get_offset_gpio_tuple([IODIRA, IODIRB], gpio)
        self.set_bit_enabled(pair[0], pair[1], True if mode is INPUT else False)

    def get_pin_mode(self, gpio) -> int:
        """
        Gets the mode of the given GPIO (INPUT or OUTPUT)
        :param gpio: the GPIO to get the mode to
        """
        pair = self.get_offset_gpio_tuple([IODIRA, IODIRB], gpio)
        return self.get_bit_enabled(pair[0], pair[1])

    def digital_write(self, gpio, direction) -> None:
        """
        Sets the given GPIO to the given direction HIGH or LOW
        :param gpio: the GPIO to set the direction to
        :param direction: one of HIGH or LOW
        """
        pair = self.get_offset_gpio_tuple([OLATA, OLATB], gpio)
        self.set_bit_enabled(pair[0], pair[1], True if direction is HIGH else False)

    def digital_read(self, gpio) -> int:
        """
        Reads the current direction of the given GPIO
        :param gpio: the GPIO to read from
        :return:
        """
        pair = self.get_offset_gpio_tuple([GPIOA, GPIOB], gpio)
        bits = self.i2c.read_from(self.address, pair[0])
        return HIGH if (bits & (1 << pair[1])) > 0 else LOW

    def digital_read_all(self) -> List[int]:
        """
        Reads the current direction of the given GPIO
        :return:
        """
        return [self.i2c.read_from(self.address, GPIOA), self.i2c.read_from(self.address, GPIOB)]

    def set_interrupt(self, gpio, enabled: bool = True) -> None:
        """
        Enables or disables the interrupt of a given GPIO
        :param gpio: the GPIO where the interrupt needs to be set,
        this needs to be one of GPAn or GPBn constants
        :param enabled: enable or disable the interrupt
        """
        pair = self.get_offset_gpio_tuple([GPINTENA, GPINTENB], gpio)
        self.set_bit_enabled(pair[0], pair[1], enabled)

    def set_all_interrupt(self, enabled: bool = True) -> None:
        """
        Enables or disables the interrupt of all GPIOs
        :param enabled: enable or disable the interrupt
        """
        self.i2c.write_to(self.address, GPINTENA, 0xFF if enabled else 0x00)
        self.i2c.write_to(self.address, GPINTENB, 0xFF if enabled else 0x00)

    def set_interrupt_mirror(self, enable: bool = True) -> None:
        """
        Enables or disables the interrupt mirroring
        :param enable: enable or disable the interrupt mirroring
        """
        self.set_bit_enabled(IOCONA, MIRROR_BIT, enable)
        self.set_bit_enabled(IOCONB, MIRROR_BIT, enable)

    def read_interrupt_captures(self) -> Tuple[List[str], List[str]]:
        """
        Reads the interrupt captured register. It captures the GPIO port value at the time
        the interrupt occurred.
        :return: a tuple of the INTCAPA and INTCAPB interrupt capture as a list of bit string
        """
        return self._get_list_of_interrupted_values_from(INTCAPA), self._get_list_of_interrupted_values_from(INTCAPB)

    def _get_list_of_interrupted_values_from(self, offset) -> List[str]:
        li = []
        interrupted = self.i2c.read_from(self.address, offset)
        bits = "{0:08b}".format(interrupted)
        for i in reversed(range(8)):
            li.append(bits[i])

        return li

    def read_interrupt_flags(self) -> Tuple[List[str], List[str]]:
        """
        Reads the interrupt flag which reflects the interrupt condition. A set bit
        indicates that the associated pin caused the interrupt.
        :return: a tuple of the INTFA and INTFB interrupt flags as list of bit string
        """
        return self._read_interrupt_flags_from(INTFA), self._read_interrupt_flags_from(INTFB)

    def _read_interrupt_flags_from(self, offset) -> List[str]:
        li = []
        interrupted = self.i2c.read_from(self.address, offset)
        bits = "{0:08b}".format(interrupted)
        for i in reversed(range(8)):
            li.append(bits[i])
        return li

    def read(self, offset) -> int:
        return self.i2c.read_from(self.address, offset)

    def write(self, offset, value) -> None:
        return self.i2c.write_to(self.address, offset, value)

    @staticmethod
    def get_offset_gpio_tuple(offsets, gpio):
        if offsets[0] not in ALL_OFFSET or offsets[1] not in ALL_OFFSET:
            raise TypeError("offsets must contain a valid offset address. See description for help")
        if gpio not in ALL_GPIO:
            raise TypeError("pin must be one of GPAn or GPBn. See description for help")

        offset = offsets[0] if gpio < 8 else offsets[1]
        _gpio = gpio % 8
        return offset, _gpio

    def set_bit_enabled(self, offset: int, gpio: int, enable: bool = True) -> None:
        state_before = self.i2c.read_from(self.address, offset)
        value = (state_before | self.bitmask(gpio)) if enable else (state_before & ~self.bitmask(gpio))
        self.i2c.write_to(self.address, offset, value)

    def get_bit_enabled(self, offset: int, gpio: int) -> int:
        state = self.i2c.read_from(self.address, offset)
        value = state & self.bitmask(gpio)
        return value

    @staticmethod
    def bitmask(gpio) -> int:
        return 1 << (gpio % 8)

    def create_interrupt_handler(self, pin, interrupt_pin) -> None:
        btn = Button(interrupt_pin)
        btn.when_pressed = lambda x: print("pressed", x, self.read_interrupt_flags(), self.digital_read(pin))
        # btn.when_activated = lambda b: print("activated", b, self.read_interrupt_flags())
        btn.when_released = lambda x: print("released", x, self.read_interrupt_flags(), self.digital_read(pin))
        # btn.when_deactivated = lambda b: print("deactivated", b, self.read_interrupt_flags())
        if 0 <= pin <= 7:
            self._gpintena_pin = interrupt_pin
            self._gpintena_btn = btn
        elif 8 <= pin <= 15:
            self._gpintenb_pin = interrupt_pin
            self._gpintenb_btn = btn
        else:
            raise TypeError("pin must be one of GPAn or GPBn. See description for help")
        self.read_interrupt_captures()

    def close(self) -> None:
        if self._gpintenb_btn:
            self._gpintenb_btn.close()
        if self._gpintena_btn:
            self._gpintena_btn.close()
        self._gpintenb_btn = self._gpintena_btn = None
        self._gpintena_pin = self._gpintenb_pin = None


class Mcp23017Factory:
    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(
        cls,
        address: int = 0x23,
        pin: int = 0,
        interrupt_pin: int | str = None,
    ) -> Mcp23017:
        if pin is None or pin < 0 or pin > 15:
            raise PinInvalidPin(f"{pin} is not a valid pin")
        with cls._lock:
            if cls._instance is None:
                cls._instance = Mcp23017Factory()
            mcp23017 = cls._instance._mcp23017s.get(address, None)
            if mcp23017 is None:
                mcp23017 = Mcp23017(address)
                cls._instance._mcp23017s[address] = mcp23017
                cls._instance._pins_in_use[address] = set()
            if pin not in cls._instance._pins_in_use[address]:
                cls._instance._pins_in_use[address].add(pin)
            else:
                raise GPIOPinInUse(f"Pin {pin} is already in use by Mcp23017 at address {hex(address)}")
            if interrupt_pin is not None:
                # the CQRobot Ocean board supports 2 interrupt lines, one for DGPIO ports 0-7 (A),
                # and another for DGPIO ports 8-15 (B). We hve to make sure the given interrupt port
                # hasn't been assigned to a different I2C board or that it hasn't been assigned to
                # a different bank on this board
                assigned = cls._instance._interrupt_pins.get(interrupt_pin, None)
                if assigned is not None:
                    if assigned != mcp23017:
                        raise GPIOPinInUse(
                            f"Pin {interrupt_pin} is already in use by Mcp23017 at address {hex(assigned.address)}"
                        )
                    associated_pins = mcp23017.interrupt_pin_range(interrupt_pin)
                    if associated_pins:
                        if pin not in associated_pins:
                            raise GPIOPinInUse(
                                f"Pin {interrupt_pin} is already in use by Mcp23017 for pins {associated_pins}"
                            )
                        # one more check, has the interrupt machinery been created? If so, we're done
                        if pin in associated_pins:
                            return mcp23017
                # set the interrupt pin state to low
                if sys.platform == "linux":
                    import lgpio

                    pi = lgpio.gpiochip_open(0)
                    lgpio.gpio_write(pi, interrupt_pin, 0)
                    lgpio.gpio_free(pi, interrupt_pin)
                    lgpio.gpiochip_close(pi)
                    print(f"Set pin {interrupt_pin} low")
                mcp23017.digital_read(pin)
                cls._instance._interrupt_pins[interrupt_pin] = mcp23017
                mcp23017.create_interrupt_handler(pin, interrupt_pin)

            return mcp23017

    # noinspection PyProtectedMember
    @classmethod
    def close(cls, mcp23017: Mcp23017, pin: int) -> None:
        with cls._lock:
            if cls._instance is None:
                return  # really this is an invalid state...
            if mcp23017.address in cls._instance._mcp23017s:
                cls._instance._pins_in_use[mcp23017.address].discard(pin)
                if len(cls._instance._pins_in_use[mcp23017.address]) == 0:
                    if mcp23017.gpintena_pin is not None:
                        cls._instance._interrupt_pins.pop(mcp23017.gpintena_pin)
                    if mcp23017.gpintenb_pin is not None:
                        cls._instance._interrupt_pins.pop(mcp23017.gpintenb_pin)
                    mcp23017.close()
                    cls._instance._mcp23017s.pop(mcp23017.address)
                    cls._instance._pins_in_use.pop(mcp23017.address)

    def __init__(self) -> None:
        if self._initialized:
            return
        else:
            self._initialized = True
        self._mcp23017s: Dict[int, Mcp23017] = dict()
        self._pins_in_use: Dict[int, Set[int]] = dict()
        self._interrupt_pins: Dict[int, Mcp23017] = dict()

    def __new__(cls, *args, **kwargs):
        """
        Provides singleton functionality. We only want one instance
        of this class in a process
        """
        with cls._lock:
            if Mcp23017Factory._instance is None:
                # noinspection PyTypeChecker
                Mcp23017Factory._instance = super(Mcp23017Factory, cls).__new__(cls)
                Mcp23017Factory._instance._initialized = False
            return Mcp23017Factory._instance
