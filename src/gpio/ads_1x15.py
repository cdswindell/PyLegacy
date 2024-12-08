from abc import ABC, ABCMeta

from smbus2 import SMBus
import time

# ADS1x15 default i2c address
I2C_address = 0x48


class Ads1x15(ABC):
    """
    General ADS1x15 family ADC class
    """

    __metaclass__ = ABCMeta

    # ADS1x15 register address
    CONVERSION_REG = 0x00
    CONFIG_REG = 0x01
    LO_THRESH_REG = 0x02
    HI_THRESH_REG = 0x03

    # Input multiplexer configuration
    INPUT_DIFF_0_1 = 0
    INPUT_DIFF_0_3 = 1
    INPUT_DIFF_1_3 = 2
    INPUT_DIFF_2_3 = 3
    INPUT_SINGLE_0 = 4
    INPUT_SINGLE_1 = 5
    INPUT_SINGLE_2 = 6
    INPUT_SINGLE_3 = 7

    # Programmable gain amplifier configuration
    PGA_6_144V = 0
    PGA_4_096V = 1
    PGA_2_048V = 2
    PGA_1_024V = 4
    PGA_0_512V = 8
    PGA_0_256V = 16

    # Device operating mode configuration
    MODE_CONTINUOUS = 0
    MODE_SINGLE = 1
    INVALID_MODE = -1

    # Data rate configuration
    DR_ADS101X_128 = 0
    DR_ADS101X_250 = 1
    DR_ADS101X_490 = 2
    DR_ADS101X_920 = 3
    DR_ADS101X_1600 = 4
    DR_ADS101X_2400 = 5
    DR_ADS101X_3300 = 6
    DR_ADS111X_8 = 0
    DR_ADS111X_16 = 1
    DR_ADS111X_32 = 2
    DR_ADS111X_64 = 3
    DR_ADS111X_128 = 4
    DR_ADS111X_250 = 5
    DR_ADS111X_475 = 6
    DR_ADS111X_860 = 7

    # Comparator configuration
    COMP_MODE_TRADITIONAL = 0
    COMP_MODE_WINDOW = 1
    COMP_POL_ACTIV_LOW = 0
    COMP_POL_ACTIV_HIGH = 1
    COMP_LATCH = 0
    COMP_NON_LATCH = 1
    COMP_QUE_1_CONV = 0
    COMP_QUE_2_CONV = 1
    COMP_QUE_4_CONV = 2
    COMP_QUE_NONE = 3

    # Default config register
    _config = 0x8583

    # Default conversion delay
    # _conversionDelay = 8

    # Maximum input port
    # _maxPorts = 4

    # Default conversion lengths
    # _adc_bits = 16

    def __init__(
        self,
        channel: int,
        bus_id: int,
        address: int,
        conversion_delay: int,
        ports: int,
        bits: int,
    ) -> None:
        """
        Constructor with SMBus ID and I2C address input
        """
        self._i2c = SMBus(bus_id)
        self._address = address
        self._conversion_delay = conversion_delay
        self._ports = ports
        self._bits = bits
        # Store initial config register to config property
        self._config = self.read_register(self.CONFIG_REG)
        # set channel
        self.request_adc(channel)

    @property
    def i2c(self) -> SMBus:
        return self._i2c

    @property
    def address(self) -> int:
        return self._address

    @property
    def conversion_delay(self) -> int:
        return self._conversion_delay

    @property
    def ports(self) -> int:
        return self._ports

    @property
    def bits(self) -> int:
        return self._bits

    def read_register(self, address: int) -> int:
        """
        Read 16-bit integer raw_value from an address pointer register
        """
        register_value = self._i2c.read_i2c_block_data(self._address, address, 2)
        return (register_value[0] << 8) + register_value[1]

    def write_register(self, address: int, value: int) -> None:
        """
        Write 16-bit integer to an address pointer register
        """
        register_value = [(value >> 8) & 0xFF, value & 0xFF]
        self._i2c.write_i2c_block_data(self._address, address, register_value)

    @property
    def channel(self):
        """
        Get input multiplexer configuration
        """
        return (self._config & 0x7000) >> 12

    @channel.setter
    def channel(self, inp: int) -> None:
        """
        Set input multiplexer configuration
        """
        # Filter input argument
        if inp < 0 or inp > 7:
            input_register = 0x0000
        else:
            input_register = inp << 12
        # Masking input argument bits (bit 12-14) to config register
        self._config = (self._config & 0x8FFF) | input_register
        self.write_register(self.CONFIG_REG, self._config)

    @property
    def gain(self):
        """Get programmable gain amplifier configuration"""
        gain_register = self._config & 0x0E00
        if gain_register == 0x0200:
            return self.PGA_4_096V
        elif gain_register == 0x0400:
            return self.PGA_2_048V
        elif gain_register == 0x0600:
            return self.PGA_1_024V
        elif gain_register == 0x0800:
            return self.PGA_0_512V
        elif gain_register == 0x0A00:
            return self.PGA_0_256V
        else:
            return 0x0000

    @gain.setter
    def gain(self, gain: int):
        """
        Set programmable gain amplifier configuration
        """
        # Filter gain argument
        if gain == self.PGA_4_096V:
            gain_register = 0x0200
        elif gain == self.PGA_2_048V:
            gain_register = 0x0400
        elif gain == self.PGA_1_024V:
            gain_register = 0x0600
        elif gain == self.PGA_0_512V:
            gain_register = 0x0800
        elif gain == self.PGA_0_256V:
            gain_register = 0x0A00
        else:
            gain_register = 0x0000
        # Masking gain argument bits (bit 9-11) to config register
        self._config = (self._config & 0xF1FF) | gain_register
        self.write_register(self.CONFIG_REG, self._config)

    @property
    def mode(self):
        """
        Get device operating mode configuration
        """
        return (self._config & 0x0100) >> 8

    @mode.setter
    def mode(self, mode: int):
        """
        Set device operating mode configuration
        """
        # Filter mode argument
        if mode == 0:
            mode_register = 0x0000
        else:
            mode_register = 0x0100
        # Masking mode argument bit (bit 8) to config register
        self._config = (self._config & 0xFEFF) | mode_register
        self.write_register(self.CONFIG_REG, self._config)

    @property
    def data_rate(self):
        """Get data rate configuration"""
        return (self._config & 0x00E0) >> 5

    @data_rate.setter
    def data_rate(self, data_rate: int):
        """
        Set data rate configuration
        """
        # Filter dataRate argument
        if data_rate < 0 or data_rate > 7:
            data_rate_register = 0x0080
        else:
            data_rate_register = data_rate << 5
        # Masking dataRate argument bits (bit 5-7) to config register
        self._config = (self._config & 0xFF1F) | data_rate_register
        self.write_register(self.CONFIG_REG, self._config)

    @property
    def comparator_mode(self):
        """
        Get comparator mode configuration
        """
        return (self._config & 0x0010) >> 4

    @comparator_mode.setter
    def comparator_mode(self, comparator_mode: int):
        """
        Set comparator mode configuration
        """
        # Filter comparatorMode argument
        if comparator_mode == 1:
            comparator_mode_register = 0x0010
        else:
            comparator_mode_register = 0x0000
        # Masking comparatorMode argument bit (bit 4) to config register
        self._config = (self._config & 0xFFEF) | comparator_mode_register
        self.write_register(self.CONFIG_REG, self._config)

    @property
    def comparator_polarity(self):
        """
        Get comparator polarity configuration
        """
        return (self._config & 0x0008) >> 3

    @comparator_polarity.setter
    def comparator_polarity(self, comparator_polarity: int):
        """
        Set comparator polarity configuration
        """
        # Filter comparatorPolarity argument
        if comparator_polarity == 1:
            comparator_polarity_register = 0x0008
        else:
            comparator_polarity_register = 0x0000
        # Masking comparatorPolarity argument bit (bit 3) to config register
        self._config = (self._config & 0xFFF7) | comparator_polarity_register
        self.write_register(self.CONFIG_REG, self._config)

    @property
    def comparator_latch(self):
        """
        Get comparator polarity configuration
        """
        return (self._config & 0x0004) >> 2

    @comparator_latch.setter
    def comparator_latch(self, comparator_latch: int):
        """Set comparator polarity configuration"""
        # Filter comparatorLatch argument
        if comparator_latch == 1:
            comparator_latch_register = 0x0004
        else:
            comparator_latch_register = 0x0000
        # Masking comparatorPolarity argument bit (bit 2) to config register
        self._config = (self._config & 0xFFFB) | comparator_latch_register
        self.write_register(self.CONFIG_REG, self._config)

    @property
    def comparator_queue(self):
        """Get comparator queue configuration"""
        return self._config & 0x0003

    @comparator_queue.setter
    def comparator_queue(self, comparator_queue: int):
        """Set comparator queue configuration"""
        # Filter comparatorQueue argument
        if comparator_queue < 0 or comparator_queue > 3:
            comparator_queue_register = 0x0002
        else:
            comparator_queue_register = comparator_queue
        # Masking comparatorQueue argument bits (bit 0-1) to config register
        self._config = (self._config & 0xFFFC) | comparator_queue_register
        self.write_register(self.CONFIG_REG, self._config)

    def get_comparator_threshold_low(self):
        """Get voltage comparator low threshold"""
        threshold = self.read_register(self.LO_THRESH_REG)
        if threshold >= 32768:
            threshold = threshold - 65536
        return threshold

    def set_comparator_threshold_low(self, threshold: float):
        """Set low threshold for voltage comparator"""
        self.write_register(self.LO_THRESH_REG, round(threshold))

    def get_comparator_threshold_high(self):
        """Get voltage comparator high threshold"""
        threshold = self.read_register(self.HI_THRESH_REG)
        if threshold >= 32768:
            threshold = threshold - 65536
        return threshold

    def set_comparator_threshold_high(self, threshold: float):
        """Set high threshold for voltage comparator"""
        self.write_register(self.HI_THRESH_REG, round(threshold))

    @property
    def is_ready(self):
        """
        Check if device currently not performing conversion
        """
        value = self.read_register(self.CONFIG_REG)
        return bool(value & 0x8000)

    @property
    def is_busy(self):
        """
        Check if device currently performing conversion
        """
        return not self.is_ready

    def request_adc(self, pin: int):
        """Request single-shot conversion of a pin to ground"""
        if pin >= self._ports or pin < 0:
            return
        self._request_adc(pin + 4)

    def _request_adc(self, channel: int):
        """Private method for starting a single-shot conversion"""
        self.channel = channel
        # Set single-shot conversion start (bit 15)
        if self._config & 0x0100:
            self.write_register(self.CONFIG_REG, self._config | 0x8000)

    def _get_adc(self) -> int:
        """Get ADC raw_value with current configuration"""
        t = time.time()
        is_continuous = not (self._config & 0x0100)
        # Wait conversion process finish or reach conversion time for continuous mode
        while not self.is_ready:
            if ((time.time() - t) * 1000) > self._conversion_delay and is_continuous:
                break
        return self.raw_value

    @property
    def raw_value(self) -> int:
        """Get ADC raw_value"""
        value = self.read_register(self.CONVERSION_REG)
        # Shift bit based on ADC bits and change 2'complement negative raw_value to negative integer
        value = value >> (16 - self._bits)
        if value >= (2 ** (self._bits - 1)):
            value = value - (2**self._bits)
        return value

    def read_adc(self, pin: int):
        """Get ADC raw_value of a pin"""
        if pin >= self._ports or pin < 0:
            return 0
        self.request_adc(pin)
        return self._get_adc()

    def request_adc_differential_0_1(self):
        """Request single-shot conversion between pin 0 and pin 1"""
        self._request_adc(0)

    def read_adc_differential_0_1(self):
        """Get ADC raw_value between pin 0 and pin 1"""
        self.request_adc_differential_0_1()
        return self._get_adc()

    @property
    def max_voltage(self) -> float:
        """Get maximum voltage conversion range"""
        if self._config & 0x0E00 == 0x0000:
            return 6.144
        elif self._config & 0x0E00 == 0x0200:
            return 4.096
        elif self._config & 0x0E00 == 0x0400:
            return 2.048
        elif self._config & 0x0E00 == 0x0600:
            return 1.024
        elif self._config & 0x0E00 == 0x0800:
            return 0.512
        else:
            return 0.256

    @property
    def value(self) -> float:
        return self.to_voltage(self.raw_value)

    @property
    def voltage(self) -> float:
        return self.to_voltage(self.raw_value)

    def to_voltage(self, value: int = 1) -> float:
        """
        Transform an ADC raw_value to nominal voltage
        """
        volts = self.max_voltage * value
        return volts / ((2 ** (self._bits - 1)) - 1)


