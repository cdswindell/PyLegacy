import abc
import math
from abc import ABC
from enum import Enum, verify, UNIQUE, IntEnum
from typing import Dict, Any, Self

"""
    General Constants
"""
DEFAULT_BAUDRATE: int = 9600
DEFAULT_PORT: str = "/dev/ttyUSB0"
DEFAULT_ADDRESS: int = 99

DEFAULT_QUEUE_SIZE: int = 2**11  # 2,048 entries

DEFAULT_THROTTLE_DELAY: int = 50  # milliseconds


class Mixins(Enum):
    """
        Common mixins we want all PyLegacy enums to support
    """
    @classmethod
    def by_name(cls, name: str, raise_exception: bool = False) -> Self | None:
        if name is None:
            if raise_exception:
                raise ValueError(f"None is not a valid {cls.__name__}")
            else:
                return None
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

    @classmethod
    def by_value(cls, value: Any, raise_exception: bool = False) -> Self | None:
        for _, member in cls.__members__.items():
            if member.value == value:
                return member
        if raise_exception:
            raise ValueError(f"'{value}' is not a valid {cls.__name__}")
        else:
            return None

    @classmethod
    def _missing_(cls, value) -> Self:
        if type(value) is str:
            value = str(value).upper()
            if value in dir(cls):
                return cls[value]
            raise ValueError(f"{value} is not a valid {cls.__name__}")


@verify(UNIQUE)
class CommandSyntax(Mixins, Enum):
    TMCC1 = 1
    TMCC2 = 2


@verify(UNIQUE)
class CommandScope(Mixins, Enum):
    ENGINE = 1
    TRAIN = 2
    SWITCH = 3
    ROUTE = 4
    ACC = 5
    SYSTEM = 6


class CommandPrefix(Mixins, IntEnum):
    """
        Marker interface for Command Prefix enums
    """

    @property
    def prefix(self) -> Self:
        return self

    @property
    def as_int(self) -> int:
        return self.value

    @property
    def as_bytes(self) -> bytes:
        return self.as_int.to_bytes(1, byteorder='big')


class CommandDef(ABC):
    __metaclass__ = abc.ABCMeta
    """
        Marker class for TMCC1 and TMCC2 Command Options, allowing the CLI layer
        to work with them in a command format agnostic manner.
    """
    def __init__(self,
                 command_bits: int,
                 d_min: int = 0,
                 d_max: int = 0,
                 d_map: Dict[int, int] = None) -> None:
        self._command_bits = command_bits
        self._d_min = d_min
        self._d_max = d_max
        self._d_map = d_map
        self._d_bits = 0
        if d_max:
            self._d_bits = math.ceil(math.log2(d_max))
        elif d_map is not None:
            self._d_bits = math.ceil(math.log2(max(d_map.values())))

    def __repr__(self) -> str:
        return f"{self}0x{self.bits:04x}: {self.num_data_bits} data bits"

    @property
    def bits(self) -> int:
        return self._command_bits

    @property
    def num_data_bits(self) -> int:
        return self._d_bits

    @property
    def data_min(self) -> int:
        return self._d_min

    @property
    def data_max(self) -> int:
        return self._d_max

    @property
    def data_map(self) -> Dict[int, int] | None:
        return self._d_map

    @property
    def syntax(self) -> CommandSyntax:
        if isinstance(self, TMCC1CommandDef):
            return CommandSyntax.TMCC1
        elif isinstance(self, TMCC2CommandDef):
            return CommandSyntax.TMCC2
        else:
            raise TypeError(f"Invalid command syntax: {self}")

    @property
    def identifier(self) -> int | None:
        """
            Only relevant for TMCC1-style commands
        """
        return None

    @property
    @abc.abstractmethod
    def first_byte(self) -> bytes | None:
        return None

    @property
    @abc.abstractmethod
    def scope(self) -> CommandScope | None:
        return None


class CommandDefEnum(Mixins, Enum):
    """
        Marker Interface to allow TMCC1EngineOption and TMCC2EngineCommandDef enums
        to be handled by engine commands
    """
    @property
    def command_def(self) -> CommandDef:
        return self.value

    @property
    def scope(self) -> CommandScope:
        return self.command_def.scope


"""
    TMCC1 Constants
"""


class TMCC1Enum(CommandDefEnum):
    """
        Marker Interface for all TMCC1 enums
    """
    pass


"""
    TMCC1 Protocol Constants
"""
TMCC1_COMMAND_PREFIX: int = 0xFE


@verify(UNIQUE)
class TMCC1CommandIdentifier(CommandPrefix):
    ENGINE = 0x00
    TRAIN = 0xC0
    SWITCH = 0x40
    ACC = 0x80
    ROUTE = 0xD0
    HALT = 0xFF


TMCC1_IDENT_TO_SCOPE_MAP: Dict[TMCC1CommandIdentifier, CommandScope] = {
    TMCC1CommandIdentifier.ENGINE: CommandScope.ENGINE,
    TMCC1CommandIdentifier.TRAIN: CommandScope.TRAIN,
    TMCC1CommandIdentifier.SWITCH: CommandScope.SWITCH,
    TMCC1CommandIdentifier.ACC: CommandScope.ACC,
    TMCC1CommandIdentifier.ROUTE: CommandScope.ROUTE,
    TMCC1CommandIdentifier.HALT: CommandScope.SYSTEM,
}

