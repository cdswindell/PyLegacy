import math
from enum import Enum, verify, UNIQUE, IntFlag
from typing import Dict, Union


class ByNameMixin(Enum):
    @classmethod
    def by_name(cls, name: str, raise_exception: bool = False) -> Enum | None:
        if name is None:
            raise ValueError(f"None is not a valid {cls.__name__}")
        orig_name = name = name.strip()
        if name in cls.__members__:
            return cls[name]
        # fall back to case-insensitive s
        name = name.lower()
        for k, v in cls.__members__.items():
            if k.lower() == name:
                return v
        else:
            if not raise_exception:
                return None
            if name:
                raise ValueError(f"'{orig_name}' is not a valid {cls.__name__}")
            else:
                raise ValueError(f"None/Empty is not a valid {cls.__name__}")


@verify(UNIQUE)
class SwitchState(ByNameMixin, Enum):
    """
        Switch State
    """
    THROUGH = 1
    OUT = 2
    SET_ADDRESS = 3


@verify(UNIQUE)
class CommandFormat(ByNameMixin, Enum):
    TMCC1 = 1
    TMCC2 = 2


@verify(UNIQUE)
class AuxChoice(ByNameMixin, Enum):
    AUX1 = 1
    AUX2 = 2
    ON = 3  # Cab1 AUX1 button
    OFF = 4  # Cab2 AUX2 button
    NUMERIC = 5
    SET_ADDRESS = 6


@verify(UNIQUE)
class AuxOption(ByNameMixin, Enum):
    ON = 1
    OFF = 2
    OPTION1 = 3
    OPTION2 = 4


"""
    General Constants
"""
DEFAULT_BAUDRATE: int = 9600
DEFAULT_PORT: str = "/dev/ttyUSB0"
DEFAULT_ADDRESS: int = 99

"""
    TMCC1 Protocol Constants
"""
TMCC1_COMMAND_PREFIX: int = 0xFE

TMCC1_HALT_COMMAND: int = 0xFFFF

TMCC1_ROUTE_COMMAND: int = 0xD01F

TMCC1_SWITCH_THROUGH_COMMAND: int = 0x4000
TMCC1_SWITCH_OUT_COMMAND: int = 0x401F
TMCC1_SWITCH_SET_ADDRESS_COMMAND: int = 0x402B

TMCC1_ACC_ON_COMMAND: int = 0x802F
TMCC1_ACC_OFF_COMMAND: int = 0x8020
TMCC1_ACC_NUMERIC_COMMAND: int = 0x8010
TMCC1_ACC_SET_ADDRESS_COMMAND: int = 0x802B

TMCC1_ACC_AUX_1_OFF_COMMAND: int = 0x8008
TMCC1_ACC_AUX_1_OPTION_1_COMMAND: int = 0x8009  # Cab1 Aux1 button
TMCC1_ACC_AUX_1_OPTION_2_COMMAND: int = 0x800A
TMCC1_ACC_AUX_1_ON_COMMAND: int = 0x800B

TMCC1_ACC_AUX_2_OFF_COMMAND: int = 0x800C
TMCC1_ACC_AUX_2_OPTION_1_COMMAND: int = 0x800D  # Cab1 Aux2 button
TMCC1_ACC_AUX_2_OPTION_2_COMMAND: int = 0x800E
TMCC1_ACC_AUX_2_ON_COMMAND: int = 0x800F