class ADS1013(Ads1x15):
    def __init__(self, channel: int = 0, bus_id: int = 1, address: int = I2C_address):
        """Initialize ADS1013 with SMBus ID and I2C address configuration"""
        super().__init__(channel, bus_id, address, 2, 1, 12)


class ADS1014(Ads1x15):
    def __init__(self, channel: int = 0, bus_id: int = 1, address: int = I2C_address):
        """Initialize ADS1014 with SMBus ID and I2C address configuration"""
        super().__init__(channel, bus_id, address, 2, 1, 12)


class ADS1015(Ads1x15):
    def __init__(self, channel: int = 0, bus_id: int = 1, address: int = I2C_address):
        """Initialize ADS1015 with SMBus ID and I2C address configuration"""
        super().__init__(channel, bus_id, address, 2, 4, 12)

    def request_adc_differential_0_3(self):
        """Request single-shot conversion between pin 0 and pin 3"""
        self._request_adc(1)

    def read_adc_differential_0_3(self):
        """Get ADC raw_value between pin 0 and pin 3"""
        self.request_adc_differential_0_3()
        return self._get_adc()

    def request_adc_differential_1_3(self):
        """Request single-shot conversion between pin 1 and pin 3"""
        self._request_adc(2)

    def read_adc_differential_1_3(self):
        """Get ADC raw_value between pin 1 and pin 3"""
        self.request_adc_differential_1_3()
        return self._get_adc()

    def request_adc_differential_2_3(self):
        """Request single-shot conversion between pin 2 and pin 3"""
        self._request_adc(3)

    def read_adc_differential_2_3(self):
        """Get ADC raw_value between pin 2 and pin 3"""
        self.request_adc_differential_2_3()
        return self._get_adc()