TMCC1_HALT_COMMAND: int = 0xFFFF


class TMCC1CommandDef(CommandDef):
    def __init__(self,
                 command_bits: int,
                 command_ident: TMCC1CommandIdentifier = TMCC1CommandIdentifier.ENGINE,
                 d_min: int = 0,
                 d_max: int = 0,
                 d_map: Dict[int, int] = None) -> None:
        super().__init__(command_bits, d_min=d_min, d_max=d_max, d_map=d_map)
        self._command_ident = command_ident

    @property
    def identifier(self) -> TMCC1CommandIdentifier:
        return self._command_ident

    @property
    def first_byte(self) -> bytes:
        return TMCC1_COMMAND_PREFIX.to_bytes(1, byteorder='big')

    @property
    def scope(self) -> CommandScope:
        return TMCC1_IDENT_TO_SCOPE_MAP[self.identifier]


@verify(UNIQUE)
class TMCC1HaltOption(TMCC1Enum):
    HALT = TMCC1CommandDef(TMCC1_HALT_COMMAND, TMCC1CommandIdentifier.HALT)


TMCC1_ROUTE_COMMAND: int = 0xD01F


@verify(UNIQUE)
class TMCC1RouteOption(TMCC1Enum):
    ROUTE = TMCC1CommandDef(TMCC1_ROUTE_COMMAND, TMCC1CommandIdentifier.ROUTE)


TMCC1_SWITCH_THROUGH_COMMAND: int = 0x4000
TMCC1_SWITCH_OUT_COMMAND: int = 0x401F
TMCC1_SWITCH_SET_ADDRESS_COMMAND: int = 0x402B


@verify(UNIQUE)
class TMCC1SwitchState(TMCC1Enum):
    """
        Switch State
    """
    THROUGH = TMCC1CommandDef(TMCC1_SWITCH_THROUGH_COMMAND, TMCC1CommandIdentifier.SWITCH)
    OUT = TMCC1CommandDef(TMCC1_SWITCH_OUT_COMMAND, TMCC1CommandIdentifier.SWITCH)
    SET_ADDRESS = TMCC1CommandDef(TMCC1_SWITCH_SET_ADDRESS_COMMAND, TMCC1CommandIdentifier.SWITCH)


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


