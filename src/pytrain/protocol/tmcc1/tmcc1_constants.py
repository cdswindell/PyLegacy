#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
"""
TMCC1 Constants
"""

from __future__ import annotations

from enum import unique
from typing import Dict, Tuple

from ..command_def import CommandDef, CommandDefEnum
from ..constants import (
    DEFAULT_ADDRESS,
    RELATIVE_SPEED_MAP,
    REVERSE_SPEED_MAP,
    CommandPrefix,
    CommandScope,
    CommandSyntax,
    OfficialRRSpeeds,
)


class TMCC1Enum(CommandDefEnum):
    """
    Marker Interface for all TMCC1 enums
    """

    pass


"""
    TMCC1 Protocol Constants
"""
TMCC1_COMMAND_PREFIX: int = 0xFE


@unique
class TMCC1CommandIdentifier(CommandPrefix):
    ENGINE = 0b00000000  # first 2 bits significant
    TRAIN = 0b11001000  # first 5 bits significant
    SWITCH = 0b01000000  # first 2 bits significant
    ACC = 0b10000000  # first 2 bits significant
    ROUTE = 0b11010000  # first 4 bits significant
    HALT = 0xFFFF  # all 16 bits significant
    SYNC = 0xF0F0  # first 12 bits significant

    @classmethod
    def classify(cls, byte_data) -> CommandScope:
        fb_value = int(byte_data[0])
        # because of the varying number of bits, we need to
        # perform different tests
        if fb_value == TMCC1CommandIdentifier.HALT:
            return CommandScope.SYSTEM
        if fb_value & 0b11010000 == TMCC1CommandIdentifier.ROUTE:
            return CommandScope.ROUTE
        if fb_value & 0b11000000 == TMCC1CommandIdentifier.ENGINE:
            return CommandScope.ENGINE
        if fb_value & 0b11000000 == TMCC1CommandIdentifier.SWITCH:
            return CommandScope.SWITCH
        if fb_value & 0b11000000 == TMCC1CommandIdentifier.ACC:
            return CommandScope.ACC
        if fb_value & 0b11111000 == TMCC1CommandIdentifier.TRAIN:
            return CommandScope.TRAIN
        raise ValueError(f"Cannot classify TMCC identifier: {byte_data.hex(':')}")


TMCC1_IDENT_TO_SCOPE_MAP: Dict[TMCC1CommandIdentifier, CommandScope] = {
    TMCC1CommandIdentifier.ENGINE: CommandScope.ENGINE,
    TMCC1CommandIdentifier.TRAIN: CommandScope.TRAIN,
    TMCC1CommandIdentifier.SWITCH: CommandScope.SWITCH,
    TMCC1CommandIdentifier.ACC: CommandScope.ACC,
    TMCC1CommandIdentifier.ROUTE: CommandScope.ROUTE,
    TMCC1CommandIdentifier.HALT: CommandScope.SYSTEM,
    TMCC1CommandIdentifier.SYNC: CommandScope.SYNC,
}