# Engine/Train commands
TMCC1_TRAIN_COMMAND_MODIFIER: int = 0xC800  # Logically OR with engine command to make train command
TMCC1_TRAIN_COMMAND_PURIFIER: int = 0x07FF  # Logically AND with engine command to reset engine bits
TMCC1_ENG_ABSOLUTE_SPEED_COMMAND: int = 0x0060  # Absolute speed 0 - 31 encoded in last 5 bits
TMCC1_ENG_RELATIVE_SPEED_COMMAND: int = 0x0040  # Relative Speed -5 - 5 encoded in last 4 bits (offset by 5)
TMCC1_ENG_FORWARD_DIRECTION_COMMAND: int = 0x0000
TMCC1_ENG_TOGGLE_DIRECTION_COMMAND: int = 0x0001
TMCC1_ENG_REVERSE_DIRECTION_COMMAND: int = 0x0003
TMCC1_ENG_BOOST_SPEED_COMMAND: int = 0x0004
TMCC1_ENG_BRAKE_SPEED_COMMAND: int = 0x0007
TMCC1_ENG_OPEN_FRONT_COUPLER_COMMAND: int = 0x0005
TMCC1_ENG_OPEN_REAR_COUPLER_COMMAND: int = 0x0006
TMCC1_ENG_BLOW_HORN_ONE_COMMAND: int = 0x001C
TMCC1_ENG_RING_BELL_COMMAND: int = 0x001D
TMCC1_ENG_LET_OFF_SOUND_COMMAND: int = 0x001E
TMCC1_ENG_BLOW_HORN_TWO_COMMAND: int = 0x001F

TMCC1_ENG_AUX1_OFF_COMMAND: int = 0x0008
TMCC1_ENG_AUX1_OPTION_ONE_COMMAND: int = 0x0009  # Aux 1 button
TMCC1_ENG_AUX1_OPTION_TWO_COMMAND: int = 0x000A
TMCC1_ENG_AUX1_ON_COMMAND: int = 0x000B

TMCC1_ENG_AUX2_OFF_COMMAND: int = 0x000C
TMCC1_ENG_AUX2_OPTION_ONE_COMMAND: int = 0x000D  # Aux 2 button
TMCC1_ENG_AUX2_OPTION_TWO_COMMAND: int = 0x000E
TMCC1_ENG_AUX2_ON_COMMAND: int = 0x000F

TMCC1_ENG_SET_MOMENTUM_LOW_COMMAND: int = 0x0028
TMCC1_ENG_SET_MOMENTUM_MEDIUM_COMMAND: int = 0x0029
TMCC1_ENG_SET_MOMENTUM_HIGH_COMMAND: int = 0x002A

TMCC1_ENG_NUMERIC_COMMAND: int = 0x0010

TMCC1_ENG_SET_ADDRESS_COMMAND: int = 0x002B

"""
    Organize some commands into maps to simplify coding
"""
TMCC1_ACC_AUX_1_OPTIONS_MAP: Dict[AuxOption, int] = {
    AuxOption.ON: TMCC1_ACC_AUX_1_ON_COMMAND,
    AuxOption.OFF: TMCC1_ACC_AUX_1_OFF_COMMAND,
    AuxOption.OPTION1: TMCC1_ACC_AUX_1_OPTION_1_COMMAND,
    AuxOption.OPTION2: TMCC1_ACC_AUX_1_OPTION_2_COMMAND,
}

TMCC1_ACC_AUX_2_OPTIONS_MAP: Dict[AuxOption, int] = {
    AuxOption.ON: TMCC1_ACC_AUX_2_ON_COMMAND,
    AuxOption.OFF: TMCC1_ACC_AUX_2_OFF_COMMAND,
    AuxOption.OPTION1: TMCC1_ACC_AUX_2_OPTION_1_COMMAND,
    AuxOption.OPTION2: TMCC1_ACC_AUX_2_OPTION_2_COMMAND,
}

TMCC1_ACC_CHOICE_MAP: Dict[AuxChoice, Union[int, Dict[AuxOption, int]]] = {
    AuxChoice.AUX1: TMCC1_ACC_AUX_1_OPTIONS_MAP,
    AuxChoice.AUX2: TMCC1_ACC_AUX_2_OPTIONS_MAP,
    AuxChoice.ON: TMCC1_ACC_AUX_1_OPTION_1_COMMAND,
    AuxChoice.OFF: TMCC1_ACC_AUX_2_OPTION_1_COMMAND,
    AuxChoice.SET_ADDRESS: TMCC1_ACC_SET_ADDRESS_COMMAND,
    AuxChoice.NUMERIC: TMCC1_ACC_NUMERIC_COMMAND
}