@verify(UNIQUE)
class TMCC1AuxOption(TMCC1Enum):
    SET_ADDRESS = TMCC1CommandDef(TMCC1_ACC_SET_ADDRESS_COMMAND, TMCC1CommandIdentifier.ACC)
    NUMERIC = TMCC1CommandDef(TMCC1_ACC_NUMERIC_COMMAND, TMCC1CommandIdentifier.ACC, d_max=9)
    AUX1_OFF = TMCC1CommandDef(TMCC1_ACC_AUX_1_OFF_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX1_ON = TMCC1CommandDef(TMCC1_ACC_AUX_1_ON_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX1_OPTION_ONE = TMCC1CommandDef(TMCC1_ACC_AUX_1_OPTION_1_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX1_OPTION_TWO = TMCC1CommandDef(TMCC1_ACC_AUX_1_OPTION_2_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX2_OFF = TMCC1CommandDef(TMCC1_ACC_AUX_2_OFF_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX2_ON = TMCC1CommandDef(TMCC1_ACC_AUX_2_ON_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX2_OPTION_ONE = TMCC1CommandDef(TMCC1_ACC_AUX_2_OPTION_1_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX2_OPTION_TWO = TMCC1CommandDef(TMCC1_ACC_AUX_2_OPTION_2_COMMAND, TMCC1CommandIdentifier.ACC)


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

TMCC1_ENG_VOLUME_UP_COMMAND: int = 0x0011
TMCC1_ENG_SOUND_ONE_COMMAND: int = 0x0012
TMCC1_ENG_RPM_UP_COMMAND: int = 0x0013
TMCC1_ENG_VOLUME_DOWN_COMMAND: int = 0x0014
TMCC1_ENG_SHUTDOWN_COMMAND: int = 0x0015
TMCC1_ENG_RPM_DOWN_COMMAND: int = 0x0016
TMCC1_ENG_SOUND_TWO_COMMAND: int = 0x0017
TMCC1_ENG_FUNC_MINUS_COMMAND: int = 0x0018
TMCC1_ENG_FUNC_PLUS_COMMAND: int = 0x0019

TMCC1_ENG_SET_ADDRESS_COMMAND: int = 0x002B

TMCC1_ROLL_SPEED: int = 1  # express speeds as simple integers
TMCC1_RESTRICTED_SPEED: int = 5
TMCC1_SLOW_SPEED: int = 10
TMCC1_MEDIUM_SPEED: int = 15
TMCC1_LIMITED_SPEED: int = 20
TMCC1_NORMAL_SPEED: int = 25
TMCC1_HIGHBALL_SPEED: int = 27

TMCC1_SPEED_MAP: dict[str, int] = {
    'ROLL': TMCC1_ROLL_SPEED,
    'RO': TMCC1_ROLL_SPEED,
    'RESTRICTED': TMCC1_RESTRICTED_SPEED,
    'RE': TMCC1_RESTRICTED_SPEED,
    'SLOW': TMCC1_SLOW_SPEED,
    'SL': TMCC1_SLOW_SPEED,
    'MEDIUM': TMCC1_MEDIUM_SPEED,
    'ME': TMCC1_MEDIUM_SPEED,
    'LIMITED': TMCC1_LIMITED_SPEED,
    'LI': TMCC1_LIMITED_SPEED,
    'NORMAL': TMCC1_NORMAL_SPEED,
    'NO': TMCC1_NORMAL_SPEED,
    'HIGH': TMCC1_HIGHBALL_SPEED,
    'HIGHBALL': TMCC1_HIGHBALL_SPEED,
    'HI': TMCC1_HIGHBALL_SPEED,
}

"""
    Relative speed is specified with values ranging from -5 to 5 that are 
    mapped to values 0 - 10
"""
RELATIVE_SPEED_MAP = dict(zip(range(-5, 6), range(0, 11)))


@verify(UNIQUE)
class TMCC1EngineOption(TMCC1Enum):
    ABSOLUTE_SPEED = TMCC1CommandDef(TMCC1_ENG_ABSOLUTE_SPEED_COMMAND, d_max=31)
    AUX1_OFF = TMCC1CommandDef(TMCC1_ENG_AUX1_OFF_COMMAND)
    AUX1_ON = TMCC1CommandDef(TMCC1_ENG_AUX1_ON_COMMAND)
    AUX1_OPTION_ONE = TMCC1CommandDef(TMCC1_ENG_AUX1_OPTION_ONE_COMMAND)
    AUX1_OPTION_TWO = TMCC1CommandDef(TMCC1_ENG_AUX1_OPTION_TWO_COMMAND)
    AUX2_OFF = TMCC1CommandDef(TMCC1_ENG_AUX2_OFF_COMMAND)
    AUX2_ON = TMCC1CommandDef(TMCC1_ENG_AUX2_ON_COMMAND)
    AUX2_OPTION_ONE = TMCC1CommandDef(TMCC1_ENG_AUX2_OPTION_ONE_COMMAND)
    AUX2_OPTION_TWO = TMCC1CommandDef(TMCC1_ENG_AUX2_OPTION_TWO_COMMAND)
    BLOW_HORN_ONE = TMCC1CommandDef(TMCC1_ENG_BLOW_HORN_ONE_COMMAND)
    BLOW_HORN_TWO = TMCC1CommandDef(TMCC1_ENG_BLOW_HORN_TWO_COMMAND)
    BOOST_SPEED = TMCC1CommandDef(TMCC1_ENG_BOOST_SPEED_COMMAND)
    BRAKE_SPEED = TMCC1CommandDef(TMCC1_ENG_BRAKE_SPEED_COMMAND)
    FORWARD_DIRECTION = TMCC1CommandDef(TMCC1_ENG_FORWARD_DIRECTION_COMMAND)
    FRONT_COUPLER = TMCC1CommandDef(TMCC1_ENG_OPEN_FRONT_COUPLER_COMMAND)
    FUNC_MINUS = TMCC1CommandDef(TMCC1_ENG_FUNC_MINUS_COMMAND)
    FUNC_PLUS = TMCC1CommandDef(TMCC1_ENG_FUNC_PLUS_COMMAND)
    LET_OFF = TMCC1CommandDef(TMCC1_ENG_LET_OFF_SOUND_COMMAND)
    MOMENTUM_HIGH = TMCC1CommandDef(TMCC1_ENG_SET_MOMENTUM_HIGH_COMMAND)
    MOMENTUM_LOW = TMCC1CommandDef(TMCC1_ENG_SET_MOMENTUM_LOW_COMMAND)
    MOMENTUM_MEDIUM = TMCC1CommandDef(TMCC1_ENG_SET_MOMENTUM_MEDIUM_COMMAND)
    NUMERIC = TMCC1CommandDef(TMCC1_ENG_NUMERIC_COMMAND, d_max=9)
    OPEN_FRONT_COUPLER = TMCC1CommandDef(TMCC1_ENG_OPEN_FRONT_COUPLER_COMMAND)
    OPEN_REAR_COUPLER = TMCC1CommandDef(TMCC1_ENG_OPEN_REAR_COUPLER_COMMAND)
    REAR_COUPLER = TMCC1CommandDef(TMCC1_ENG_OPEN_REAR_COUPLER_COMMAND)
    RELATIVE_SPEED = TMCC1CommandDef(TMCC1_ENG_RELATIVE_SPEED_COMMAND, d_map=RELATIVE_SPEED_MAP)
    REVERSE_DIRECTION = TMCC1CommandDef(TMCC1_ENG_REVERSE_DIRECTION_COMMAND)
    RING_BELL = TMCC1CommandDef(TMCC1_ENG_RING_BELL_COMMAND)
    RPM_DOWN = TMCC1CommandDef(TMCC1_ENG_RPM_DOWN_COMMAND)
    RPM_UP = TMCC1CommandDef(TMCC1_ENG_RPM_UP_COMMAND)
    SET_ADDRESS = TMCC1CommandDef(TMCC1_ENG_SET_ADDRESS_COMMAND)
    SHUTDOWN_DELAYED = TMCC1CommandDef(TMCC1_ENG_SHUTDOWN_COMMAND)
    SOUND_ONE = TMCC1CommandDef(TMCC1_ENG_SOUND_ONE_COMMAND)
    SOUND_TWO = TMCC1CommandDef(TMCC1_ENG_SOUND_TWO_COMMAND)
    TOGGLE_DIRECTION = TMCC1CommandDef(TMCC1_ENG_TOGGLE_DIRECTION_COMMAND)
    VOLUME_DOWN = TMCC1CommandDef(TMCC1_ENG_VOLUME_DOWN_COMMAND)
    VOLUME_UP = TMCC1CommandDef(TMCC1_ENG_VOLUME_UP_COMMAND)


"""
    TMCC2 constants
"""

"""
    Legacy/TMCC2 Protocol/first_byte Constants
"""
# All Legacy/TMCC2 commands begin with one of the following 1 byte sequences
# Engine/Train/Parameter 2 digit address are first 7 bits of first byte
LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX: int = 0xFA
LEGACY_PARAMETER_COMMAND_PREFIX: int = 0xFB
LEGACY_ENGINE_COMMAND_PREFIX: int = 0xF8
LEGACY_TRAIN_COMMAND_PREFIX: int = 0xF9


class TMCC2Enum(CommandDefEnum):
    """
        Marker Interface for all TMCC2 enums
    """
    pass


@verify(UNIQUE)
class TMCC2CommandPrefix(CommandPrefix):
    ENGINE = LEGACY_ENGINE_COMMAND_PREFIX
    TRAIN = LEGACY_TRAIN_COMMAND_PREFIX
    ROUTE = LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX  # probably used for other things
    PARAMETER = LEGACY_PARAMETER_COMMAND_PREFIX


TMCC2_FIRST_BYTE_TO_SCOPE_MAP = {
    TMCC2CommandPrefix.ENGINE: CommandScope.ENGINE,
    TMCC2CommandPrefix.TRAIN: CommandScope.TRAIN,
    TMCC2CommandPrefix.ROUTE: CommandScope.ROUTE,
}


class TMCC2CommandDef(CommandDef):
    def __init__(self,
                 command_bits: int,
                 first_byte: TMCC2CommandPrefix = TMCC2CommandPrefix.ENGINE,
                 d_min: int = 0,
                 d_max: int = 0,
                 d_map: Dict[int, int] = None) -> None:
        super().__init__(command_bits,  d_min=d_min, d_max=d_max, d_map=d_map)
        self._first_byte = first_byte

    @property
    def first_byte(self) -> bytes:
        return self._first_byte.as_bytes

    @property
    def scope(self) -> CommandScope:
        return TMCC2_FIRST_BYTE_TO_SCOPE_MAP[self._first_byte]


# The TMCC2 route command is an undocumented "extended block command" (0xFA)
LEGACY_ROUTE_COMMAND: int = 0x00FD


@verify(UNIQUE)
class TMCC2RouteCommandDef(TMCC2Enum):
    ROUTE = TMCC2CommandDef(LEGACY_ROUTE_COMMAND, first_byte=TMCC2CommandPrefix.ROUTE)


# TMCC2 Commands with Bit 9 = "0"
TMCC2_SET_ABSOLUTE_SPEED_COMMAND: int = 0x0000  # encode speed in last byte (0 - 199)
TMCC2_SET_MOMENTUM_COMMAND: int = 0x00C8  # encode momentum in last 3 bits (0 - 7)
TMCC2_SET_BRAKE_LEVEL_COMMAND: int = 0x00E0  # encode brake level in last 3 bits (0 - 7)
TMCC2_SET_BOOST_LEVEL_COMMAND: int = 0x00E8  # encode boost level in last 3 bits (0 - 7)
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
TMCC2_ENG_REFUELLING_SOUND_COMMAND: int = 0x012D

TMCC2_DIESEL_RUN_LEVEL_SOUND_COMMAND: int = 0x01A0  # run level 0 - 7 encoded in last 3 bits

TMCC2_ENGINE_LABOR_COMMAND: int = 0x01C0  # engine labor 0 - 31 encoded in last 5 bytes

TMCC2_START_UP_SEQ_ONE_COMMAND: int = 0x01FB
TMCC2_START_UP_SEQ_TWO_COMMAND: int = 0x01FC
TMCC2_SHUTDOWN_SEQ_ONE_COMMAND: int = 0x01FD
TMCC2_SHUTDOWN_SEQ_TWO_COMMAND: int = 0x01FE

TMCC2_AUX1_OFF_COMMAND: int = 0x0108
TMCC2_AUX1_OPTION_ONE_COMMAND: int = 0x0109  # Cab 1 Aux1 button
TMCC2_AUX1_OPTION_TWO_COMMAND: int = 0x010A
TMCC2_AUX1_ON_COMMAND: int = 0x010B

TMCC2_AUX2_OFF_COMMAND: int = 0x010C
TMCC2_AUX2_OPTION_ONE_COMMAND: int = 0x010D  # Cab 1 Aux2 button
TMCC2_AUX2_OPTION_TWO_COMMAND: int = 0x010E
TMCC2_AUX2_ON_COMMAND: int = 0x010F

TMCC2_SET_RELATIVE_SPEED_COMMAND: int = 0x0140  # Relative Speed -5 - 5 encoded in last 4 bits (offset by 5)

TMCC2_ROLL_SPEED: int = 1  # express speeds as simple integers
TMCC2_RESTRICTED_SPEED: int = 24
TMCC2_SLOW_SPEED: int = 59
TMCC2_MEDIUM_SPEED: int = 92
TMCC2_LIMITED_SPEED: int = 118
TMCC2_NORMAL_SPEED: int = 145
TMCC2_HIGHBALL_SPEED: int = 199

TMCC2_SPEED_MAP = dict(ROLL=TMCC2_ROLL_SPEED, RO=TMCC2_ROLL_SPEED,
                       RESTRICTED=TMCC2_RESTRICTED_SPEED, RE=TMCC2_RESTRICTED_SPEED,
                       SLOW=TMCC2_SLOW_SPEED, SL=TMCC2_SLOW_SPEED,
                       MEDIUM=TMCC2_MEDIUM_SPEED, ME=TMCC2_MEDIUM_SPEED,
                       LIMITED=TMCC2_LIMITED_SPEED, LI=TMCC2_LIMITED_SPEED,
                       NORMAL=TMCC2_NORMAL_SPEED, NO=TMCC2_NORMAL_SPEED,
                       HIGH=TMCC2_HIGHBALL_SPEED, HIGHBALL=TMCC2_HIGHBALL_SPEED, HI=TMCC2_HIGHBALL_SPEED)


@verify(UNIQUE)
class TMCC2EngineCommandDef(TMCC2Enum):
    ABSOLUTE_SPEED = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND, d_max=199)
    AUGER = TMCC2CommandDef(TMCC2_ENG_AUGER_SOUND_COMMAND)
    AUX1_OFF = TMCC2CommandDef(TMCC2_AUX1_OFF_COMMAND)
    AUX1_ON = TMCC2CommandDef(TMCC2_AUX1_ON_COMMAND)
    AUX1_OPTION_ONE = TMCC2CommandDef(TMCC2_AUX1_OPTION_ONE_COMMAND)
    AUX1_OPTION_TWO = TMCC2CommandDef(TMCC2_AUX1_OPTION_TWO_COMMAND)
    AUX2_OFF = TMCC2CommandDef(TMCC2_AUX2_OFF_COMMAND)
    AUX2_ON = TMCC2CommandDef(TMCC2_AUX2_ON_COMMAND)
    AUX2_OPTION_ONE = TMCC2CommandDef(TMCC2_AUX2_OPTION_ONE_COMMAND)
    AUX2_OPTION_TWO = TMCC2CommandDef(TMCC2_AUX2_OPTION_TWO_COMMAND)
    BELL_OFF = TMCC2CommandDef(TMCC2_BELL_OFF_COMMAND)
    BELL_ON = TMCC2CommandDef(TMCC2_BELL_ON_COMMAND)
    BELL_ONE_SHOT_DING = TMCC2CommandDef(TMCC2_BELL_ONE_SHOT_DING_COMMAND, d_max=3)
    BELL_SLIDER_POSITION = TMCC2CommandDef(TMCC2_BELL_SLIDER_POSITION_COMMAND, d_min=2, d_max=5)
    BLOW_HORN_ONE = TMCC2CommandDef(TMCC2_BLOW_HORN_ONE_COMMAND)
    BLOW_HORN_TWO = TMCC2CommandDef(TMCC2_BLOW_HORN_TWO_COMMAND)
    BOOST_LEVEL = TMCC2CommandDef(TMCC2_SET_BOOST_LEVEL_COMMAND, d_max=7)
    BOOST_SPEED = TMCC2CommandDef(TMCC2_BOOST_SPEED_COMMAND)
    BRAKE_AIR_RELEASE = TMCC2CommandDef(TMCC2_ENG_BRAKE_AIR_RELEASE_SOUND_COMMAND)
    BRAKE_LEVEL = TMCC2CommandDef(TMCC2_SET_BRAKE_LEVEL_COMMAND, d_max=7)
    BRAKE_SPEED = TMCC2CommandDef(TMCC2_BRAKE_SPEED_COMMAND)
    BRAKE_SQUEAL = TMCC2CommandDef(TMCC2_ENG_BRAKE_SQUEAL_SOUND_COMMAND)
    DIESEL_LEVEL = TMCC2CommandDef(TMCC2_DIESEL_RUN_LEVEL_SOUND_COMMAND, d_max=7)
    ENGINE_LABOR = TMCC2CommandDef(TMCC2_ENGINE_LABOR_COMMAND, d_max=31)
    FORWARD_DIRECTION = TMCC2CommandDef(TMCC2_FORWARD_DIRECTION_COMMAND)
    FRONT_COUPLER = TMCC2CommandDef(TMCC2_OPEN_FRONT_COUPLER_COMMAND)
    LET_OFF = TMCC2CommandDef(TMCC2_ENG_LET_OFF_SOUND_COMMAND)
    LET_OFF_LONG = TMCC2CommandDef(TMCC2_ENG_LET_OFF_LONG_SOUND_COMMAND)
    MOMENTUM = TMCC2CommandDef(TMCC2_SET_MOMENTUM_COMMAND, d_max=7)
    MOMENTUM_HIGH = TMCC2CommandDef(TMCC2_SET_MOMENTUM_HIGH_COMMAND)
    MOMENTUM_LOW = TMCC2CommandDef(TMCC2_SET_MOMENTUM_LOW_COMMAND)
    MOMENTUM_MEDIUM = TMCC2CommandDef(TMCC2_SET_MOMENTUM_MEDIUM_COMMAND)
    NUMERIC = TMCC2CommandDef(TMCC2_NUMERIC_COMMAND, d_max=9)
    QUILLING_HORN_INTENSITY = TMCC2CommandDef(TMCC2_QUILLING_HORN_INTENSITY_COMMAND, d_max=16)
    REAR_COUPLER = TMCC2CommandDef(TMCC2_OPEN_REAR_COUPLER_COMMAND)
    REFUELLING = TMCC2CommandDef(TMCC2_ENG_REFUELLING_SOUND_COMMAND)
    RELATIVE_SPEED = TMCC2CommandDef(TMCC2_SET_RELATIVE_SPEED_COMMAND, d_map=RELATIVE_SPEED_MAP)
    REVERSE_DIRECTION = TMCC2CommandDef(TMCC2_REVERSE_DIRECTION_COMMAND)
    RING_BELL = TMCC2CommandDef(TMCC2_RING_BELL_COMMAND)
    SET_ADDRESS = TMCC2CommandDef(TMCC1_ENG_SET_ADDRESS_COMMAND)
    SHUTDOWN_DELAYED = TMCC2CommandDef(TMCC2_SHUTDOWN_SEQ_ONE_COMMAND)
    SHUTDOWN_IMMEDIATE = TMCC2CommandDef(TMCC2_SHUTDOWN_SEQ_TWO_COMMAND)
    SPEED_HIGH_BALL = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_HIGHBALL_SPEED)
    SPEED_LIMITED = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_LIMITED_SPEED)
    SPEED_MEDIUM = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_MEDIUM_SPEED)
    SPEED_NORMAL = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_NORMAL_SPEED)
    SPEED_RESTRICTED = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_RESTRICTED_SPEED)
    SPEED_ROLL = TMCC2CommandDef(TMCC2_ROLL_SPEED | TMCC2_ROLL_SPEED)
    SPEED_SLOW = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_SLOW_SPEED)
    STALL = TMCC2CommandDef(TMCC2_STALL_COMMAND)
    START_UP_DELAYED = TMCC2CommandDef(TMCC2_START_UP_SEQ_ONE_COMMAND)
    START_UP_IMMEDIATE = TMCC2CommandDef(TMCC2_START_UP_SEQ_TWO_COMMAND)
    STOP_IMMEDIATE = TMCC2CommandDef(TMCC2_STOP_IMMEDIATE_COMMAND)
    SYSTEM_HALT = TMCC2CommandDef(TMCC2_HALT_COMMAND)
    TOGGLE_DIRECTION = TMCC2CommandDef(TMCC2_TOGGLE_DIRECTION_COMMAND)
    TRAIN_BRAKE = TMCC2CommandDef(TMCC2_SET_TRAIN_BRAKE_COMMAND, d_max=7)
    WATER_INJECTOR = TMCC2CommandDef(TMCC2_WATER_INJECTOR_SOUND_COMMAND)