class TMCC1CommandDef(CommandDef):
    def __init__(
        self,
        command_bits: int,
        command_ident: TMCC1CommandIdentifier = TMCC1CommandIdentifier.ENGINE,
        is_addressable: bool = True,
        num_address_bits: int = 7,
        d_min: int = 0,
        d_max: int = 0,
        d_map: Dict[int, int] = None,
        do_reverse_lookup: bool = True,
        alias: str = None,
        data: int = None,
        filtered: bool = False,
        aux1: bool = False,
        interval: int = None,
    ) -> None:
        super().__init__(
            command_bits,
            is_addressable=is_addressable,
            num_address_bits=num_address_bits,
            d_min=d_min,
            d_max=d_max,
            d_map=d_map,
            do_reverse_lookup=do_reverse_lookup,
            alias=alias,
            data=data,
            filtered=filtered,
            interval=interval,
        )
        self._command_ident = command_ident
        self._aux1 = aux1

    @property
    def syntax(self) -> CommandSyntax:
        return CommandSyntax.TMCC

    @property
    def identifier(self) -> TMCC1CommandIdentifier:
        return self._command_ident

    @property
    def first_byte(self) -> bytes:
        return TMCC1_COMMAND_PREFIX.to_bytes(1, byteorder="big")

    @property
    def scope(self) -> CommandScope:
        return TMCC1_IDENT_TO_SCOPE_MAP[self.identifier]

    @property
    def is_aux1_prefixed(self) -> bool:
        return self._aux1

    @property
    def address_mask(self) -> int:
        return 0xFFFF & ~((2**self.num_address_bits - 1) << 7)

    @property
    def train_address_mask(self) -> int:
        return 0xFFFF & ~(((2**4) - 1) << 7)

    def address_from_bytes(self, byte_data: bytes) -> int:
        if self.is_addressable:
            value = int.from_bytes(byte_data, byteorder="big")
            # if first byte indicates train, we have to change the address mask
            if self.classify(byte_data) == CommandScope.TRAIN:
                return (0xFFFF & (~self.train_address_mask & value)) >> 7
            else:
                return (0xFFFF & (~self.address_mask & value)) >> 7
        else:
            return DEFAULT_ADDRESS

    @staticmethod
    def classify(byte_data: bytes) -> CommandScope:
        return TMCC1CommandIdentifier.classify(byte_data)

    @property
    def alias(self) -> TMCC1EngineCommandEnum | Tuple[TMCC1EngineCommandEnum, int] | None:
        if self._alias is not None:
            if isinstance(self._alias, str):
                alias = TMCC1EngineCommandEnum.by_name(self._alias, raise_exception=True)
                if self._data is None:
                    return alias
                else:
                    return alias, self._data
            else:
                raise ValueError(f"Cannot classify command alias: {self._alias} ({type(self._alias)})")
        return None


class SyncCommandDef(TMCC1CommandDef):
    def __init__(
        self,
        command_bits: int,
        node_scope: bool = False,
        d_min: int = 0,
        d_max: int = 0,
        d_map: Dict[int, int] = None,
        do_reverse_lookup: bool = True,
        alias: str = None,
        data: int = None,
        filtered: bool = False,
    ) -> None:
        super().__init__(
            command_bits,
            command_ident=TMCC1CommandIdentifier.SYNC,
            is_addressable=False,
            num_address_bits=7,
            d_min=d_min,
            d_max=d_max,
            d_map=d_map,
            do_reverse_lookup=do_reverse_lookup,
            alias=alias,
            data=data,
            filtered=filtered,
        )
        self._node_scope = node_scope

    @property
    def is_node_scope(self) -> bool:
        return self._node_scope


TMCC1_REGISTER_COMMAND: int = 0xF0F0
TMCC1_DISCONNECT_COMMAND: int = 0xF0F1
TMCC1_SYNC_REQUEST_COMMAND: int = 0xF0F2
TMCC1_SYNC_BEGIN_COMMAND: int = 0xF0F3
TMCC1_SYNCING_COMMAND: int = 0xF0F4
TMCC1_SYNC_COMPLETE_COMMAND: int = 0xF0F5
TMCC1_SENDING_STATE_COMMAND: int = 0xF0F6
TMCC1_QUIT_COMMAND: int = 0xF0F7
TMCC1_REBOOT_COMMAND: int = 0xF0F8
TMCC1_UPDATE_COMMAND: int = 0xF0F9
TMCC1_UPGRADE_COMMAND: int = 0xF0FA
TMCC1_SHUTDOWN_COMMAND: int = 0xF0FB
TMCC1_RESTART_COMMAND: int = 0xF0FC
TMCC1_KEEP_ALIVE_COMMAND: int = 0xF0FD
TMCC1_RESYNC_COMMAND: int = 0xF0FE
TMCC1_SYNCED_COMMAND: int = 0xF0FF