"""
    Legacy/TMCC2 Protocol Constants
"""
LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX: int = 0xFA
LEGACY_ROUTE_COMMAND: int = 0x00FD

LEGACY_PARAMETER_COMMAND_PREFIX: int = 0xFB

# Engine/Train 2 digit address are first 7 bits of first byte
LEGACY_ENGINE_COMMAND_PREFIX: int = 0xF8
LEGACY_TRAIN_COMMAND_PREFIX: int = 0xF9

RELATIVE_SPEED_MAP = dict(zip(range(-5, 6), range(0, 11)))


@verify(UNIQUE)
class TMCCCommandScope(ByNameMixin, IntFlag):
    ENGINE = LEGACY_ENGINE_COMMAND_PREFIX
    TRAIN = LEGACY_TRAIN_COMMAND_PREFIX
    PARAMETER = LEGACY_PARAMETER_COMMAND_PREFIX
    EXTENDED = LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX


# TMCC2 Commands with Bit 9 = "0"
TMCC2_SET_ABSOLUTE_SPEED_COMMAND: int = 0x0000  # encode speed in last byte (0 - 199)
TMCC2_SET_MOMENTUM_COMMAND: int = 0x00C8  # encode momentum in last 3 bits (0 - 7)
TMCC2_SET_BRAKE_COMMAND: int = 0x00E0  # encode brake level in last 3 bits (0 - 7)
TMCC2_SET_BOOST_COMMAND: int = 0x00E8  # encode boost level in last 3 bits (0 - 7)
TMCC2_SET_TRAIN_BRAKE_COMMAND: int = 0x00F0  # encode train brake in last 3 bits (0 - 7)
TMCC2_STALL_COMMAND: int = 0x00F8
TMCC2_STOP_IMMEDIATE_COMMAND: int = 0x00FB

# TMCC2 Commands with Bit 9 = "1"
TMCC2_FORWARD_DIRECTION_COMMAND: int = 0x0100
TMCC2_TOGGLE_DIRECTION_COMMAND: int = 0x0101
TMCC2_REVERSE_DIRECTION_COMMAND: int = 0x0103

TMCC2_OPEN_FRONT_COUPLER_COMMAND: int = 0x0105
TMCC2_OPEN_REAR_COUPLER_COMMAND: int = 0x0106

TMCC2_RING_BELL_COMMAND: int = 0x011D
TMCC2_BELL_OFF_COMMAND: int = 0x01F4
TMCC2_BELL_ON_COMMAND: int = 0x01F5
TMCC2_BELL_ONE_SHOT_DING_COMMAND: int = 0x01F0  # encode ding in last 2 bits (0 - 3)
TMCC2_BELL_SLIDER_POSITION_COMMAND: int = 0x01B0  # encode position in last 3 bits (2 - 5)

TMCC2_BLOW_HORN_ONE_COMMAND: int = 0x011C
TMCC2_BLOW_HORN_TWO_COMMAND: int = 0x011F
TMCC2_QUILLING_HORN_INTENSITY_COMMAND: int = 0x01E0

TMCC2_SET_MOMENTUM_LOW_COMMAND: int = 0x0128
TMCC2_SET_MOMENTUM_MEDIUM_COMMAND: int = 0x0129
TMCC2_SET_MOMENTUM_HIGH_COMMAND: int = 0x012A

TMCC2_BOOST_SPEED_COMMAND: int = 0x0104
TMCC2_BRAKE_SPEED_COMMAND: int = 0x0107

TMCC2_HALT_COMMAND: int = 0x01AB

TMCC2_NUMERIC_COMMAND: int = 0x0110

