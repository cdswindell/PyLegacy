from __future__ import annotations

import abc
from enum import unique
from typing import Dict, Tuple

from range_key_dict import RangeKeyDict

from ..command_def import CommandDef, CommandDefEnum
from ..constants import (
    DEFAULT_ADDRESS,
    DEFAULT_ENGINE_LABOR,
    RELATIVE_SPEED_MAP,
    CommandPrefix,
    CommandScope,
    CommandSyntax,
    OfficialRRSpeeds,
)

LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX: int = 0xFA
LEGACY_MULTIBYTE_COMMAND_PREFIX: int = 0xFB
LEGACY_ENGINE_COMMAND_PREFIX: int = 0xF8
LEGACY_TRAIN_COMMAND_PREFIX: int = 0xF9

"""
    TMCC2 constants
"""


class TMCC2Enum(CommandDefEnum):
    """
    Marker Interface for all TMCC2 enums
    """

    pass


"""
    Legacy/TMCC2 Protocol/first_byte Constants
"""


# All Legacy/TMCC2 commands begin with one of the following 1 byte sequences
# Engine/Train/Parameter 2 digit address is first 7 bits of first byte


@unique
class TMCC2CommandPrefix(CommandPrefix):
    ENGINE = LEGACY_ENGINE_COMMAND_PREFIX
    TRAIN = LEGACY_TRAIN_COMMAND_PREFIX
    ROUTE = LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX  # probably used for other things
    PARAMETER = LEGACY_MULTIBYTE_COMMAND_PREFIX


TMCC2_FIRST_BYTE_TO_SCOPE_MAP = {
    TMCC2CommandPrefix.ENGINE: CommandScope.ENGINE,
    TMCC2CommandPrefix.TRAIN: CommandScope.TRAIN,
    TMCC2CommandPrefix.ROUTE: CommandScope.ROUTE,
}

TMCC2_SCOPE_TO_FIRST_BYTE_MAP = {s: p for p, s in TMCC2_FIRST_BYTE_TO_SCOPE_MAP.items()}


class TMCC2CommandDef(CommandDef):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        command_bits: int,
        scope: CommandScope = CommandScope.ENGINE,
        is_addressable: bool = True,
        d_min: int = 0,
        d_max: int = 0,
        d_map: Dict[int, int] = None,
        alias: str = None,
        data: int = None,
        filtered=False,
        interval: int = None,
        d4_broadcast: bool = False,  # if True, command is broadcast from Base 3 for D4 engines
    ) -> None:
        super().__init__(
            command_bits,
            is_addressable,
            d_min=d_min,
            d_max=d_max,
            d_map=d_map,
            alias=alias,
            data=data,
            filtered=filtered,
            interval=interval,
        )
        self._scope = scope
        self._d4_broadcast = d4_broadcast

    @property
    def first_byte(self) -> bytes:
        return TMCC2_SCOPE_TO_FIRST_BYTE_MAP[self.scope].to_bytes(1, byteorder="big")

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def syntax(self) -> CommandSyntax:
        return CommandSyntax.LEGACY

    @property
    def address_mask(self) -> int:
        return 0xFFFF & ~((2**self.num_address_bits - 1) << 9)

    @property
    def is_d4_broadcast(self) -> bool:
        return self._d4_broadcast

    def address_from_bytes(self, byte_data: bytes) -> int:
        if self.is_addressable:
            value = int.from_bytes(byte_data[0:2], byteorder="big")
            address = (0xFFFF & (~self.address_mask & value)) >> 9
            if len(byte_data) <= 2 and 1 <= address <= 99:
                return address
            elif len(byte_data) <= 6 and address == 0:
                add_str = ""
                for i in range(2, 6):
                    add_str += chr(byte_data[i])
                return int(add_str)
            raise AttributeError(f"Cannot decode address from bytes: {byte_data.hex()}")
        else:
            return DEFAULT_ADDRESS

    @property
    def alias(self) -> TMCC2EngineCommandEnum | Tuple[TMCC2EngineCommandEnum, int] | None:
        if self._alias is not None:
            if isinstance(self._alias, str):
                alias = TMCC2EngineCommandEnum.by_name(self._alias, raise_exception=True)
            else:
                raise ValueError(f"Cannot classify command alias: {self._alias} ({type(self._alias)})")
            if self._data is None:
                return alias
            else:
                return alias, self._data
        return None


TMCC2_HALT_COMMAND: int = 0x01AB