@unique
class TMCC1SyncCommandEnum(TMCC1Enum):
    DISCONNECT = SyncCommandDef(TMCC1_DISCONNECT_COMMAND)
    KEEP_ALIVE = SyncCommandDef(TMCC1_KEEP_ALIVE_COMMAND)
    QUIT = SyncCommandDef(TMCC1_QUIT_COMMAND)
    REBOOT = SyncCommandDef(TMCC1_REBOOT_COMMAND, node_scope=True)
    REGISTER = SyncCommandDef(TMCC1_REGISTER_COMMAND)
    RESTART = SyncCommandDef(TMCC1_RESTART_COMMAND)
    RESYNC = SyncCommandDef(TMCC1_RESYNC_COMMAND)
    SENDING_STATE = SyncCommandDef(TMCC1_SENDING_STATE_COMMAND)
    SHUTDOWN = SyncCommandDef(TMCC1_SHUTDOWN_COMMAND, node_scope=True)
    SYNCHRONIZED = SyncCommandDef(TMCC1_SYNCED_COMMAND)
    SYNCHRONIZING = SyncCommandDef(TMCC1_SYNCING_COMMAND)
    SYNC_BEGIN = SyncCommandDef(TMCC1_SYNC_BEGIN_COMMAND)
    SYNC_COMPLETE = SyncCommandDef(TMCC1_SYNC_COMPLETE_COMMAND)
    SYNC_REQUEST = SyncCommandDef(TMCC1_SYNC_REQUEST_COMMAND)
    UPDATE = SyncCommandDef(TMCC1_UPDATE_COMMAND)
    UPGRADE = SyncCommandDef(TMCC1_UPGRADE_COMMAND)


TMCC1_HALT_COMMAND: int = 0xFFFF


@unique
class TMCC1HaltCommandEnum(TMCC1Enum):
    HALT = TMCC1CommandDef(TMCC1_HALT_COMMAND, TMCC1CommandIdentifier.HALT, is_addressable=False, filtered=True)


TMCC1_ROUTE_COMMAND: int = 0xD01F


@unique
class TMCC1RouteCommandEnum(TMCC1Enum):
    FIRE = TMCC1CommandDef(TMCC1_ROUTE_COMMAND, TMCC1CommandIdentifier.ROUTE, num_address_bits=5)


TMCC1_SWITCH_THRU_COMMAND: int = 0x4000
TMCC1_SWITCH_OUT_COMMAND: int = 0x401F
TMCC1_SWITCH_SET_ADDRESS_COMMAND: int = 0x402B


@unique
class TMCC1SwitchCommandEnum(TMCC1Enum):
    THRU = TMCC1CommandDef(TMCC1_SWITCH_THRU_COMMAND, TMCC1CommandIdentifier.SWITCH)
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

TMCC1_ACC_FRONT_COUPLER_COMMAND: int = 0x8005
TMCC1_ACC_REAR_COUPLER_COMMAND: int = 0x8006

TMCC1_ACC_BOOST_COMMAND: int = 0x8004
TMCC1_ACC_BRAKE_COMMAND: int = 0x8007
TMCC1_ACC_RELATIVE_SPEED_COMMAND: int = 0x8040
TMCC1_ACC_FORWARD_SPEED_COMMAND: int = 0x8000
TMCC1_ACC_REVERSE_SPEED_COMMAND: int = 0x807C