TMCC2_ENG_LET_OFF_SOUND_COMMAND: int = 0x01F9
TMCC2_ENG_LET_OFF_LONG_SOUND_COMMAND: int = 0x01FA
TMCC2_WATER_INJECTOR_SOUND_COMMAND: int = 0x01A8
TMCC2_ENG_BRAKE_SQUEAL_SOUND_COMMAND: int = 0x01F6
TMCC2_ENG_AUGER_SOUND_COMMAND: int = 0x01F7
TMCC2_ENG_BRAKE_AIR_RELEASE_SOUND_COMMAND: int = 0x01F8
TMCC2_ENG_REFUELLING_SOUND_COMMAND: int = 0x012C

TMCC2_DIESEL_RUN_LEVEL_SOUND_COMMAND: int = 0x01A0  # run level 0 - 7 encoded in last 3 bits
TMCC2_ENGINE_LABOR_SOUND_COMMAND: int = 0x01C0  # engine labor 0 - 31 encoded in last 5 bytes

TMCC2_START_UP_SEQ_ONE_COMMAND: int = 0x01FB
TMCC2_START_UP_SEQ_TWO_COMMAND: int = 0x01FC
TMCC2_SHUTDOWN_SEQ_ONE_COMMAND: int = 0x01FD
TMCC2_SHUTDOWN_SEQ_TWO_COMMAND: int = 0x01FE

TMCC2_SET_RELATIVE_SPEED_COMMAND: int = 0x0140  # Relative Speed -5 - 5 encoded in last 4 bits (offset by 5)


class EngineOption:
    """
        Marker class for TMCC1EngineOptionEnum and TMCC2EngineOptionEnum, allowing the CLI layer
        to work with them in a command format agnostic manner.
    """
    def __init__(self, command_op: int, d_min: int = 0, d_max: int = 0, d_map: Dict[int, int] = None) -> None:
        self._command_op = command_op
        self._d_min = d_min
        self._d_max = d_max
        self._d_map = d_map
        self._d_bits = 0
        if d_max:
            self._d_bits = math.ceil(math.log2(d_max))
        elif d_map is not None:
            self._d_bits = math.ceil(math.log2(max(d_map.values())))

    def __repr__(self) -> str:
        return f"0x{self.command:04x}: {self.num_data_bits} data bits"

    @property
    def command(self) -> int:
        return self._command_op

    @property
    def num_data_bits(self) -> int:
        return self._d_bits

    def apply_data(self, data: int | None = None) -> int:
        """
            For commands that take parameters, such as engine speed and brake level,
            apply the data bits to the command op bytes to form the complete byte
            set to send to the Lionel LCS SER2.
        """
        if self._d_bits and data is None:
            raise ValueError("Data is required")
        if self._d_bits == 0:
            return self.command
        elif self._d_map:
            if data in self._d_map:
                data = self._d_map[data]
            else:
                raise ValueError(f"Invalid data value: {data} (not in map)")
        elif data < self._d_min or data > self._d_max:
            raise ValueError(f"Invalid data value: {data} (not in range)")
        # sanitize data so we don't set bits we shouldn't
        filtered_data = data & (2 ** self._d_bits - 1)
        if data != filtered_data:
            raise ValueError(f"Invalid data value: {data} (not in range)")
        return data | self._command_op


class EngineOptionEnum(ByNameMixin):
    """
        Marker Interface to allow TMCC1EngineOption and TMCC2EngineOption enums
        to be handled by engine commands
    """

    @classmethod
    def _missing_(cls, value):
        if type(value) is str:
            value = str(value).upper()
            if value in dir(cls):
                return cls[value]
            raise ValueError(f"{value} is not a valid {cls.__name__}")