"""
    Legacy/TMCC2 Multi-byte Command sequences
"""
TMCC2_PARAMETER_INDEX_PREFIX: int = 0x70

"""
    Word #1 - Parameter indexes
"""
TMCC2_PARAMETER_ASSIGNMENT_PARAMETER_INDEX: int = 0x01
TMCC2_RAIL_SOUNDS_DIALOG_TRIGGERS_PARAMETER_INDEX: int = 0x02
TMCC2_RAIL_SOUNDS_EFFECTS_TRIGGERS_PARAMETER_INDEX: int = 0x04
TMCC2_RAIL_SOUNDS_MASKING_CONTROL_PARAMETER_INDEX: int = 0x06
TMCC2_EFFECTS_CONTROLS_PARAMETER_INDEX: int = 0x0C
TMCC2_LIGHTING_CONTROLS_PARAMETER_INDEX: int = 0x0D
TMCC2_VARIABLE_LENGTH_COMMAND_PARAMETER_INDEX: int = 0x0F


@verify(UNIQUE)
class TMCC2ParameterIndex(Mixins, IntEnum):
    PARAMETER_ASSIGNMENT = TMCC2_PARAMETER_ASSIGNMENT_PARAMETER_INDEX
    DIALOG_CONTROLS = TMCC2_RAIL_SOUNDS_DIALOG_TRIGGERS_PARAMETER_INDEX
    EFFECTS_TRIGGERS = TMCC2_RAIL_SOUNDS_EFFECTS_TRIGGERS_PARAMETER_INDEX
    MASKING_CONTROL = TMCC2_RAIL_SOUNDS_MASKING_CONTROL_PARAMETER_INDEX
    EFFECTS_CONTROLS = TMCC2_EFFECTS_CONTROLS_PARAMETER_INDEX
    LIGHTING_CONTROLS = TMCC2_LIGHTING_CONTROLS_PARAMETER_INDEX
    VARIABLE_LENGTH_COMMAND = TMCC2_VARIABLE_LENGTH_COMMAND_PARAMETER_INDEX