@unique
class TMCC1AuxCommandEnum(TMCC1Enum):
    SET_ADDRESS = TMCC1CommandDef(TMCC1_ACC_SET_ADDRESS_COMMAND, TMCC1CommandIdentifier.ACC)
    NUMERIC = TMCC1CommandDef(TMCC1_ACC_NUMERIC_COMMAND, TMCC1CommandIdentifier.ACC, d_max=9)
    AUX1_OFF = TMCC1CommandDef(TMCC1_ACC_AUX_1_OFF_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX1_ON = TMCC1CommandDef(TMCC1_ACC_AUX_1_ON_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX1_OPT_ONE = TMCC1CommandDef(TMCC1_ACC_AUX_1_OPTION_1_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX1_OPT_TWO = TMCC1CommandDef(TMCC1_ACC_AUX_1_OPTION_2_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX2_OFF = TMCC1CommandDef(TMCC1_ACC_AUX_2_OFF_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX2_ON = TMCC1CommandDef(TMCC1_ACC_AUX_2_ON_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX2_OPT_ONE = TMCC1CommandDef(TMCC1_ACC_AUX_2_OPTION_1_COMMAND, TMCC1CommandIdentifier.ACC)
    AUX2_OPT_TWO = TMCC1CommandDef(TMCC1_ACC_AUX_2_OPTION_2_COMMAND, TMCC1CommandIdentifier.ACC)
    FRONT_COUPLER = TMCC1CommandDef(TMCC1_ACC_FRONT_COUPLER_COMMAND, TMCC1CommandIdentifier.ACC)
    REAR_COUPLER = TMCC1CommandDef(TMCC1_ACC_REAR_COUPLER_COMMAND, TMCC1CommandIdentifier.ACC)
    BOOST = TMCC1CommandDef(TMCC1_ACC_BOOST_COMMAND, TMCC1CommandIdentifier.ACC)
    BRAKE = TMCC1CommandDef(TMCC1_ACC_BRAKE_COMMAND, TMCC1CommandIdentifier.ACC)
    FORWARD_SPEED = TMCC1CommandDef(TMCC1_ACC_FORWARD_SPEED_COMMAND, TMCC1CommandIdentifier.ACC, d_max=3)
    REVERSE_SPEED = TMCC1CommandDef(
        TMCC1_ACC_REVERSE_SPEED_COMMAND, TMCC1CommandIdentifier.ACC, d_map=REVERSE_SPEED_MAP
    )
    RELATIVE_SPEED = TMCC1CommandDef(
        TMCC1_ACC_RELATIVE_SPEED_COMMAND, TMCC1CommandIdentifier.ACC, d_map=RELATIVE_SPEED_MAP
    )


# Engine/Train commands
TMCC1_TRAIN_COMMAND_MODIFIER: int = 0xC800  # Logically OR with engine command to make train command
TMCC1_TRAIN_COMMAND_PURIFIER: int = 0x07FF  # Logically AND with engine command to reset engine bits
TMCC1_ENG_ABSOLUTE_SPEED_COMMAND: int = 0x0060  # Absolute speed 0-31 encoded in last 5-bits
TMCC1_ENG_RELATIVE_SPEED_COMMAND: int = 0x0040  # Relative Speed -5 - 5 encoded in last 4-bits (offset by 5)
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

TMCC1_ENG_AUX3_OPTION_ONE_COMMAND: int = 0x003B  # Aux 3 button

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

TMCC1_ENG_ASSIGN_TRAIN_COMMAND: int = 0x0030
TMCC1_ENG_ASSIGN_SINGLE_FORWARD_COMMAND: int = 0x0020
TMCC1_ENG_ASSIGN_SINGLE_REVERSE_COMMAND: int = 0x0024
TMCC1_ENG_ASSIGN_HEAD_FORWARD_COMMAND: int = 0x0021
TMCC1_ENG_ASSIGN_HEAD_REVERSE_COMMAND: int = 0x0025
TMCC1_ENG_ASSIGN_MIDDLE_FORWARD_COMMAND: int = 0x0022
TMCC1_ENG_ASSIGN_MIDDLE_REVERSE_COMMAND: int = 0x0026
TMCC1_ENG_ASSIGN_REAR_FORWARD_COMMAND: int = 0x0023
TMCC1_ENG_ASSIGN_REAR_REVERSE_COMMAND: int = 0x0027
TMCC1_ENG_CLEAR_CONSIST_COMMAND: int = 0x002C

TMCC1_ROLL_SPEED: int = 1  # express speeds as simple integers
TMCC1_RESTRICTED_SPEED: int = 5
TMCC1_SLOW_SPEED: int = 10
TMCC1_MEDIUM_SPEED: int = 15
TMCC1_LIMITED_SPEED: int = 20
TMCC1_NORMAL_SPEED: int = 25
TMCC1_HIGHBALL_SPEED: int = 27

TMCC1_SPEED_MAP: dict[str, int] = {
    "STOP_HOLD": 0,
    "SH": 0,
    "STOP": 0,
    "ROLL": TMCC1_ROLL_SPEED,
    "RO": TMCC1_ROLL_SPEED,
    "RESTRICTED": TMCC1_RESTRICTED_SPEED,
    "RE": TMCC1_RESTRICTED_SPEED,
    "SLOW": TMCC1_SLOW_SPEED,
    "SL": TMCC1_SLOW_SPEED,
    "MEDIUM": TMCC1_MEDIUM_SPEED,
    "ME": TMCC1_MEDIUM_SPEED,
    "LIMITED": TMCC1_LIMITED_SPEED,
    "LI": TMCC1_LIMITED_SPEED,
    "NORMAL": TMCC1_NORMAL_SPEED,
    "NO": TMCC1_NORMAL_SPEED,
    "HIGH": TMCC1_HIGHBALL_SPEED,
    "HIGHBALL": TMCC1_HIGHBALL_SPEED,
    "HI": TMCC1_HIGHBALL_SPEED,
}

TMCC1_NUMERIC_SPEED_TO_DIRECTIVE_MAP = {s: p for p, s in TMCC1_SPEED_MAP.items() if len(p) > 2 and p != "HIGH"}


@unique
class TMCC1RRSpeedsEnum(OfficialRRSpeeds):
    STOP_HOLD = range(0, TMCC1_ROLL_SPEED)
    ROLL = range(TMCC1_ROLL_SPEED, TMCC1_RESTRICTED_SPEED)
    RESTRICTED = range(TMCC1_RESTRICTED_SPEED, TMCC1_SLOW_SPEED)
    SLOW = range(TMCC1_SLOW_SPEED, TMCC1_MEDIUM_SPEED)
    MEDIUM = range(TMCC1_MEDIUM_SPEED, TMCC1_LIMITED_SPEED)
    LIMITED = range(TMCC1_LIMITED_SPEED, TMCC1_NORMAL_SPEED)
    NORMAL = range(TMCC1_NORMAL_SPEED, TMCC1_HIGHBALL_SPEED)
    HIGHBALL = range(TMCC1_HIGHBALL_SPEED, 32)


@unique
class TMCC1EngineCommandEnum(TMCC1Enum):
    ABSOLUTE_SPEED = TMCC1CommandDef(TMCC1_ENG_ABSOLUTE_SPEED_COMMAND, d_max=31, filtered=True)
    ASSIGN_TRAIN = TMCC1CommandDef(TMCC1_ENG_ASSIGN_TRAIN_COMMAND, d_max=10)
    AUX1_OFF = TMCC1CommandDef(TMCC1_ENG_AUX1_OFF_COMMAND)
    AUX1_ON = TMCC1CommandDef(TMCC1_ENG_AUX1_ON_COMMAND)
    AUX1_OPTION_ONE = TMCC1CommandDef(TMCC1_ENG_AUX1_OPTION_ONE_COMMAND)
    AUX1_OPTION_TWO = TMCC1CommandDef(TMCC1_ENG_AUX1_OPTION_TWO_COMMAND)
    AUX2_OFF = TMCC1CommandDef(TMCC1_ENG_AUX2_OFF_COMMAND)
    AUX2_ON = TMCC1CommandDef(TMCC1_ENG_AUX2_ON_COMMAND)
    AUX2_OPTION_ONE = TMCC1CommandDef(TMCC1_ENG_AUX2_OPTION_ONE_COMMAND)
    AUX2_OPTION_TWO = TMCC1CommandDef(TMCC1_ENG_AUX2_OPTION_TWO_COMMAND)
    AUX3_OPTION_ONE = TMCC1CommandDef(TMCC1_ENG_AUX3_OPTION_ONE_COMMAND)
    BLOW_HORN_ONE = TMCC1CommandDef(TMCC1_ENG_BLOW_HORN_ONE_COMMAND, interval=100)
    BLOW_HORN_TWO = TMCC1CommandDef(TMCC1_ENG_BLOW_HORN_TWO_COMMAND, interval=100)
    BOOST_SPEED = TMCC1CommandDef(TMCC1_ENG_BOOST_SPEED_COMMAND, interval=200)
    BRAKE_SPEED = TMCC1CommandDef(TMCC1_ENG_BRAKE_SPEED_COMMAND, interval=200)
    CLEAR_CONSIST = TMCC1CommandDef(TMCC1_ENG_CLEAR_CONSIST_COMMAND)
    FORWARD_DIRECTION = TMCC1CommandDef(TMCC1_ENG_FORWARD_DIRECTION_COMMAND, filtered=False)
    FRONT_COUPLER = TMCC1CommandDef(TMCC1_ENG_OPEN_FRONT_COUPLER_COMMAND)
    FUNC_MINUS = TMCC1CommandDef(TMCC1_ENG_FUNC_MINUS_COMMAND, alias="NUMERIC", data=8)
    FUNC_PLUS = TMCC1CommandDef(TMCC1_ENG_FUNC_PLUS_COMMAND, alias="NUMERIC", data=9)
    HEAD_FORWARD = TMCC1CommandDef(TMCC1_ENG_ASSIGN_HEAD_FORWARD_COMMAND)
    HEAD_REVERSE = TMCC1CommandDef(TMCC1_ENG_ASSIGN_HEAD_REVERSE_COMMAND)
    LET_OFF = TMCC1CommandDef(TMCC1_ENG_LET_OFF_SOUND_COMMAND)
    MIDDLE_FORWARD = TMCC1CommandDef(TMCC1_ENG_ASSIGN_MIDDLE_FORWARD_COMMAND)
    MIDDLE_REVERSE = TMCC1CommandDef(TMCC1_ENG_ASSIGN_MIDDLE_REVERSE_COMMAND)
    MOMENTUM_HIGH = TMCC1CommandDef(TMCC1_ENG_SET_MOMENTUM_HIGH_COMMAND)
    MOMENTUM_LOW = TMCC1CommandDef(TMCC1_ENG_SET_MOMENTUM_LOW_COMMAND)
    MOMENTUM_MEDIUM = TMCC1CommandDef(TMCC1_ENG_SET_MOMENTUM_MEDIUM_COMMAND)
    NUMERIC = TMCC1CommandDef(TMCC1_ENG_NUMERIC_COMMAND, d_max=9)
    REAR_COUPLER = TMCC1CommandDef(TMCC1_ENG_OPEN_REAR_COUPLER_COMMAND)
    REAR_FORWARD = TMCC1CommandDef(TMCC1_ENG_ASSIGN_REAR_FORWARD_COMMAND)
    REAR_REVERSE = TMCC1CommandDef(TMCC1_ENG_ASSIGN_REAR_REVERSE_COMMAND)
    RELATIVE_SPEED = TMCC1CommandDef(TMCC1_ENG_RELATIVE_SPEED_COMMAND, d_map=RELATIVE_SPEED_MAP)
    RESET = TMCC1CommandDef(TMCC1_ENG_NUMERIC_COMMAND | 0, alias="NUMERIC", data=0)
    REVERSE_DIRECTION = TMCC1CommandDef(TMCC1_ENG_REVERSE_DIRECTION_COMMAND, filtered=False)
    RING_BELL = TMCC1CommandDef(TMCC1_ENG_RING_BELL_COMMAND)
    RPM_DOWN = TMCC1CommandDef(TMCC1_ENG_RPM_DOWN_COMMAND, alias="NUMERIC", data=6)
    RPM_UP = TMCC1CommandDef(TMCC1_ENG_RPM_UP_COMMAND, alias="NUMERIC", data=3)
    SET_ADDRESS = TMCC1CommandDef(TMCC1_ENG_SET_ADDRESS_COMMAND)
    SHUTDOWN_IMMEDIATE = TMCC1CommandDef(TMCC1_ENG_NUMERIC_COMMAND | 5, alias="NUMERIC", data=5, aux1=True)
    SINGLE_FORWARD = TMCC1CommandDef(TMCC1_ENG_ASSIGN_SINGLE_FORWARD_COMMAND)
    SINGLE_REVERSE = TMCC1CommandDef(TMCC1_ENG_ASSIGN_SINGLE_REVERSE_COMMAND)
    SMOKE_OFF = TMCC1CommandDef(TMCC1_ENG_NUMERIC_COMMAND | 8, alias="NUMERIC", data=8)
    SMOKE_ON = TMCC1CommandDef(TMCC1_ENG_NUMERIC_COMMAND | 9, alias="NUMERIC", data=9)
    SOUND_ONE = TMCC1CommandDef(TMCC1_ENG_SOUND_ONE_COMMAND, alias="NUMERIC", data=2)
    TOWER_CHATTER = TMCC1CommandDef(TMCC1_ENG_SOUND_TWO_COMMAND, alias="NUMERIC", data=7)
    START_UP_IMMEDIATE = TMCC1CommandDef(TMCC1_ENG_NUMERIC_COMMAND | 3, alias="NUMERIC", data=3, aux1=True)
    STOP_IMMEDIATE = TMCC1CommandDef(TMCC1_ENG_ABSOLUTE_SPEED_COMMAND, alias="ABSOLUTE_SPEED", data=0, filtered=True)
    TOGGLE_DIRECTION = TMCC1CommandDef(TMCC1_ENG_TOGGLE_DIRECTION_COMMAND, filtered=True)
    VOLUME_DOWN = TMCC1CommandDef(TMCC1_ENG_VOLUME_DOWN_COMMAND, alias="NUMERIC", data=4)
    VOLUME_UP = TMCC1CommandDef(TMCC1_ENG_VOLUME_UP_COMMAND, alias="NUMERIC", data=1)
    SPEED_HIGHBALL = TMCC1CommandDef(
        TMCC1_ENG_ABSOLUTE_SPEED_COMMAND | TMCC1_HIGHBALL_SPEED,
        alias="ABSOLUTE_SPEED",
        data=TMCC1_HIGHBALL_SPEED,
        filtered=True,
    )
    SPEED_LIMITED = TMCC1CommandDef(
        TMCC1_ENG_ABSOLUTE_SPEED_COMMAND | TMCC1_LIMITED_SPEED,
        alias="ABSOLUTE_SPEED",
        data=TMCC1_LIMITED_SPEED,
        filtered=True,
    )
    SPEED_MEDIUM = TMCC1CommandDef(
        TMCC1_ENG_ABSOLUTE_SPEED_COMMAND | TMCC1_MEDIUM_SPEED,
        alias="ABSOLUTE_SPEED",
        data=TMCC1_MEDIUM_SPEED,
        filtered=True,
    )
    SPEED_NORMAL = TMCC1CommandDef(
        TMCC1_ENG_ABSOLUTE_SPEED_COMMAND | TMCC1_NORMAL_SPEED,
        alias="ABSOLUTE_SPEED",
        data=TMCC1_NORMAL_SPEED,
        filtered=True,
    )
    SPEED_RESTRICTED = TMCC1CommandDef(
        TMCC1_ENG_ABSOLUTE_SPEED_COMMAND | TMCC1_RESTRICTED_SPEED,
        alias="ABSOLUTE_SPEED",
        data=TMCC1_RESTRICTED_SPEED,
        filtered=True,
    )
    SPEED_ROLL = TMCC1CommandDef(
        TMCC1_ENG_ABSOLUTE_SPEED_COMMAND | TMCC1_ROLL_SPEED,
        alias="ABSOLUTE_SPEED",
        data=TMCC1_ROLL_SPEED,
        filtered=True,
    )
    SPEED_SLOW = TMCC1CommandDef(
        TMCC1_ENG_ABSOLUTE_SPEED_COMMAND | TMCC1_SLOW_SPEED,
        alias="ABSOLUTE_SPEED",
        data=TMCC1_SLOW_SPEED,
        filtered=True,
    )
    SPEED_STOP_HOLD = TMCC1CommandDef(
        TMCC1_ENG_ABSOLUTE_SPEED_COMMAND,
        alias="ABSOLUTE_SPEED",
        data=0,
        filtered=True,
    )


TMCC1_COMMAND_TO_ALIAS_MAP = {}
for tmcc1_enum in [TMCC1EngineCommandEnum]:
    for enum in tmcc1_enum:
        if enum.is_alias:
            TMCC1_COMMAND_TO_ALIAS_MAP[enum.alias] = enum