@unique
class TMCC2HaltCommandEnum(TMCC2Enum):
    HALT = TMCC2CommandDef(TMCC2_HALT_COMMAND, CommandScope.ENGINE, alias="SYSTEM_HALT", data=99)


# The TMCC2 route command is an undocumented "extended block command" (0xFA)
LEGACY_ROUTE_COMMAND: int = 0x00FD


@unique
class TMCC2RouteCommandEnum(TMCC2Enum):
    FIRE = TMCC2CommandDef(LEGACY_ROUTE_COMMAND, scope=CommandScope.ROUTE)


TMCC2_AUX1_OFF_COMMAND: int = 0x0108
TMCC2_AUX1_ON_COMMAND: int = 0x010B
TMCC2_AUX1_OPTION_ONE_COMMAND: int = 0x0109  # Cab 1 Aux1 button
TMCC2_AUX1_OPTION_TWO_COMMAND: int = 0x010A
TMCC2_AUX2_OFF_COMMAND: int = 0x010C
TMCC2_AUX2_ON_COMMAND: int = 0x010F
TMCC2_AUX2_OPTION_ONE_COMMAND: int = 0x010D  # Cab 1 Aux2 button
TMCC2_AUX2_OPTION_TWO_COMMAND: int = 0x010E
TMCC2_AUX3_OPTION_ONE_COMMAND: int = 0x013B
TMCC2_BELL_OFF_COMMAND: int = 0x01F4
TMCC2_BELL_ONE_SHOT_DING_COMMAND: int = 0x01F0  # encode ding in last 2 bits (0 - 3)
TMCC2_BELL_ON_COMMAND: int = 0x01F5
TMCC2_BELL_SLIDER_POSITION_COMMAND: int = 0x01B0  # encode position in last 3 bits (2 - 5)
TMCC2_BLOW_HORN_ONE_COMMAND: int = 0x011C
TMCC2_BLOW_HORN_TWO_COMMAND: int = 0x011F
TMCC2_BOOST_SPEED_COMMAND: int = 0x0104
TMCC2_BRAKE_SPEED_COMMAND: int = 0x0107
TMCC2_DIESEL_RPM_SOUND_COMMAND: int = 0x01A0  # run level 0-7 encoded in the last 3 bits
TMCC2_ENGINE_LABOR_COMMAND: int = 0x01C0  # engine labor 0-31 encoded in the last 5 bits
TMCC2_ENG_AUGER_SOUND_COMMAND: int = 0x01F7
TMCC2_ENG_BRAKE_AIR_RELEASE_SOUND_COMMAND: int = 0x01F8
TMCC2_ENG_BRAKE_SQUEAL_SOUND_COMMAND: int = 0x01F6
TMCC2_ENG_CYLINDER_HISS_SOUND_COMMAND: int = 0x0152
TMCC2_ENG_LET_OFF_LONG_SOUND_COMMAND: int = 0x01FA
TMCC2_ENG_LET_OFF_SOUND_COMMAND: int = 0x01F9
TMCC2_ENG_POP_OFF_SOUND_COMMAND: int = 0x0153
TMCC2_ENG_REFUELLING_SOUND_COMMAND: int = 0x012D
TMCC2_FORWARD_DIRECTION_COMMAND: int = 0x0100
TMCC2_HIGHBALL_SPEED: int = 199
TMCC2_LIMITED_SPEED: int = 118
TMCC2_MEDIUM_SPEED: int = 92
TMCC2_MOTION_START_COMMAND: int = 0x00FA
TMCC2_MOTION_STOP_COMMAND: int = 0x00FE
TMCC2_NORMAL_SPEED: int = 145
TMCC2_NUMERIC_COMMAND: int = 0x0110
TMCC2_ENG_RPM_DOWN_COMMAND: int = 0x0116
TMCC2_ENG_RPM_UP_COMMAND: int = 0x0113
TMCC2_OPEN_FRONT_COUPLER_COMMAND: int = 0x0105
TMCC2_OPEN_REAR_COUPLER_COMMAND: int = 0x0106
TMCC2_QUILLING_HORN_COMMAND: int = 0x01E0
TMCC2_RESTRICTED_SPEED: int = 24
TMCC2_REVERSE_DIRECTION_COMMAND: int = 0x0103
TMCC2_RING_BELL_COMMAND: int = 0x011D
TMCC2_ROLL_SPEED: int = 1  # express speeds as simple integers
TMCC2_SET_ABSOLUTE_SPEED_COMMAND: int = 0x0000  # encode speed in last byte (0-199)
TMCC2_SET_ADDRESS_COMMAND: int = 0x012B
TMCC2_SET_BOOST_LEVEL_COMMAND: int = 0x00E8  # encode boost level in last 3 bits (0-7)
TMCC2_SET_BRAKE_LEVEL_COMMAND: int = 0x00E0  # encode brake level in last 3 bits (0-7)
TMCC2_SET_MOMENTUM_COMMAND: int = 0x00C8  # encode momentum in last 3 bits (0 - 7)
TMCC2_SET_MOMENTUM_LOW_COMMAND: int = 0x0128
TMCC2_SET_MOMENTUM_MEDIUM_COMMAND: int = 0x0129
TMCC2_SET_MOMENTUM_HIGH_COMMAND: int = 0x012A
TMCC2_SET_RELATIVE_SPEED_COMMAND: int = 0x0140  # Relative Speed -5 - 5 encoded in last 4 bits (offset by 5)
TMCC2_SET_TRAIN_BRAKE_COMMAND: int = 0x00F0  # encode train brake in the last 3 bits (0-7)
TMCC2_SHUTDOWN_SEQ_ONE_COMMAND: int = 0x01FD
TMCC2_SHUTDOWN_SEQ_TWO_COMMAND: int = 0x01FE
TMCC2_SLOW_SPEED: int = 59
TMCC2_SOUND_OFF_COMMAND: int = 0x0150
TMCC2_SOUND_ON_COMMAND: int = 0x0151
TMCC2_STALL_COMMAND: int = 0x00F8
TMCC2_START_UP_SEQ_ONE_COMMAND: int = 0x01FB
TMCC2_START_UP_SEQ_TWO_COMMAND: int = 0x01FC
TMCC2_STOP_IMMEDIATE_COMMAND: int = 0x00FB
TMCC2_TOGGLE_DIRECTION_COMMAND: int = 0x0101
TMCC2_VOLUME_DOWN_COMMAND_HACK = 0x0114
TMCC2_VOLUME_UP_COMMAND_HACK = 0x0111
TMCC2_WATER_INJECTOR_SOUND_COMMAND: int = 0x01A8