class TMCC2ParameterDataEnum(Mixins, IntEnum):
    """
        Marker interface for all Parameter Data enums
    """
    pass


"""
    Word #2 -Dialog trigger controls (index 0x2)
"""
TMCC2_DIALOGS_CONTROL_SHUTDOWN: int = 0x01
TMCC2_DIALOGS_CONTROL_SCENE_TWO: int = 0x02
TMCC2_DIALOG_CONTROL_SCENE_SEVEN: int = 0x03
TMCC2_DIALOG_CONTROL_SCENE_FIVE: int = 0x04
TMCC2_DIALOG_CONTROL_SHORT_HORN: int = 0x05
TMCC2_DIALOG_CONTROL_CONVENTIONAL_SHUTDOWN: int = 0x01


@verify(UNIQUE)
class TMCC2DialogControl(TMCC2ParameterDataEnum):
    CONVENTIONAL_SHUTDOWN = TMCC2_DIALOGS_CONTROL_SHUTDOWN


"""
    Word #2 - Effects controls (index 0xC)
"""
TMCC2_EFFECTS_CONTROL_SMOKE_OFF: int = 0x00
TMCC2_EFFECTS_CONTROL_SMOKE_LOW: int = 0x01
TMCC2_EFFECTS_CONTROL_SMOKE_MEDIUM: int = 0x02
TMCC2_EFFECTS_CONTROL_SMOKE_HIGH: int = 0x03

TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_UP: int = 0x10
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_DOWN: int = 0x11
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_UP: int = 0x12
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_DOWN: int = 0x13


TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_OPEN: int = 0x20
TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_CLOSE: int = 0x21
TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_OPEN: int = 0x22
TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_CLOSE: int = 0x23

TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_ONE_ON: int = 0x30
TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_ONE_OFF: int = 0x31
TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_TWO_ON: int = 0x32
TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_TWO_OFF: int = 0x33
TMCC2_EFFECTS_CONTROL_STOCK_CAR_LOAD: int = 0x34
TMCC2_EFFECTS_CONTROL_STOCK_CAR_UNLOAD: int = 0x35
TMCC2_EFFECTS_CONTROL_STOCK_CAR_FRED_ON: int = 0x36
TMCC2_EFFECTS_CONTROL_STOCK_CAR_FRED_OFF: int = 0x37
TMCC2_EFFECTS_CONTROL_STOCK_CAR_FLAT_WHEEL_ON: int = 0x38
TMCC2_EFFECTS_CONTROL_STOCK_CAR_FLAT_WHEEL_OFF: int = 0x39
TMCC2_EFFECTS_CONTROL_STOCK_CAR_GAME_ON: int = 0x3A
TMCC2_EFFECTS_CONTROL_STOCK_CAR_GAME_OFF: int = 0x3B


