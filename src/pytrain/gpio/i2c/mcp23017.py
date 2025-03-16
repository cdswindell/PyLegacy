import threading
import time
from typing import List, Tuple, Dict, Set

from gpiozero import GPIOPinInUse, PinInvalidPin, Button, Device

from .i2c import I2C
from .i2c_device import I2CDevice

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
        self._lock = threading.RLock()
        self.address = address
        self.i2c = i2c if i2c else I2C()
        self.set_all_input()
        self.set_all_pull_up()
        self.set_all_interrupt_config()
        self.set_interrupt_mirror(True)
        self._int_pin = None
        self._int_btn = None
        self._clients: Dict[int, I2CDevice] = dict()

    @property
    def interrupt_pin(self) -> int:
        return self._int_pin

    @property
    def interrupt_btn(self) -> Button:
        return self._int_btn

    @property
    def polarities(self) -> int:
        ret = self.i2c.read_from(self.address, IPOLA)
        ret |= self.i2c.read_from(self.address, IPOLB) << 8
        return ret

    @polarities.setter
    def polarities(self, value: int) -> None:
        self.i2c.write_to(self.address, IPOLA, value & 0xFF)
        self.i2c.write_to(self.address, IPOLB, (value >> 8) & 0xFF)

    def set_polarity(self, gpio: int, value: int) -> None:
        pair = self.get_offset_gpio_tuple([IPOLA, IPOLB], gpio)
        self.set_bit_enabled(pair[0], pair[1], True if value is HIGH else False)

    def get_polarity(self, gpio: int) -> int:
        pair = self.get_offset_gpio_tuple([IPOLA, IPOLB], gpio)
        return HIGH if self.get_bit_enabled(pair[0], pair[1]) != 0 else LOW

    def set_all_polarity_low(self) -> None:
        """sets all GPIOs normal polarity"""
        self.i2c.write_to(self.address, IPOLA, LOW)
        self.i2c.write_to(self.address, IPOLB, LOW)

    def set_all_output(self) -> None:
        """sets all GPIOs as OUTPUT"""
        self.i2c.write_to(self.address, IODIRA, OUTPUT)
        self.i2c.write_to(self.address, IODIRB, OUTPUT)

    def set_all_input(self) -> None:
        """sets all GPIOs as INPUT"""
        self.i2c.write_to(self.address, IODIRA, INPUT)
        self.i2c.write_to(self.address, IODIRB, INPUT)

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

    @property
    def pin_modes(self) -> int:
        ret = self.i2c.read_from(self.address, IODIRA)
        ret |= self.i2c.read_from(self.address, IODIRB) << 8
        return ret

    @pin_modes.setter
    def pin_modes(self, value: int) -> None:
        self.i2c.write_to(self.address, IODIRA, value & 0xFF)
        self.i2c.write_to(self.address, IODIRB, (value >> 8) & 0xFF)

    @property
    def pull_ups(self) -> int:
        ret = self.i2c.read_from(self.address, GPPUA)
        ret |= self.i2c.read_from(self.address, GPPUB) << 8
        return ret

    @pull_ups.setter
    def pull_ups(self, value: int) -> None:
        self.i2c.write_to(self.address, GPPUA, value & 0xFF)
        self.i2c.write_to(self.address, GPPUB, (value >> 8) & 0xFF)

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

    def digital_write(self, gpio, state) -> None:
        """
        Sets the given GPIO to the given state: HIGH or LOW
        :param gpio: the GPIO to set the state of
        :param state: one of HIGH or LOW
        """
        pair = self.get_offset_gpio_tuple([OLATA, OLATB], gpio)
        self.set_bit_enabled(pair[0], pair[1], True if state is HIGH else False)

    def digital_read(self, gpio) -> int:
        """
        Reads the current direction of the given GPIO
        :param gpio: the GPIO to read from
        :return:
        """
        pair = self.get_offset_gpio_tuple([GPIOA, GPIOB], gpio)
        with self._lock:
            bits = self.i2c.read_from(self.address, pair[0])
            return HIGH if (bits & (1 << pair[1])) > 0 else LOW

    def value(self, gpio: int) -> int:
        return 1 if self.digital_read(gpio) == HIGH else 0

    def set_value(self, gpio: int, value: int) -> None:
        if self.get_pin_mode(gpio) != OUTPUT:
            raise TypeError(f"GPIO {gpio} must be set as OUTPUT to set a value")
        self.digital_write(gpio, HIGH if value == 1 else LOW)

    def digital_read_all(self) -> List[int]:
        """
        Reads the current direction of the given GPIO
        :return:
        """
        return [self.i2c.read_from(self.address, GPIOA), self.i2c.read_from(self.address, GPIOB)]

    @property
    def values(self) -> int:
        ret = self.i2c.read_from(self.address, GPIOA)
        ret |= self.i2c.read_from(self.address, GPIOB) << 8
        return ret

    @values.setter
    def values(self, value: int) -> None:
        self.i2c.write_to(self.address, GPIOA, value & 0xFF)
        self.i2c.write_to(self.address, GPIOB, (value >> 8) & 0xFF)

    @property
    def io_control(self) -> int:
        return self.i2c.read_from(self.address, IOCONA)

    @io_control.setter
    def io_control(self, value: int) -> None:
        self.i2c.write_to(self.address, IOCONA, value)

    def get_all_interrupt_config(self) -> List:
        """
        Return interrupt comparison criteria
        """
        return [
            self.i2c.read_from(self.address, INTCONA),
            self.i2c.read_from(self.address, INTCONB),
        ]

    def set_all_interrupt_config(self, prev_val: bool = True) -> None:
        """
        Configure interrupt comparison criteria
        :param prev_val: True to compare to previous value, False to compare to def value
        """
        self.i2c.write_to(self.address, INTCONA, 0x00 if prev_val else 0xFF)
        self.i2c.write_to(self.address, INTCONB, 0x00 if prev_val else 0xFF)

    def clear_interrupts(self) -> None:
        with self._lock:
            self._clear_interrupts()

    def _clear_interrupts(self) -> None:
        self.i2c.read_from(self.address, INTCAPA)
        self.i2c.read_from(self.address, INTCAPB)

    def clear_int_a(self) -> None:
        with self._lock:
            self.i2c.read_from(self.address, INTCAPA)

    def clear_int_b(self) -> None:
        with self._lock:
            self.i2c.read_from(self.address, INTCAPB)

    def enable_interrupt(self, gpio) -> None:
        self._enable_interrupt(gpio, True)

    def disable_interrupt(self, gpio) -> None:
        self._enable_interrupt(gpio, False)

    def _enable_interrupt(self, gpio, enabled: bool = True) -> None:
        """
        Enables or disables the interrupt of a given GPIO
        :param gpio: the GPIO where the interrupt needs to be set,
        this needs to be one of GPAn or GPBn constants
        :param enabled: enable or disable the interrupt
        """
        pair = self.get_offset_gpio_tuple([GPINTENA, GPINTENB], gpio)
        self.set_bit_enabled(pair[0], pair[1], enabled)

    def is_interrupt_enabled(self, gpio) -> int:
        pair = self.get_offset_gpio_tuple([GPINTENA, GPINTENB], gpio)
        return self.get_bit_enabled(pair[0], pair[1])

    def enable_interrupts(self) -> None:
        self._set_interrupts(True)

    def disable_interrupts(self) -> None:
        self._set_interrupts(False)

    def _set_interrupts(self, enabled: bool = True) -> None:
        """
        Enables or disables the interrupt of all GPIOs
        :param enabled: enable or disable the interrupt
        """
        self.i2c.write_to(self.address, GPINTENA, 0xFF if enabled else 0x00)
        self.i2c.write_to(self.address, GPINTENB, 0xFF if enabled else 0x00)

    def get_all_interrupts(self) -> List:
        return [self.i2c.read_from(self.address, GPINTENA), self.i2c.read_from(self.address, GPINTENB)]

    @property
    def interrupts_on(self) -> int:
        ret = self.i2c.read_from(self.address, GPINTENA)
        ret |= self.i2c.read_from(self.address, GPINTENB) << 8
        return ret

    @interrupts_on.setter
    def interrupts_on(self, value: int) -> None:
        self.i2c.write_to(self.address, GPINTENA, value & 0xFF)
        self.i2c.write_to(self.address, GPINTENB, (value >> 8) & 0xFF)

    def set_interrupt_mirror(self, enable: bool = True) -> None:
        """
        Enables or disables the interrupt mirroring
        :param enable: enable or disable the interrupt mirroring
        """
        self.set_bit_enabled(IOCONA, MIRROR_BIT, enable)
        self.set_bit_enabled(IOCONB, MIRROR_BIT, enable)

    @property
    def interrupts(self) -> int:
        """
        Reads the interrupt registers.
        :return: an int representing the pin(s) that caused the interrupt
        """
        ret = self.i2c.read_from(self.address, INTFA)
        ret |= self.i2c.read_from(self.address, INTFB) << 8
        return ret

    @property
    def interrupted_pins(self) -> List[int]:
        """
        Reads the interrupt registers.
        :return: an int representing the pin(s) that caused the interrupt
        """
        ret = self.i2c.read_from(self.address, INTFA)
        ret |= self.i2c.read_from(self.address, INTFB) << 8
        return [pin for pin in range(16) if ret & (1 << pin)]

    @property
    def captures(self) -> int:
        """
        Reads the interrupt captured register. It captures the GPIO port value at the time
        the interrupt occurred.
        Note: This method clears interrupts
        :return: an int representing the state of all GPIOs at the time of interrupt
        """
        ret = self.i2c.read_from(self.address, INTCAPA)
        ret |= self.i2c.read_from(self.address, INTCAPB) << 8
        return 0xFF & ~ret

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

    def set_bit_enabled(self, offset: int, gpio: int, enable: bool = True) -> None:
        state_before = self.i2c.read_from(self.address, offset)
        value = (state_before | self.bitmask(gpio)) if enable else (state_before & ~self.bitmask(gpio))
        self.i2c.write_to(self.address, offset, value)

    def get_bit_enabled(self, offset: int, gpio: int) -> int:
        state = self.i2c.read_from(self.address, offset)
        value = state & self.bitmask(gpio)
        return value

    @staticmethod
    def get_offset_gpio_tuple(offsets, gpio):
        if offsets[0] not in ALL_OFFSET or offsets[1] not in ALL_OFFSET:
            raise TypeError("offsets must contain a valid offset address. See description for help")
        if gpio not in ALL_GPIO:
            raise TypeError("pin must be one of GPAn or GPBn. See description for help")

        offset = offsets[0] if gpio < 8 else offsets[1]
        _gpio = gpio % 8
        return offset, _gpio

    @staticmethod
    def bitmask(gpio) -> int:
        return 1 << (gpio % 8)

    # noinspection PyProtectedMember
    def handle_interrupt(self) -> None:
        with self._lock:
            pull_ups = self.pull_ups
            interrupts = self.interrupted_pins
            state = None
            for i in interrupts:
                from ..gpio_handler import DEFAULT_BOUNCE_TIME

                bounce_time = DEFAULT_BOUNCE_TIME
                elapsed_bounce_time = 0
                # for every pin that generated an interrupt, if there is a
                # client associated with this pin, fire event
                if i in self._clients:
                    pull_up = (pull_ups & (1 << i)) != 0
                    client = self._clients[i]
                    if hasattr(client, "bounce_time") and client.bounce_time is not None:
                        bounce_time = client.bounce_time
                    # do the bounce time here; if multiple I2C buttons were pressed
                    # at the same time, this may mean we debounce more than we should,
                    # but we need to make sure each individual button has settled
                    # before we decide if its state has changed
                    if bounce_time > elapsed_bounce_time:
                        bounce_time -= elapsed_bounce_time
                        elapsed_bounce_time += bounce_time
                        time.sleep(bounce_time)
                    if state is None:
                        state = self.captures  # clears interrupts, re-enabling them!!
                    capture_bit = 1 if (state & (1 << i)) != 0 else 0
                    if pull_up is True:
                        active = capture_bit == 1
                    else:
                        active = capture_bit == 0
                    # print(
                    #     f"itp {i} active: {active} pull: {pull_up} cb: {capture_bit} state: {state} "
                    #     f"bounce: {bounce_time} client: {client}"
                    # )
                    # this is part of debouncing; current button state must match
                    # state at interrupt time if we are to consider it a new event
                    if active == client.is_active:
                        client._signal_event(active)
            if state is None:
                # make sure interrupts are always reset, either because
                # we processed them above or here
                self._clear_interrupts()

    def create_interrupt_handler(self, pin, interrupt_pin) -> None:
        if 0 <= pin <= 15:
            with self._lock:
                self._int_pin = interrupt_pin
                self._int_btn = Button(interrupt_pin)
                self._int_btn.when_activated = self.handle_interrupt
                self._clear_interrupts()  # public method is locked, would deadlock
        else:
            raise TypeError("pin must be one of GPAn or GPBn. See description for help")

    def close(self) -> None:
        with self._lock:
            if self._int_btn is not None:
                self._int_btn.close()
                self._int_btn = None
        self._int_pin = self._int_btn = None

    def register_client(self, pin: int, client: I2CDevice):
        if hasattr(client, "pin") and getattr(client, "pin") != pin:
            raise PinInvalidPin(f"{pin} is not a valid pin for {client}")
        self._clients[pin] = client

    def deregister_client(self, client: Device):
        if hasattr(client, "pin"):
            self._clients.pop(getattr(client, "pin"), None)


class Mcp23017Factory:
    _instance = None
    _lock = threading.RLock()

    @classmethod
    def build(
        cls,
        address: int = 0x23,
        pin: int = 0,
        interrupt_pin: int | str = None,
        client: I2CDevice = None,
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
                    if mcp23017.interrupt_pin is not None and mcp23017.interrupt_pin != interrupt_pin:
                        raise PinInvalidPin(
                            f"Interrupt pin {mcp23017.interrupt_pin} already assigned "
                            f"to Mcp23017 at {hex(mcp23017.address)}"
                        )
                    # one more check, has the interrupt machinery been created? If so, we're done
                    if mcp23017.interrupt_pin == interrupt_pin:
                        mcp23017.register_client(pin, client)
                        return mcp23017
                cls._instance._interrupt_pins[interrupt_pin] = mcp23017
                mcp23017.create_interrupt_handler(pin, interrupt_pin)
                mcp23017.register_client(pin, client)
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
                    if mcp23017.interrupt_pin is not None:
                        cls._instance._interrupt_pins.pop(mcp23017.interrupt_pin)
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