class ADS1113(Ads1x15):
    def __init__(self, channel: int = 0, bus_id: int = 1, address: int = I2C_address):
        """Initialize ADS1113 with SMBus ID and I2C address configuration"""
        super().__init__(channel, bus_id, address, 8, 1, 16)


class ADS1114(Ads1x15):
    def __init__(self, channel: int = 0, bus_id: int = 1, address: int = I2C_address):
        """Initialize ADS1114 with SMBus ID and I2C address configuration"""
        super().__init__(channel, bus_id, address, 8, 1, 16)


class ADS1115(Ads1x15):
    def __init__(
        self,
        channel: int = 0,
        bus_id: int = 1,
        address: int = I2C_address,
        gain: int = Ads1x15.PGA_6_144V,
        data_rate: int = Ads1x15.DR_ADS111X_128,
    ):
        """Initialize ADS1115 with SMBus ID and I2C address configuration"""
        super().__init__(channel, bus_id, address, 8, 4, 16)
        self.gain = gain
        self.mode = self.MODE_CONTINUOUS
        self.data_rate = data_rate

    def request_adc_differential_0_3(self):
        """
        Request single-shot conversion between pin 0 and pin 3
        """
        self._request_adc(1)

    def read_adc_differential_0_3(self):
        """
        Get ADC raw_value between pin 0 and pin 3
        """
        self.request_adc_differential_0_3()
        return self._get_adc()

    def request_adc_differential_1_3(self):
        """
        Request single-shot conversion between pin 1 and pin 3
        """
        self._request_adc(2)

    def read_adc_differential_1_3(self):
        """
        Get ADC raw_value between pin 1 and pin 3
        """
        self.request_adc_differential_1_3()
        return self._get_adc()

    def request_adc_differential_2_3(self):
        """
        Request single-shot conversion between pin 2 and pin 3
        """
        self._request_adc(3)

    def read_adc_differential_2_3(self):
        """
        Get ADC raw_value between pin 2 and pin 3
        """
        self.request_adc_differential_2_3()
        return self._get_adc()