TMCC2_ASSIGN_SINGLE_FORWARD: int = 0x0120
TMCC2_ASSIGN_SINGLE_REVERSE: int = 0x0121
TMCC2_ASSIGN_HEAD_FORWARD: int = 0x0122
TMCC2_ASSIGN_HEAD_REVERSE: int = 0x0123
TMCC2_ASSIGN_MIDDLE_FORWARD: int = 0x0124
TMCC2_ASSIGN_MIDDLE_REVERSE: int = 0x0125
TMCC2_ASSIGN_REAR_FORWARD: int = 0x0126
TMCC2_ASSIGN_REAR_REVERSE: int = 0x0127
TMCC2_ASSIGN_CLEAR_CONSIST: int = 0x012C
TMCC2_ASSIGN_TO_TRAIN: int = 0x0130


TMCC2_SPEED_MAP = dict(
    STOP_HOLD=0,
    SH=0,
    STOP=0,
    ROLL=TMCC2_ROLL_SPEED,
    RO=TMCC2_ROLL_SPEED,
    RESTRICTED=TMCC2_RESTRICTED_SPEED,
    RE=TMCC2_RESTRICTED_SPEED,
    SLOW=TMCC2_SLOW_SPEED,
    SL=TMCC2_SLOW_SPEED,
    MEDIUM=TMCC2_MEDIUM_SPEED,
    ME=TMCC2_MEDIUM_SPEED,
    LIMITED=TMCC2_LIMITED_SPEED,
    LI=TMCC2_LIMITED_SPEED,
    NORMAL=TMCC2_NORMAL_SPEED,
    NO=TMCC2_NORMAL_SPEED,
    HIGH=TMCC2_HIGHBALL_SPEED,
    HIGHBALL=TMCC2_HIGHBALL_SPEED,
    HI=TMCC2_HIGHBALL_SPEED,
)

TMCC2_NUMERIC_SPEED_TO_DIRECTIVE_MAP = {s: p for p, s in TMCC2_SPEED_MAP.items() if len(p) > 2 and p != "HIGH"}