@verify(UNIQUE)
class TMCC2EffectsControl(TMCC2ParameterDataEnum):
    PANTO_FRONT_DOWN = TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_DOWN
    PANTO_FRONT_UP = TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_UP
    PANTO_REAR_DOWN = TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_DOWN
    PANTO_REAR_UP = TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_UP
    SMOKE_HIGH = TMCC2_EFFECTS_CONTROL_SMOKE_HIGH
    SMOKE_LOW = TMCC2_EFFECTS_CONTROL_SMOKE_LOW
    SMOKE_MEDIUM = TMCC2_EFFECTS_CONTROL_SMOKE_MEDIUM
    SMOKE_OFF = TMCC2_EFFECTS_CONTROL_SMOKE_OFF
    STOCK_FRED_OFF = TMCC2_EFFECTS_CONTROL_STOCK_CAR_FRED_OFF
    STOCK_FRED_ON = TMCC2_EFFECTS_CONTROL_STOCK_CAR_FRED_ON
    STOCK_GAME_OFF = TMCC2_EFFECTS_CONTROL_STOCK_CAR_GAME_OFF
    STOCK_GAME_ON = TMCC2_EFFECTS_CONTROL_STOCK_CAR_GAME_ON
    STOCK_LOAD = TMCC2_EFFECTS_CONTROL_STOCK_CAR_LOAD
    STOCK_OPTION_ONE_OFF = TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_ONE_OFF
    STOCK_OPTION_ONE_ON = TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_ONE_ON
    STOCK_OPTION_ONE_TWO = TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_TWO_OFF
    STOCK_OPTION_TWO_ON = TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_TWO_ON
    STOCK_UNLOAD = TMCC2_EFFECTS_CONTROL_STOCK_CAR_UNLOAD
    STOCK_WHEEL_OFF = TMCC2_EFFECTS_CONTROL_STOCK_CAR_FLAT_WHEEL_OFF
    STOCK_WHEEL_ON = TMCC2_EFFECTS_CONTROL_STOCK_CAR_FLAT_WHEEL_ON
    SUBWAY_LEFT_DOOR_CLOSE = TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_CLOSE
    SUBWAY_LEFT_DOOR_OPEN = TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_OPEN
    SUBWAY_RIGHT_DOOR_CLOSE = TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_CLOSE
    SUBWAY_RIGHT_DOOR_OPEN = TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_OPEN