@verify(UNIQUE)
class TMCC1EngineOption(EngineOptionEnum, Enum):
    ABSOLUTE_SPEED = EngineOption(TMCC1_ENG_ABSOLUTE_SPEED_COMMAND, d_max=31)
    AUX1_OFF = EngineOption(TMCC1_ENG_AUX1_OFF_COMMAND)
    AUX1_ON = EngineOption(TMCC1_ENG_AUX1_ON_COMMAND)
    AUX1_OPTION_ONE = EngineOption(TMCC1_ENG_AUX1_OPTION_ONE_COMMAND)
    AUX1_OPTION_TWO = EngineOption(TMCC1_ENG_AUX1_OPTION_TWO_COMMAND)
    AUX2_OFF = EngineOption(TMCC1_ENG_AUX2_OFF_COMMAND)
    AUX2_ON = EngineOption(TMCC1_ENG_AUX2_ON_COMMAND)
    AUX2_OPTION_ONE = EngineOption(TMCC1_ENG_AUX2_OPTION_ONE_COMMAND)
    AUX2_OPTION_TWO = EngineOption(TMCC1_ENG_AUX2_OPTION_TWO_COMMAND)
    BLOW_HORN_ONE = EngineOption(TMCC1_ENG_BLOW_HORN_ONE_COMMAND)
    BLOW_HORN_TWO = EngineOption(TMCC1_ENG_BLOW_HORN_TWO_COMMAND)
    BOOST_SPEED = EngineOption(TMCC1_ENG_BOOST_SPEED_COMMAND)
    BRAKE_SPEED = EngineOption(TMCC1_ENG_BRAKE_SPEED_COMMAND)
    FORWARD_DIRECTION = EngineOption(TMCC1_ENG_FORWARD_DIRECTION_COMMAND)
    FRONT_COUPLER = EngineOption(TMCC1_ENG_OPEN_FRONT_COUPLER_COMMAND)
    LET_OFF = EngineOption(TMCC1_ENG_LET_OFF_SOUND_COMMAND)
    MOMENTUM_HIGH = EngineOption(TMCC1_ENG_SET_MOMENTUM_HIGH_COMMAND)
    MOMENTUM_LOW = EngineOption(TMCC1_ENG_SET_MOMENTUM_LOW_COMMAND)
    MOMENTUM_MEDIUM = EngineOption(TMCC1_ENG_SET_MOMENTUM_MEDIUM_COMMAND)
    NUMERIC = EngineOption(TMCC1_ENG_NUMERIC_COMMAND, d_max=10)
    OPEN_FRONT_COUPLER = EngineOption(TMCC1_ENG_OPEN_FRONT_COUPLER_COMMAND)
    OPEN_REAR_COUPLER = EngineOption(TMCC1_ENG_OPEN_REAR_COUPLER_COMMAND)
    REAR_COUPLER = EngineOption(TMCC1_ENG_OPEN_REAR_COUPLER_COMMAND)
    RELATIVE_SPEED = EngineOption(TMCC1_ENG_RELATIVE_SPEED_COMMAND, d_map=RELATIVE_SPEED_MAP)
    REVERSE_DIRECTION = EngineOption(TMCC1_ENG_REVERSE_DIRECTION_COMMAND)
    RING_BELL = EngineOption(TMCC1_ENG_RING_BELL_COMMAND)
    SET_ADDRESS = EngineOption(TMCC1_ENG_SET_ADDRESS_COMMAND)
    TOGGLE_DIRECTION = EngineOption(TMCC1_ENG_TOGGLE_DIRECTION_COMMAND)