@unique
class TMCC2RRSpeedsEnum(OfficialRRSpeeds):
    STOP_HOLD = range(0, TMCC2_ROLL_SPEED)
    ROLL = range(TMCC2_ROLL_SPEED, TMCC2_RESTRICTED_SPEED)
    RESTRICTED = range(TMCC2_RESTRICTED_SPEED, TMCC2_SLOW_SPEED)
    SLOW = range(TMCC2_SLOW_SPEED, TMCC2_MEDIUM_SPEED)
    MEDIUM = range(TMCC2_MEDIUM_SPEED, TMCC2_LIMITED_SPEED)
    LIMITED = range(TMCC2_LIMITED_SPEED, TMCC2_NORMAL_SPEED)
    NORMAL = range(TMCC2_NORMAL_SPEED, TMCC2_HIGHBALL_SPEED)
    HIGHBALL = range(TMCC2_HIGHBALL_SPEED, TMCC2_HIGHBALL_SPEED + 1)


@unique
class TMCC2EngineCommandEnum(TMCC2Enum):
    ABSOLUTE_SPEED = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND, d_max=199, filtered=True, d4_broadcast=True)
    AUGER = TMCC2CommandDef(TMCC2_ENG_AUGER_SOUND_COMMAND)
    AUX1_OFF = TMCC2CommandDef(TMCC2_AUX1_OFF_COMMAND)
    AUX1_ON = TMCC2CommandDef(TMCC2_AUX1_ON_COMMAND)
    AUX1_OPTION_ONE = TMCC2CommandDef(TMCC2_AUX1_OPTION_ONE_COMMAND)
    AUX1_OPTION_TWO = TMCC2CommandDef(TMCC2_AUX1_OPTION_TWO_COMMAND)
    AUX2_OFF = TMCC2CommandDef(TMCC2_AUX2_OFF_COMMAND)
    AUX2_ON = TMCC2CommandDef(TMCC2_AUX2_ON_COMMAND)
    AUX2_OPTION_ONE = TMCC2CommandDef(TMCC2_AUX2_OPTION_ONE_COMMAND)
    AUX2_OPTION_TWO = TMCC2CommandDef(TMCC2_AUX2_OPTION_TWO_COMMAND)
    AUX3_OPTION_ONE = TMCC2CommandDef(TMCC2_AUX3_OPTION_ONE_COMMAND)
    BELL_OFF = TMCC2CommandDef(TMCC2_BELL_OFF_COMMAND)
    BELL_ON = TMCC2CommandDef(TMCC2_BELL_ON_COMMAND)
    BELL_ONE_SHOT_DING = TMCC2CommandDef(TMCC2_BELL_ONE_SHOT_DING_COMMAND, d_max=3, interval=1000)
    BELL_SLIDER_POSITION = TMCC2CommandDef(TMCC2_BELL_SLIDER_POSITION_COMMAND, d_min=2, d_max=5)
    BLOW_HORN_ONE = TMCC2CommandDef(TMCC2_BLOW_HORN_ONE_COMMAND, interval=100)
    BLOW_HORN_TWO = TMCC2CommandDef(TMCC2_BLOW_HORN_TWO_COMMAND, interval=100)
    BOOST_LEVEL = TMCC2CommandDef(TMCC2_SET_BOOST_LEVEL_COMMAND, d_max=7)
    BOOST_SPEED = TMCC2CommandDef(TMCC2_BOOST_SPEED_COMMAND, interval=200)
    BRAKE_AIR_RELEASE = TMCC2CommandDef(TMCC2_ENG_BRAKE_AIR_RELEASE_SOUND_COMMAND)
    BRAKE_LEVEL = TMCC2CommandDef(TMCC2_SET_BRAKE_LEVEL_COMMAND, d_max=7)
    BRAKE_SPEED = TMCC2CommandDef(TMCC2_BRAKE_SPEED_COMMAND, interval=200)
    BRAKE_SQUEAL = TMCC2CommandDef(TMCC2_ENG_BRAKE_SQUEAL_SOUND_COMMAND)
    CYLINDER_HISS = TMCC2CommandDef(TMCC2_ENG_CYLINDER_HISS_SOUND_COMMAND)
    DIESEL_RPM = TMCC2CommandDef(TMCC2_DIESEL_RPM_SOUND_COMMAND, d_max=7, filtered=True)
    ENGINE_LABOR = TMCC2CommandDef(TMCC2_ENGINE_LABOR_COMMAND, d_max=31, filtered=True, d4_broadcast=True)
    ENGINE_LABOR_DEFAULT = TMCC2CommandDef(
        TMCC2_ENGINE_LABOR_COMMAND | 12, alias="ENGINE_LABOR", data=DEFAULT_ENGINE_LABOR, filtered=True
    )
    FORWARD_DIRECTION = TMCC2CommandDef(TMCC2_FORWARD_DIRECTION_COMMAND, filtered=True, d4_broadcast=True)
    FRONT_COUPLER = TMCC2CommandDef(TMCC2_OPEN_FRONT_COUPLER_COMMAND)
    LET_OFF = TMCC2CommandDef(TMCC2_ENG_LET_OFF_SOUND_COMMAND)
    LET_OFF_LONG = TMCC2CommandDef(TMCC2_ENG_LET_OFF_LONG_SOUND_COMMAND)
    MOMENTUM = TMCC2CommandDef(TMCC2_SET_MOMENTUM_COMMAND, d_max=7)
    MOMENTUM_HIGH = TMCC2CommandDef(TMCC2_SET_MOMENTUM_HIGH_COMMAND)
    MOMENTUM_LOW = TMCC2CommandDef(TMCC2_SET_MOMENTUM_LOW_COMMAND)
    MOMENTUM_MEDIUM = TMCC2CommandDef(TMCC2_SET_MOMENTUM_MEDIUM_COMMAND)
    MOTION_START = TMCC2CommandDef(TMCC2_MOTION_START_COMMAND)
    MOTION_STOP = TMCC2CommandDef(TMCC2_MOTION_STOP_COMMAND)
    NUMERIC = TMCC2CommandDef(TMCC2_NUMERIC_COMMAND, d_max=9)
    POP_OFF = TMCC2CommandDef(TMCC2_ENG_POP_OFF_SOUND_COMMAND)
    QUILLING_HORN = TMCC2CommandDef(TMCC2_QUILLING_HORN_COMMAND, d_max=15, interval=100)
    REAR_COUPLER = TMCC2CommandDef(TMCC2_OPEN_REAR_COUPLER_COMMAND)
    REFUELLING = TMCC2CommandDef(TMCC2_ENG_REFUELLING_SOUND_COMMAND)
    RELATIVE_SPEED = TMCC2CommandDef(TMCC2_SET_RELATIVE_SPEED_COMMAND, d_map=RELATIVE_SPEED_MAP)
    REVERSE_DIRECTION = TMCC2CommandDef(TMCC2_REVERSE_DIRECTION_COMMAND, filtered=True, d4_broadcast=True)
    RING_BELL = TMCC2CommandDef(TMCC2_RING_BELL_COMMAND)
    RPM_DOWN = TMCC2CommandDef(TMCC2_ENG_RPM_DOWN_COMMAND, alias="NUMERIC", data=6)
    RPM_UP = TMCC2CommandDef(TMCC2_ENG_RPM_UP_COMMAND, alias="NUMERIC", data=3)
    SET_ADDRESS = TMCC2CommandDef(TMCC2_SET_ADDRESS_COMMAND)
    SHUTDOWN_DELAYED = TMCC2CommandDef(TMCC2_NUMERIC_COMMAND | 5, alias="NUMERIC", data=5)
    RESET = TMCC2CommandDef(TMCC2_NUMERIC_COMMAND | 0, alias="NUMERIC", data=0)
    SHUTDOWN_DELAYED_NOP = TMCC2CommandDef(TMCC2_SHUTDOWN_SEQ_ONE_COMMAND)
    SHUTDOWN_IMMEDIATE = TMCC2CommandDef(TMCC2_SHUTDOWN_SEQ_TWO_COMMAND)
    SOUND_OFF = TMCC2CommandDef(TMCC2_SOUND_OFF_COMMAND)
    SOUND_ON = TMCC2CommandDef(TMCC2_SOUND_ON_COMMAND)
    SPEED_HIGHBALL = TMCC2CommandDef(
        TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_HIGHBALL_SPEED, alias="ABSOLUTE_SPEED", data=TMCC2_HIGHBALL_SPEED
    )
    SPEED_LIMITED = TMCC2CommandDef(
        TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_LIMITED_SPEED, alias="ABSOLUTE_SPEED", data=TMCC2_LIMITED_SPEED
    )
    SPEED_MEDIUM = TMCC2CommandDef(
        TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_MEDIUM_SPEED, alias="ABSOLUTE_SPEED", data=TMCC2_MEDIUM_SPEED
    )
    SPEED_NORMAL = TMCC2CommandDef(
        TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_NORMAL_SPEED, alias="ABSOLUTE_SPEED", data=TMCC2_NORMAL_SPEED
    )
    SPEED_RESTRICTED = TMCC2CommandDef(
        TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_RESTRICTED_SPEED, alias="ABSOLUTE_SPEED", data=TMCC2_RESTRICTED_SPEED
    )
    SPEED_ROLL = TMCC2CommandDef(
        TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_ROLL_SPEED, alias="ABSOLUTE_SPEED", data=TMCC2_ROLL_SPEED
    )
    SPEED_SLOW = TMCC2CommandDef(
        TMCC2_SET_ABSOLUTE_SPEED_COMMAND | TMCC2_SLOW_SPEED, alias="ABSOLUTE_SPEED", data=TMCC2_SLOW_SPEED
    )
    SPEED_STOP_HOLD = TMCC2CommandDef(TMCC2_SET_ABSOLUTE_SPEED_COMMAND, alias="ABSOLUTE_SPEED", data=0)
    STALL = TMCC2CommandDef(TMCC2_STALL_COMMAND)
    START_UP_DELAYED = TMCC2CommandDef(TMCC2_START_UP_SEQ_ONE_COMMAND)
    START_UP_IMMEDIATE = TMCC2CommandDef(TMCC2_START_UP_SEQ_TWO_COMMAND)
    STOP_IMMEDIATE = TMCC2CommandDef(TMCC2_STOP_IMMEDIATE_COMMAND, filtered=True, d4_broadcast=True)
    SYSTEM_HALT = TMCC2CommandDef(TMCC2_HALT_COMMAND)
    TOGGLE_DIRECTION = TMCC2CommandDef(TMCC2_TOGGLE_DIRECTION_COMMAND, filtered=True, d4_broadcast=True)
    TOWER_CHATTER = TMCC2CommandDef(TMCC2_NUMERIC_COMMAND | 7, alias="NUMERIC", data=7)
    TRAIN_BRAKE = TMCC2CommandDef(TMCC2_SET_TRAIN_BRAKE_COMMAND, d_max=7, filtered=True, d4_broadcast=True)
    WATER_INJECTOR = TMCC2CommandDef(TMCC2_WATER_INJECTOR_SOUND_COMMAND)
    VOLUME_UP = TMCC2CommandDef(TMCC2_VOLUME_UP_COMMAND_HACK, alias="NUMERIC", data=1)
    VOLUME_DOWN = TMCC2CommandDef(TMCC2_VOLUME_DOWN_COMMAND_HACK, alias="NUMERIC", data=4)
    SINGLE_FORWARD = TMCC2CommandDef(TMCC2_ASSIGN_SINGLE_FORWARD)
    SINGLE_REVERSE = TMCC2CommandDef(TMCC2_ASSIGN_SINGLE_REVERSE)
    HEAD_FORWARD = TMCC2CommandDef(TMCC2_ASSIGN_HEAD_FORWARD)
    HEAD_REVERSE = TMCC2CommandDef(TMCC2_ASSIGN_HEAD_REVERSE)
    MIDDLE_FORWARD = TMCC2CommandDef(TMCC2_ASSIGN_MIDDLE_FORWARD)
    MIDDLE_REVERSE = TMCC2CommandDef(TMCC2_ASSIGN_MIDDLE_REVERSE)
    REAR_FORWARD = TMCC2CommandDef(TMCC2_ASSIGN_REAR_FORWARD)
    REAR_REVERSE = TMCC2CommandDef(TMCC2_ASSIGN_REAR_REVERSE)
    CLEAR_CONSIST = TMCC2CommandDef(TMCC2_ASSIGN_CLEAR_CONSIST)


# map dereferenced commands to their aliases
TMCC2_COMMAND_TO_ALIAS_MAP = {}
for tmcc2_enum in [TMCC2EngineCommandEnum, TMCC2HaltCommandEnum, TMCC2RouteCommandEnum]:
    for enum in tmcc2_enum:
        if enum.is_alias:
            TMCC2_COMMAND_TO_ALIAS_MAP[enum.alias] = enum

# Speed to RPM Map
TMCC2_SPEED_TO_RPM = RangeKeyDict(
    {
        (0, 4): 0,
        (4, 29): 1,
        (29, 57): 2,
        (57, 86): 3,
        (86, 114): 4,
        (114, 143): 5,
        (143, 171): 6,
        (171, 200): 7,
    }
)


def tmcc2_speed_to_rpm(speed: int) -> int:
    return TMCC2_SPEED_TO_RPM[speed]