"""
    Word #2 - Lighting controls (index 0xD)
"""
TMCC2_LIGHTING_CONTROL_CAB_LIGHT_AUTO: int = 0xF2
TMCC2_LIGHTING_CONTROL_CAB_LIGHT_OFF: int = 0xF0
TMCC2_LIGHTING_CONTROL_CAB_LIGHT_ON: int = 0xF1

TMCC2_LIGHTING_CONTROL_CAR_LIGHT_AUTO: int = 0xFA
TMCC2_LIGHTING_CONTROL_CAR_LIGHT_OFF: int = 0xF8
TMCC2_LIGHTING_CONTROL_CAR_LIGHT_ON: int = 0xF9

TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_OFF: int = 0xC0
TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_OFF_PULSE_ON_WITH_HORN: int = 0xC1
TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_ON: int = 0xC3
TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_ON_PULSE_OFF_WITH_HORN: int = 0xC2

TMCC2_LIGHTING_CONTROL_DOGHOUSE_LIGHT_OFF: int = 0xA1
TMCC2_LIGHTING_CONTROL_DOGHOUSE_LIGHT_ON: int = 0xA0

TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_AUTO: int = 0xD2
TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_OFF: int = 0xD0
TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_ON: int = 0xD1

TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_AUTO: int = 0xB2
TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_OFF: int = 0xB0
TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_ON: int = 0xB1

TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_OFF: int = 0xC8
TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_ON: int = 0xC9

TMCC2_LIGHTING_CONTROL_MARS_LIGHT_OFF: int = 0xE8
TMCC2_LIGHTING_CONTROL_MARS_LIGHT_ON: int = 0xE9

TMCC2_LIGHTING_CONTROL_RULE_17_AUTO: int = 0xF6
TMCC2_LIGHTING_CONTROL_RULE_17_OFF: int = 0xF4
TMCC2_LIGHTING_CONTROL_RULE_17_ON: int = 0xF5

TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_OFF: int = 0xE0
TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_ON_DOUBLE_FLASH: int = 0xE2
TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_ON_SINGLE_FLASH: int = 0xE1

TMCC2_LIGHTING_CONTROL_TENDER_MARKER_LIGHT_OFF: int = 0xCC
TMCC2_LIGHTING_CONTROL_TENDER_MARKER_LIGHT_ON: int = 0xCD


@verify(UNIQUE)
class TMCC2LightingControl(TMCC2ParameterDataEnum):
    CAB_AUTO = TMCC2_LIGHTING_CONTROL_CAB_LIGHT_AUTO
    CAB_OFF = TMCC2_LIGHTING_CONTROL_CAB_LIGHT_OFF
    CAB_ON = TMCC2_LIGHTING_CONTROL_CAB_LIGHT_ON
    CAR_AUTO = TMCC2_LIGHTING_CONTROL_CAR_LIGHT_AUTO
    CAR_OFF = TMCC2_LIGHTING_CONTROL_CAR_LIGHT_OFF
    CAR_ON = TMCC2_LIGHTING_CONTROL_CAR_LIGHT_ON
    DITCH_OFF = TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_OFF
    DITCH_OFF_PULSE_ON_WITH_HORN = TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_OFF_PULSE_ON_WITH_HORN
    DITCH_ON = TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_ON
    DITCH_ON_PULSE_OFF_WITH_HORN = TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_ON_PULSE_OFF_WITH_HORN
    DOGHOUSE_OFF = TMCC2_LIGHTING_CONTROL_DOGHOUSE_LIGHT_OFF
    DOGHOUSE_ON = TMCC2_LIGHTING_CONTROL_DOGHOUSE_LIGHT_ON
    GROUND_AUTO = TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_AUTO
    GROUND_OFF = TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_OFF
    GROUND_ON = TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_ON
    HAZARD_AUTO = TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_AUTO
    HAZARD_OFF = TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_OFF
    HAZARD_ON = TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_ON
    LOCO_MARKER_OFF = TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_OFF
    LOCO_MARKER_ON = TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_ON
    MARS_OFF = TMCC2_LIGHTING_CONTROL_MARS_LIGHT_OFF
    MARS_ON = TMCC2_LIGHTING_CONTROL_MARS_LIGHT_ON
    RULE_17_AUTO = TMCC2_LIGHTING_CONTROL_RULE_17_AUTO
    RULE_17_OFF = TMCC2_LIGHTING_CONTROL_RULE_17_OFF
    RULE_17_ON = TMCC2_LIGHTING_CONTROL_RULE_17_ON
    STROBE_LIGHT_OFF = TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_OFF
    STROBE_LIGHT_ON = TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_ON_SINGLE_FLASH
    STROBE_LIGHT_ON_DOUBLE = TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_ON_DOUBLE_FLASH
    TENDER_MARKER_OFF = TMCC2_LIGHTING_CONTROL_TENDER_MARKER_LIGHT_OFF
    TENDER_MARKER_ON = TMCC2_LIGHTING_CONTROL_TENDER_MARKER_LIGHT_ON