@verify(UNIQUE)
class TMCC2EngineOption(EngineOptionEnum, Enum):
    ABSOLUTE_SPEED = EngineOption(TMCC2_SET_ABSOLUTE_SPEED_COMMAND, d_max=199)
    AUGER = EngineOption(TMCC2_ENG_AUGER_SOUND_COMMAND)
    BELL_OFF = EngineOption(TMCC2_BELL_OFF_COMMAND)
    BELL_ON = EngineOption(TMCC2_BELL_ON_COMMAND)
    BELL_ONE_SHOT_DING = EngineOption(TMCC2_BELL_ONE_SHOT_DING_COMMAND, d_max=3)
    BELL_SLIDER_POSITION = EngineOption(TMCC2_BELL_SLIDER_POSITION_COMMAND, d_min=2, d_max=5)
    BLOW_HORN_ONE = EngineOption(TMCC2_BLOW_HORN_ONE_COMMAND)
    BLOW_HORN_TWO = EngineOption(TMCC2_BLOW_HORN_TWO_COMMAND)
    BOOST_LEVEL = EngineOption(TMCC2_SET_BOOST_COMMAND, d_max=7)
    BOOST_SPEED = EngineOption(TMCC2_BOOST_SPEED_COMMAND)
    BRAKE_AIR_RELEASE = EngineOption(TMCC2_ENG_BRAKE_AIR_RELEASE_SOUND_COMMAND)
    BRAKE_LEVEL = EngineOption(TMCC2_SET_BRAKE_COMMAND, d_max=7)
    BRAKE_SPEED = EngineOption(TMCC2_BRAKE_SPEED_COMMAND)
    BRAKE_SQUEAL = EngineOption(TMCC2_ENG_BRAKE_SQUEAL_SOUND_COMMAND)
    FORWARD_DIRECTION = EngineOption(TMCC2_FORWARD_DIRECTION_COMMAND)
    FRONT_COUPLER = EngineOption(TMCC2_OPEN_FRONT_COUPLER_COMMAND)
    LET_OFF = EngineOption(TMCC2_ENG_LET_OFF_SOUND_COMMAND)
    LET_OFF_LONG = EngineOption(TMCC2_ENG_LET_OFF_LONG_SOUND_COMMAND)
    MOMENTUM = EngineOption(TMCC2_SET_MOMENTUM_COMMAND, d_max=7)
    MOMENTUM_HIGH = EngineOption(TMCC2_SET_MOMENTUM_HIGH_COMMAND)
    MOMENTUM_LOW = EngineOption(TMCC2_SET_MOMENTUM_LOW_COMMAND)
    MOMENTUM_MEDIUM = EngineOption(TMCC2_SET_MOMENTUM_MEDIUM_COMMAND)
    NUMERIC = EngineOption(TMCC2_NUMERIC_COMMAND, d_max=10)
    QUILLING_HORN_INTENSITY = EngineOption(TMCC2_QUILLING_HORN_INTENSITY_COMMAND, d_max=16)
    REAR_COUPLER = EngineOption(TMCC2_OPEN_REAR_COUPLER_COMMAND)
    REFUELLING = EngineOption(TMCC2_ENG_REFUELLING_SOUND_COMMAND)
    RELATIVE_SPEED = EngineOption(TMCC2_SET_RELATIVE_SPEED_COMMAND, d_map=RELATIVE_SPEED_MAP)
    REVERSE_DIRECTION = EngineOption(TMCC2_REVERSE_DIRECTION_COMMAND)
    RING_BELL = EngineOption(TMCC2_RING_BELL_COMMAND)
    SET_STALL = EngineOption(TMCC2_STALL_COMMAND)
    SHUTDOWN_DELAYED = EngineOption(TMCC2_SHUTDOWN_SEQ_ONE_COMMAND)
    SHUTDOWN_IMMEDIATE = EngineOption(TMCC2_SHUTDOWN_SEQ_TWO_COMMAND)
    START_UP_DELAYED = EngineOption(TMCC2_START_UP_SEQ_ONE_COMMAND)
    START_UP_IMMEDIATE = EngineOption(TMCC2_START_UP_SEQ_TWO_COMMAND)
    STOP_IMMEDIATE = EngineOption(TMCC2_STOP_IMMEDIATE_COMMAND)
    SYSTEM_HALT = EngineOption(TMCC2_HALT_COMMAND)
    TOGGLE_DIRECTION = EngineOption(TMCC2_TOGGLE_DIRECTION_COMMAND)
    TRAIN_BRAKE = EngineOption(TMCC2_SET_TRAIN_BRAKE_COMMAND, d_max=7)
