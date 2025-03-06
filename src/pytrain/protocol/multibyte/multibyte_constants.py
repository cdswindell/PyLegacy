from __future__ import annotations

import abc
from enum import IntEnum, unique
from typing import List

from ..command_def import Mixins
from ..tmcc2.tmcc2_constants import (
    TMCC2_SOUND_OFF_COMMAND,
    TMCC2_SOUND_ON_COMMAND,
    TMCC2CommandDef,
    TMCC2CommandPrefix,
    TMCC2Enum,
)

"""
    Legacy/TMCC2 Multi-byte Command sequences
"""


class TMCC2MultiByteEnum(TMCC2Enum):
    """
    Marker Interface for all TMCC2 enums
    """

    pass


"""
    Word #1 - Function indexes
"""
TMCC2_R4LC_INDEX_PREFIX: int = 0x40
TMCC2_VARIABLE_INDEX_PREFIX: int = 0x60
TMCC2_PARAMETER_INDEX_PREFIX: int = 0x70


@unique
class TMCCPrefixEnum(Mixins, IntEnum):
    R4LC = TMCC2_R4LC_INDEX_PREFIX
    VARIABLE = TMCC2_VARIABLE_INDEX_PREFIX
    PARAMETER = TMCC2_PARAMETER_INDEX_PREFIX


# Parameter indexes
TMCC2_PARAMETER_ASSIGNMENT_PARAMETER_INDEX: int = 0x71
TMCC2_RAIL_SOUNDS_DIALOG_TRIGGERS_PARAMETER_INDEX: int = 0x72
TMCC2_RAIL_SOUNDS_EFFECTS_TRIGGERS_PARAMETER_INDEX: int = 0x74
TMCC2_RAIL_SOUNDS_MASKING_CONTROL_PARAMETER_INDEX: int = 0x76
TMCC2_EFFECTS_CONTROLS_PARAMETER_INDEX: int = 0x7C
TMCC2_LIGHTING_CONTROLS_PARAMETER_INDEX: int = 0x7D
TMCC2_VARIABLE_LENGTH_COMMAND_PARAMETER_INDEX: int = 0x7F


@unique
class TMCC2ParameterIndex(Mixins, IntEnum):
    PARAMETER_ASSIGNMENT = TMCC2_PARAMETER_ASSIGNMENT_PARAMETER_INDEX
    DIALOG_TRIGGERS = TMCC2_RAIL_SOUNDS_DIALOG_TRIGGERS_PARAMETER_INDEX
    EFFECTS_TRIGGERS = TMCC2_RAIL_SOUNDS_EFFECTS_TRIGGERS_PARAMETER_INDEX
    MASKING_CONTROLS = TMCC2_RAIL_SOUNDS_MASKING_CONTROL_PARAMETER_INDEX
    EFFECTS_CONTROLS = TMCC2_EFFECTS_CONTROLS_PARAMETER_INDEX
    LIGHTING_CONTROLS = TMCC2_LIGHTING_CONTROLS_PARAMETER_INDEX
    VARIABLE_LENGTH_COMMAND = TMCC2_VARIABLE_LENGTH_COMMAND_PARAMETER_INDEX


class MultiByteCommandDef(TMCC2CommandDef):
    __metaclass__ = abc.ABCMeta

    def __init__(self, command_bits: int, d_min: int = 0, d_max: int = 0, interval: int = None) -> None:
        super().__init__(command_bits, d_min=d_min, d_max=d_max, interval=interval)
        self._first_byte = TMCC2CommandPrefix.ENGINE


class TMCC2ParameterEnum(TMCC2MultiByteEnum):
    """
    Marker interface for all Parameter Data enums
    """

    pass


"""
    Word #2 - RailSounds Dialog trigger controls (index 0x2)
"""
TMCC2_DIALOG_CONTROL_CONVENTIONAL_SHUTDOWN: int = 0x01
TMCC2_DIALOG_CONTROL_SCENE_TWO: int = 0x02
TMCC2_DIALOG_CONTROL_SCENE_SEVEN: int = 0x03
TMCC2_DIALOG_CONTROL_SCENE_FIVE: int = 0x04
TMCC2_DIALOG_CONTROL_SHORT_HORN: int = 0x05
TMCC2_DIALOG_CONTROL_TOWER_ENGINE_STARTUP: int = 0x06
TMCC2_DIALOG_CONTROL_ENGINEER_DEPARTURE_DENIED: int = 0x07
TMCC2_DIALOG_CONTROL_ENGINEER_DEPARTURE_GRANTED: int = 0x08
TMCC2_DIALOG_CONTROL_ENGINEER_HAVE_DEPARTED: int = 0x09
TMCC2_DIALOG_CONTROL_ENGINEER_ALL_CLEAR: int = 0x0A
TMCC2_DIALOG_CONTROL_TOWER_STOP_HOLD: int = 0x0B
TMCC2_DIALOG_CONTROL_TOWER_RESTRICTED_SPEED: int = 0x0C
TMCC2_DIALOG_CONTROL_TOWER_SLOW_SPEED: int = 0x0D
TMCC2_DIALOG_CONTROL_TOWER_MEDIUM_SPEED: int = 0x0E
TMCC2_DIALOG_CONTROL_TOWER_LIMITED_SPEED: int = 0x0F
TMCC2_DIALOG_CONTROL_TOWER_NORMAL_SPEED: int = 0x10
TMCC2_DIALOG_CONTROL_TOWER_HIGHBALL_SPEED: int = 0x11
TMCC2_DIALOG_CONTROL_ENGINEER_ARRIVING_SOON: int = 0x12
TMCC2_DIALOG_CONTROL_ENGINEER_HAVE_ARRIVED: int = 0x13
TMCC2_DIALOG_CONTROL_ENGINEER_SHUTDOWN: int = 0x14
TMCC2_DIALOG_CONTROL_ENGINEER_ID: int = 0x15
TMCC2_DIALOG_CONTROL_ENGINEER_ACK: int = 0x16
TMCC2_DIALOG_CONTROL_ENGINEER_STOP_SPEED_ACK: int = 0x17
TMCC2_DIALOG_CONTROL_ENGINEER_RESTRICTED_SPEED_ACK: int = 0x18
TMCC2_DIALOG_CONTROL_ENGINEER_SLOW_SPEED_ACK: int = 0x19
TMCC2_DIALOG_CONTROL_ENGINEER_MEDIUM_SPEED_ACK: int = 0x1A
TMCC2_DIALOG_CONTROL_ENGINEER_LIMITED_SPEED_ACK: int = 0x1B
TMCC2_DIALOG_CONTROL_ENGINEER_NORMAL_SPEED_ACK: int = 0x1C
TMCC2_DIALOG_CONTROL_ENGINEER_HIGHBALL_SPEED_ACK: int = 0x1D

TMCC2_DIALOG_CONTROL_ENGINEER_CONTEXT_DEPENDENT: int = 0x1E
TMCC2_DIALOG_CONTROL_EMERGENCY_CONTEXT_DEPENDENT: int = 0x1F
TMCC2_DIALOG_CONTROL_TOWER_CONTEXT_DEPENDENT: int = 0x20
TMCC2_DIALOG_CONTROL_TOWER_DEPARTURE_DENIED: int = 0x22
TMCC2_DIALOG_CONTROL_TOWER_DEPARTURE_GRANTED: int = 0x23
TMCC2_DIALOG_CONTROL_TOWER_DEPARTED: int = 0x24
TMCC2_DIALOG_CONTROL_TOWER_ALL_CLEAR: int = 0x25
TMCC2_DIALOG_CONTROL_TOWER_ARRIVING: int = 0x2D
# noinspection DuplicatedCode
TMCC2_DIALOG_CONTROL_TOWER_ARRIVED: int = 0x2E
TMCC2_DIALOG_CONTROL_TOWER_SHUT_DOWN: int = 0x2F

TMCC2_DIALOG_CONTROL_CONDUCTOR_ALL_ABOARD_A: int = 0x30

TMCC2_DIALOG_CONTROL_ENGINEER_ACK_STANDING_BY: int = 0x31
TMCC2_DIALOG_CONTROL_ENGINEER_ACK_CLEARED_TO_GO: int = 0x32
TMCC2_DIALOG_CONTROL_ENGINEER_ACK_CLEAR_AHEAD: int = 0x33
TMCC2_DIALOG_CONTROL_ENGINEER_ACK_CLEAR_INBOUND: int = 0x34
TMCC2_DIALOG_CONTROL_ENGINEER_ACK_WELCOME_BACK: int = 0x35
TMCC2_DIALOG_CONTROL_ENGINEER_ACK_ID: int = 0x36

TMCC2_DIALOG_CONTROL_ENGINEER_FUEL_LEVEL: int = 0x3D
TMCC2_DIALOG_CONTROL_ENGINEER_FUEL_REFILLED: int = 0x3E
TMCC2_DIALOG_CONTROL_ENGINEER_SPEED: int = 0x3F
TMCC2_DIALOG_CONTROL_ENGINEER_WATER_LEVEL: int = 0x40
TMCC2_DIALOG_CONTROL_ENGINEER_WATER_REFILLED: int = 0x41

TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_OFF: int = 0x50
TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_ON: int = 0x51
TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_CLEAR: int = 0x52
TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_DEPARTED: int = 0x53
TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_TRANSIT: int = 0x54
TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_MAX_SPEED: int = 0x55

TMCC2_DIALOG_CONTROL_CONDUCTOR_NEXT_STOP: int = 0x68
TMCC2_DIALOG_CONTROL_CONDUCTOR_WATCH_YOUR_STEP: int = 0x69
TMCC2_DIALOG_CONTROL_CONDUCTOR_ALL_ABOARD: int = 0x6A
TMCC2_DIALOG_CONTROL_CONDUCTOR_TICKETS_PLEASE: int = 0x6B
TMCC2_DIALOG_CONTROL_CONDUCTOR_PREMATURE_STOP: int = 0x6C

TMCC2_DIALOG_CONTROL_STEWARD_WELCOME_ABOARD: int = 0x6D
TMCC2_DIALOG_CONTROL_STEWARD_FIRST_SEATING: int = 0x6E
TMCC2_DIALOG_CONTROL_STEWARD_SECOND_SEATING: int = 0x6F
TMCC2_DIALOG_CONTROL_STEWARD_LOUNGE_CAR_OPEN: int = 0x70

TMCC2_DIALOG_CONTROL_STATION_ARRIVING: int = 0x71
TMCC2_DIALOG_CONTROL_STATION_ARRIVED: int = 0x72
TMCC2_DIALOG_CONTROL_STATION_BOARDING: int = 0x73
TMCC2_DIALOG_CONTROL_STATION_DEPARTING: int = 0x74

TMCC2_DIALOG_CONTROL_PASSENGER_CAR_STARTUP: int = 0x75
TMCC2_DIALOG_CONTROL_PASSENGER_CAR_SHUTDOWN: int = 0x76

TMCC2_DIALOG_CONTROL_SPECIAL_GUEST_ENABLED: int = 0x7D
TMCC2_DIALOG_CONTROL_SPECIAL_GUEST_DISABLED: int = 0x7E


@unique
class TMCC2RailSoundsDialogControl(TMCC2ParameterEnum):
    CONVENTIONAL_SHUTDOWN = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_CONVENTIONAL_SHUTDOWN)
    SCENE_TWO = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SCENE_TWO)
    SCENE_FIVE = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SCENE_FIVE)
    SCENE_SEVEN = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SCENE_SEVEN)
    SHORT_HORN = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SHORT_HORN)
    TOWER_STARTUP = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_ENGINE_STARTUP)
    ENGINEER_DEPARTURE_DENIED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_DEPARTURE_DENIED)
    ENGINEER_DEPARTURE_GRANTED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_DEPARTURE_GRANTED)
    ENGINEER_DEPARTED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_HAVE_DEPARTED)
    ENGINEER_ALL_CLEAR = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ALL_CLEAR)
    TOWER_SPEED_STOP_HOLD = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_STOP_HOLD)
    TOWER_SPEED_RESTRICTED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_RESTRICTED_SPEED)
    TOWER_SPEED_SLOW = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_SLOW_SPEED)
    TOWER_SPEED_MEDIUM = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_MEDIUM_SPEED)
    TOWER_SPEED_LIMITED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_LIMITED_SPEED)
    TOWER_SPEED_NORMAL = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_NORMAL_SPEED)
    TOWER_SPEED_HIGHBALL = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_HIGHBALL_SPEED)
    ENGINEER_ARRIVING = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ARRIVING_SOON)
    ENGINEER_ARRIVED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_HAVE_ARRIVED)
    ENGINEER_SHUTDOWN = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_SHUTDOWN)
    ENGINEER_ID = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ID)
    ENGINEER_ACK = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ACK)
    ENGINEER_SPEED_STOP_HOLD = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_STOP_SPEED_ACK)
    ENGINEER_SPEED_RESTRICTED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_RESTRICTED_SPEED_ACK)
    ENGINEER_SPEED_SLOW = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_SLOW_SPEED_ACK)
    ENGINEER_SPEED_MEDIUM = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_MEDIUM_SPEED_ACK)
    ENGINEER_SPEED_LIMITED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_LIMITED_SPEED_ACK)
    ENGINEER_SPEED_NORMAL = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_NORMAL_SPEED_ACK)
    ENGINEER_SPEED_HIGHBALL = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_HIGHBALL_SPEED_ACK)
    ENGINEER_CONTEXT_DEPENDENT = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_CONTEXT_DEPENDENT)
    EMERGENCY_CONTEXT_DEPENDENT = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_EMERGENCY_CONTEXT_DEPENDENT)
    TOWER_CONTEXT_DEPENDENT = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_CONTEXT_DEPENDENT)
    TOWER_DEPARTURE_DENIED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_DEPARTURE_DENIED)
    TOWER_DEPARTURE_GRANTED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_DEPARTURE_GRANTED)
    TOWER_DEPARTED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_DEPARTED)
    TOWER_ALL_CLEAR = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_ALL_CLEAR)
    TOWER_ARRIVING = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_ARRIVING)
    TOWER_ARRIVED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_ARRIVED)
    TOWER_SHUTDOWN = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_TOWER_SHUT_DOWN)

    ENGINEER_ACK_STAND_BY = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ACK_STANDING_BY)
    ENGINEER_ACK_CLEARED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ACK_CLEARED_TO_GO)
    ENGINEER_ACK_CLEAR_AHEAD = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ACK_CLEAR_AHEAD)
    ENGINEER_ACK_CLEAR_INBOUND = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ACK_CLEAR_INBOUND)
    ENGINEER_ACK_WELCOME_BACK = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ACK_WELCOME_BACK)
    ENGINEER_ACK_ID = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_ACK_ID)
    ENGINEER_FUEL_LEVEL = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_FUEL_LEVEL)
    ENGINEER_SPEED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_SPEED)
    ENGINEER_FUEL_REFILLED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_FUEL_REFILLED)
    ENGINEER_WATER_LEVEL = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_WATER_LEVEL)
    ENGINEER_WATER_REFILLED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_ENGINEER_WATER_REFILLED)

    CONDUCTOR_NEXT_STOP = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_CONDUCTOR_NEXT_STOP)
    CONDUCTOR_WATCH_YOUR_STEP = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_CONDUCTOR_WATCH_YOUR_STEP)
    CONDUCTOR_ALL_ABOARD = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_CONDUCTOR_ALL_ABOARD)
    CONDUCTOR_TICKETS_PLEASE = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_CONDUCTOR_TICKETS_PLEASE)
    CONDUCTOR_PREMATURE_STOP = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_CONDUCTOR_PREMATURE_STOP)

    STEWARD_WELCOME_ABOARD = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_STEWARD_WELCOME_ABOARD)
    STEWARD_FIRST_SEATING = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_STEWARD_FIRST_SEATING)
    STEWARD_SECOND_SEATING = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_STEWARD_SECOND_SEATING)
    STEWARD_LOUNGE_CAR_OPEN = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_STEWARD_LOUNGE_CAR_OPEN)

    STATION_ARRIVING = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_STATION_ARRIVING)
    STATION_ARRIVED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_STATION_ARRIVED)
    STATION_BOARDING = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_STATION_BOARDING)
    STATION_DEPARTING = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_STATION_DEPARTING)

    PASSENGER_CAR_STARTUP = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_PASSENGER_CAR_STARTUP)
    PASSENGER_CAR_SHUTDOWN = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_PASSENGER_CAR_SHUTDOWN)

    SPECIAL_GUEST_ENABLED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SPECIAL_GUEST_ENABLED)
    SPECIAL_GUEST_DISABLED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SPECIAL_GUEST_DISABLED)

    SEQUENCE_OFF = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_OFF)
    SEQUENCE_ON = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_ON)
    SEQUENCE_CLEAR = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_CLEAR)
    SEQUENCE_DEPARTED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_DEPARTED)
    SEQUENCE_TRANSIT = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_TRANSIT)
    SEQUENCE_MAX_SPEED = MultiByteCommandDef(TMCC2_DIALOG_CONTROL_SEQUENCE_CONTROL_MAX_SPEED)


"""
    Word #2 - RailSounds Effects trigger controls (index 0x4)
"""
TMCC2_RS_EFFECTS_PRIME_MOVER_OFF: int = 0x10
TMCC2_RS_EFFECTS_PRIME_MOVER_ON: int = 0x11
TMCC2_RS_EFFECTS_MASTER_VOLUME_DOWN: int = 0x12
TMCC2_RS_EFFECTS_MASTER_VOLUME_UP: int = 0x13
TMCC2_RS_EFFECTS_BLEND_VOLUME_DOWN: int = 0x14
TMCC2_RS_EFFECTS_BLEND_VOLUME_UP: int = 0x15
TMCC2_RS_EFFECTS_CYLINDER_CLEARING_ON: int = 0x20
TMCC2_RS_EFFECTS_CYLINDER_CLEARING_OFF: int = 0x21
TMCC2_RS_EFFECTS_WHEEL_SLIP_TRIGGER: int = 0x22
TMCC2_RS_EFFECTS_STANDBY_WARNING_BELL: int = 0x23
TMCC2_RS_EFFECTS_STANDBY_MODE_DISABLE: int = 0x24
TMCC2_RS_EFFECTS_STANDBY_MODE_ENABLE: int = 0x25
TMCC2_RS_EFFECTS_FORCE_COUPLER_IMPACT_COMPRESS: int = 0x26
TMCC2_RS_EFFECTS_FORCE_COUPLER_IMPACT_STRETCH: int = 0x27
TMCC2_RS_EFFECTS_CIRCUIT_BREAKER_MAIN_LIGHTS: int = 0x28
TMCC2_RS_EFFECTS_CIRCUIT_BREAKER_CAB_LIGHTS: int = 0x29
TMCC2_RS_EFFECTS_CIRCUIT_BREAKER_WORK_LIGHTS: int = 0x2A
TMCC2_RS_EFFECTS_SEQUENCE_CONTROL_OFF: int = 0x2C
TMCC2_RS_EFFECTS_SEQUENCE_CONTROL_ON: int = 0x2D

TMCC2_RS_EFFECTS_RESET_ODOMETER: int = 0x30
TMCC2_RS_EFFECTS_INCREMENT_FUEL_LOAD: int = 0x31

TMCC2_RS_EFFECTS_SOUND_SYSTEM_OFF = TMCC2_SOUND_OFF_COMMAND
TMCC2_RS_EFFECTS_SOUND_SYSTEM_ON = TMCC2_SOUND_ON_COMMAND


@unique
class TMCC2RailSoundsEffectsControl(TMCC2ParameterEnum):
    ADD_FUEL = MultiByteCommandDef(TMCC2_RS_EFFECTS_INCREMENT_FUEL_LOAD)
    BLEND_DOWN = MultiByteCommandDef(TMCC2_RS_EFFECTS_BLEND_VOLUME_DOWN)
    BLEND_UP = MultiByteCommandDef(TMCC2_RS_EFFECTS_BLEND_VOLUME_UP)
    CAB_BREAKER = MultiByteCommandDef(TMCC2_RS_EFFECTS_CIRCUIT_BREAKER_CAB_LIGHTS)
    COUPLER_COMPRESS = MultiByteCommandDef(TMCC2_RS_EFFECTS_FORCE_COUPLER_IMPACT_COMPRESS)
    COUPLER_STRETCH = MultiByteCommandDef(TMCC2_RS_EFFECTS_FORCE_COUPLER_IMPACT_STRETCH)
    CYLINDER_OFF = MultiByteCommandDef(TMCC2_RS_EFFECTS_CYLINDER_CLEARING_OFF)
    CYLINDER_ON = MultiByteCommandDef(TMCC2_RS_EFFECTS_CYLINDER_CLEARING_ON)
    MAIN_BREAKER = MultiByteCommandDef(TMCC2_RS_EFFECTS_CIRCUIT_BREAKER_MAIN_LIGHTS)
    PRIME_OFF = MultiByteCommandDef(TMCC2_RS_EFFECTS_PRIME_MOVER_OFF)
    PRIME_ON = MultiByteCommandDef(TMCC2_RS_EFFECTS_PRIME_MOVER_ON)
    RESET_ODOMETER = MultiByteCommandDef(TMCC2_RS_EFFECTS_RESET_ODOMETER)
    SEQUENCE_CONTROL_OFF = MultiByteCommandDef(TMCC2_RS_EFFECTS_SEQUENCE_CONTROL_OFF)
    SEQUENCE_CONTROL_ON = MultiByteCommandDef(TMCC2_RS_EFFECTS_SEQUENCE_CONTROL_ON)
    STANDBY_BELL = MultiByteCommandDef(TMCC2_RS_EFFECTS_STANDBY_WARNING_BELL)
    STANDBY_DISABLE = MultiByteCommandDef(TMCC2_RS_EFFECTS_STANDBY_MODE_DISABLE)
    STANDBY_ENABLE = MultiByteCommandDef(TMCC2_RS_EFFECTS_STANDBY_MODE_ENABLE)
    VOLUME_DOWN_RS = MultiByteCommandDef(TMCC2_RS_EFFECTS_MASTER_VOLUME_DOWN)
    VOLUME_UP_RS = MultiByteCommandDef(TMCC2_RS_EFFECTS_MASTER_VOLUME_UP)
    WHEEL_SLIP = MultiByteCommandDef(TMCC2_RS_EFFECTS_WHEEL_SLIP_TRIGGER)
    WORK_BREAKER = MultiByteCommandDef(TMCC2_RS_EFFECTS_CIRCUIT_BREAKER_WORK_LIGHTS)


"""
    Word #2 - Sound masking controls (index 0x6)
"""
TMCC2_MASKING_DIALOG_NC_SIGNAL_NC: int = 0x00
TMCC2_MASKING_DIALOG_PLAY_ALWAYS_SIGNAL_NC: int = 0x01
TMCC2_MASKING_DIALOG_PLAY_NEVER_SIGNAL_NC: int = 0x02
TMCC2_MASKING_DIALOG_DEFAULT_SIGNAL_NC: int = 0x03

TMCC2_MASKING_DIALOG_NC_SIGNAL_PLAY_ALWAYS: int = 0x04
TMCC2_MASKING_DIALOG_PLAY_ALWAYS_SIGNAL_PLAY_ALWAYS: int = 0x05
TMCC2_MASKING_DIALOG_PLAY_NEVER_SIGNAL_PLAY_ALWAYS: int = 0x06
TMCC2_MASKING_DIALOG_DEFAULT_SIGNAL_PLAY_ALWAYS: int = 0x07

TMCC2_MASKING_DIALOG_NC_SIGNAL_PLAY_NEVER: int = 0x08
TMCC2_MASKING_DIALOG_PLAY_ALWAYS_SIGNAL_PLAY_NEVER: int = 0x09
TMCC2_MASKING_DIALOG_PLAY_NEVER_SIGNAL_PLAY_NEVER: int = 0x0A
TMCC2_MASKING_DIALOG_DEFAULT_SIGNAL_PLAY_NEVER: int = 0x0B

TMCC2_MASKING_DIALOG_NC_SIGNAL_DEFAULT: int = 0x0C
TMCC2_MASKING_DIALOG_PLAY_ALWAYS_SIGNAL_DEFAULT: int = 0x0D
TMCC2_MASKING_DIALOG_PLAY_NEVER_SIGNAL_DEFAULT: int = 0x0E
TMCC2_MASKING_DIALOG_DEFAULT_SIGNAL_DEFAULT: int = 0x0F

TMCC2_BRAKE_SQUEAL_DISABLE: int = 0x20
TMCC2_BRAKE_SQUEAL_ENABLE: int = 0x21


@unique
class TMCC2MaskingControl(TMCC2ParameterEnum):
    NC_NC = MultiByteCommandDef(TMCC2_MASKING_DIALOG_NC_SIGNAL_NC)
    ALWAYS_NC = MultiByteCommandDef(TMCC2_MASKING_DIALOG_PLAY_ALWAYS_SIGNAL_NC)
    NEVER_NC = MultiByteCommandDef(TMCC2_MASKING_DIALOG_PLAY_NEVER_SIGNAL_NC)
    DEFAULT_NC = MultiByteCommandDef(TMCC2_MASKING_DIALOG_DEFAULT_SIGNAL_NC)
    NC_ALWAYS = MultiByteCommandDef(TMCC2_MASKING_DIALOG_NC_SIGNAL_PLAY_ALWAYS)
    ALWAYS_ALWAYS = MultiByteCommandDef(TMCC2_MASKING_DIALOG_PLAY_ALWAYS_SIGNAL_PLAY_ALWAYS)
    NEVER_ALWAYS = MultiByteCommandDef(TMCC2_MASKING_DIALOG_PLAY_NEVER_SIGNAL_PLAY_ALWAYS)
    DEFAULT_ALWAYS = MultiByteCommandDef(TMCC2_MASKING_DIALOG_DEFAULT_SIGNAL_PLAY_ALWAYS)
    NC_NEVER = MultiByteCommandDef(TMCC2_MASKING_DIALOG_NC_SIGNAL_PLAY_NEVER)
    ALWAYS_NEVER = MultiByteCommandDef(TMCC2_MASKING_DIALOG_PLAY_ALWAYS_SIGNAL_PLAY_NEVER)
    NEVER_NEVER = MultiByteCommandDef(TMCC2_MASKING_DIALOG_PLAY_NEVER_SIGNAL_PLAY_NEVER)
    DEFAULT_NEVER = MultiByteCommandDef(TMCC2_MASKING_DIALOG_DEFAULT_SIGNAL_PLAY_NEVER)
    NC_DEFAULT = MultiByteCommandDef(TMCC2_MASKING_DIALOG_NC_SIGNAL_DEFAULT)
    PLAY_DEFAULT = MultiByteCommandDef(TMCC2_MASKING_DIALOG_PLAY_ALWAYS_SIGNAL_DEFAULT)
    NEVER_DEFAULT = MultiByteCommandDef(TMCC2_MASKING_DIALOG_PLAY_NEVER_SIGNAL_DEFAULT)
    DEFAULT_DEFAULT = MultiByteCommandDef(TMCC2_MASKING_DIALOG_DEFAULT_SIGNAL_DEFAULT)
    BRAKE_SQUEAL_ENABLE = MultiByteCommandDef(TMCC2_BRAKE_SQUEAL_ENABLE)
    BRAKE_SQUEAL_DISABLE = MultiByteCommandDef(TMCC2_BRAKE_SQUEAL_DISABLE)


"""
    Word #2 - Effects controls (index 0xC)
"""
TMCC2_EFFECTS_CONTROL_SMOKE_OFF: int = 0x00
TMCC2_EFFECTS_CONTROL_SMOKE_LOW: int = 0x01
TMCC2_EFFECTS_CONTROL_SMOKE_MEDIUM: int = 0x02
TMCC2_EFFECTS_CONTROL_SMOKE_HIGH: int = 0x03
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_UP_CAB2: int = 0x10
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_DOWN_CAB2: int = 0x11
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_UP_CAB2: int = 0x12
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_DOWN_CAB2: int = 0x13
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_UP: int = 0x19
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_DOWN: int = 0x18
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_UP: int = 0x1B
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_DOWN: int = 0x1A
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_BOTH_UP: int = 0x1F
TMCC2_EFFECTS_CONTROL_PANTOGRAPH_BOTH_DOWN: int = 0x1E
TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_OPEN_CAB2: int = 0x20
TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_CLOSE_CAB2: int = 0x21
TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_OPEN_CAB2: int = 0x22
TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_CLOSE_CAB2: int = 0x23
TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_CLOSE: int = 0x28
TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_OPEN: int = 0x29
TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_CLOSE: int = 0x2A
TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_OPEN: int = 0x2B
TMCC2_EFFECTS_CONTROL_SUBWAY_BOTH_DOOR_CLOSE: int = 0x2E
TMCC2_EFFECTS_CONTROL_SUBWAY_BOTH_DOOR_OPEN: int = 0x2F
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
TMCC2_EFFECTS_CONTROL_SCENE_ZERO: int = 0x3C
TMCC2_EFFECTS_CONTROL_SCENE_ONE: int = 0x3D
TMCC2_EFFECTS_CONTROL_SCENE_TWO: int = 0x3E
TMCC2_EFFECTS_CONTROL_SCENE_THREE: int = 0x3F
TMCC2_EFFECTS_CONTROL_COAL_EMPTY: int = 0x50
TMCC2_EFFECTS_CONTROL_COAL_FULL: int = 0x51
TMCC2_EFFECTS_CONTROL_COAL_EMPTYING: int = 0x52
TMCC2_EFFECTS_CONTROL_COAL_FILLING: int = 0x53


@unique
class TMCC2EffectsControl(TMCC2ParameterEnum):
    PANTO_FRONT_DOWN = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_DOWN)
    PANTO_FRONT_UP = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_PANTOGRAPH_FRONT_UP)
    PANTO_REAR_DOWN = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_DOWN)
    PANTO_REAR_UP = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_PANTOGRAPH_REAR_UP)
    PANTO_BOTH_DOWN = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_PANTOGRAPH_BOTH_DOWN)
    PANTO_BOTH_UP = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_PANTOGRAPH_BOTH_UP)
    SMOKE_HIGH = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SMOKE_HIGH)
    SMOKE_LOW = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SMOKE_LOW)
    SMOKE_MEDIUM = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SMOKE_MEDIUM)
    SMOKE_OFF = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SMOKE_OFF)
    STOCK_FRED_OFF = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_FRED_OFF)
    STOCK_FRED_ON = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_FRED_ON)
    STOCK_GAME_OFF = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_GAME_OFF)
    STOCK_GAME_ON = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_GAME_ON)
    STOCK_LOAD = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_LOAD)
    STOCK_OPTION_ONE_OFF = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_ONE_OFF)
    STOCK_OPTION_ONE_ON = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_ONE_ON)
    STOCK_OPTION_ONE_TWO = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_TWO_OFF)
    STOCK_OPTION_TWO_ON = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_OPTION_TWO_ON)
    STOCK_UNLOAD = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_UNLOAD)
    STOCK_WHEEL_OFF = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_FLAT_WHEEL_OFF)
    STOCK_WHEEL_ON = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_STOCK_CAR_FLAT_WHEEL_ON)
    SUBWAY_LEFT_DOOR_CLOSE = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_CLOSE)
    SUBWAY_LEFT_DOOR_OPEN = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SUBWAY_LEFT_DOOR_OPEN)
    SUBWAY_RIGHT_DOOR_CLOSE = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_CLOSE)
    SUBWAY_RIGHT_DOOR_OPEN = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SUBWAY_RIGHT_DOOR_OPEN)
    SUBWAY_BOTH_DOOR_CLOSE = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SUBWAY_BOTH_DOOR_CLOSE)
    SUBWAY_BOTH_DOOR_OPEN = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_SUBWAY_BOTH_DOOR_OPEN)
    COAL_EMPTY = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_COAL_EMPTY)
    COAL_FULL = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_COAL_FULL)
    COAL_EMPTYING = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_COAL_EMPTYING)
    COAL_FILLING = MultiByteCommandDef(TMCC2_EFFECTS_CONTROL_COAL_FILLING)


"""
    Word #2 - Lighting controls (index 0xD)
"""
TMCC2_LIGHTING_CONTROL_CAB_LIGHT_AUTO: int = 0xF2
TMCC2_LIGHTING_CONTROL_CAB_LIGHT_OFF: int = 0xF0
TMCC2_LIGHTING_CONTROL_CAB_LIGHT_ON: int = 0xF1
TMCC2_LIGHTING_CONTROL_CAB_LIGHT_TOGGLE: int = 0xF3
TMCC2_LIGHTING_CONTROL_CAR_LIGHT_AUTO: int = 0xFA
TMCC2_LIGHTING_CONTROL_CAR_LIGHT_OFF: int = 0xF8
TMCC2_LIGHTING_CONTROL_CAR_LIGHT_ON: int = 0xF9
TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_OFF: int = 0xC0
TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_OFF_PULSE_ON_WITH_HORN: int = 0xC1
TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_ON: int = 0xC3
TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_ON_PULSE_OFF_WITH_HORN: int = 0xC2
TMCC2_LIGHTING_CONTROL_DOGHOUSE_LIGHT_OFF: int = 0xA0
TMCC2_LIGHTING_CONTROL_DOGHOUSE_LIGHT_ON: int = 0xA1
TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_AUTO: int = 0xD2
TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_OFF: int = 0xD0
TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_ON: int = 0xD1
TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_OFF: int = 0xB0
TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_ON: int = 0xB1
TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_AUTO: int = 0xB2
TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_OFF: int = 0xC8
TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_ON: int = 0xC9
TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_AUTO: int = 0xCA
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
TMCC2_LIGHTING_CONTROL_WORK_LIGHT_OFF: int = 0xD8
TMCC2_LIGHTING_CONTROL_WORK_LIGHT_ON: int = 0xD9
TMCC2_LIGHTING_CONTROL_WORK_LIGHT_AUTO: int = 0xDA


@unique
class TMCC2LightingControl(TMCC2ParameterEnum):
    CAB_AUTO = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_CAB_LIGHT_AUTO)
    CAB_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_CAB_LIGHT_OFF)
    CAB_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_CAB_LIGHT_ON)
    CAB_TOGGLE = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_CAB_LIGHT_TOGGLE)
    CAR_AUTO = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_CAR_LIGHT_AUTO)
    CAR_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_CAR_LIGHT_OFF)
    CAR_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_CAR_LIGHT_ON)
    DITCH_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_OFF)
    DITCH_OFF_PULSE_ON_WITH_HORN = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_OFF_PULSE_ON_WITH_HORN)
    DITCH_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_ON)
    DITCH_ON_PULSE_OFF_WITH_HORN = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_DITCH_LIGHT_ON_PULSE_OFF_WITH_HORN)
    DOGHOUSE_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_DOGHOUSE_LIGHT_OFF)
    DOGHOUSE_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_DOGHOUSE_LIGHT_ON)
    GROUND_AUTO = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_AUTO)
    GROUND_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_OFF)
    GROUND_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_GROUND_LIGHT_ON)
    HAZARD_AUTO = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_AUTO)
    HAZARD_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_OFF)
    HAZARD_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_HAZARD_LIGHT_ON)
    LOCO_MARKER_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_OFF)
    LOCO_MARKER_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_ON)
    LOCO_MARKER_AUTO = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_LOCO_MARKER_LIGHT_AUTO)
    MARS_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_MARS_LIGHT_OFF)
    MARS_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_MARS_LIGHT_ON)
    RULE_17_AUTO = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_RULE_17_AUTO)
    RULE_17_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_RULE_17_OFF)
    RULE_17_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_RULE_17_ON)
    STROBE_LIGHT_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_OFF)
    STROBE_LIGHT_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_ON_SINGLE_FLASH)
    STROBE_LIGHT_ON_DOUBLE = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_STROBE_LIGHT_ON_DOUBLE_FLASH)
    TENDER_MARKER_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_TENDER_MARKER_LIGHT_OFF)
    TENDER_MARKER_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_TENDER_MARKER_LIGHT_ON)
    WORK_AUTO = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_WORK_LIGHT_AUTO)
    WORK_OFF = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_WORK_LIGHT_OFF)
    WORK_ON = MultiByteCommandDef(TMCC2_LIGHTING_CONTROL_WORK_LIGHT_ON)


# R4LC Commands; modify Engine eeprom
@unique
class UnitAssignment(Mixins, IntEnum):
    SINGLE_FORWARD = 0b000
    SINGLE_REVERSE = 0b100
    HEAD_FORWARD = 0b001
    HEAD_REVERSE = 0b101
    MIDDLE_FORWARD = 0b010
    MIDDLE_REVERSE = 0b110
    TAIL_FORWARD = 0b011
    TAIL_REVERSE = 0b111


# index values,
TMCC2_SET_ENGINE_ADDRESS_INDEX: int = 0x40
TMCC2_SET_ENGINE_STALL_INDEX: int = 0x41
TMCC2_SET_TRAIN_ADDRESS_INDEX: int = 0x42
TMCC2_SET_TRAIN_UNIT_INDEX: int = 0x43
TMCC2_SET_MAX_SPEED_INDEX: int = 0x44
TMCC2_SET_DIRECTION_INDEX: int = 0x45
TMCC2_SET_FLAGS_INDEX: int = 0x46
TMCC2_SET_CONTROL_INDEX: int = 0x47
TMCC2_SET_ENGINE_TYPE_INDEX: int = 0x48
TMCC2_SET_SPEED_RESOLUTION_INDEX: int = 0x49
TMCC2_SET_VARIABLE_RESOLUTION_INDEX: int = 0x4A
TMCC2_SET_INDIRECT_INDEX: int = 0x4F


@unique
class TMCC2R4LCIndex(Mixins, IntEnum):
    ENGINE_ADDRESS = TMCC2_SET_ENGINE_ADDRESS_INDEX
    ENGINE_STALL = TMCC2_SET_ENGINE_STALL_INDEX
    TRAIN_ADDRESS = TMCC2_SET_TRAIN_ADDRESS_INDEX
    TRAIN_UNIT = TMCC2_SET_TRAIN_UNIT_INDEX
    MAX_SPEED = TMCC2_SET_MAX_SPEED_INDEX
    DIRECTION = TMCC2_SET_DIRECTION_INDEX
    FLAGS = TMCC2_SET_FLAGS_INDEX
    CONTROL = TMCC2_SET_CONTROL_INDEX
    ENGINE_TYPE = TMCC2_SET_ENGINE_TYPE_INDEX
    SPEED_RESOLUTION = TMCC2_SET_SPEED_RESOLUTION_INDEX
    VARIABLE_RESOLUTION = TMCC2_SET_VARIABLE_RESOLUTION_INDEX
    INDIRECT = TMCC2_SET_INDIRECT_INDEX


# I don't like using the same constants for the "data" enums, but for now...
# This will probably stick, as we are really only going to use these to
# echo commands
@unique
class TMCC2R4LCEnum(TMCC2MultiByteEnum):
    ENGINE_ADDRESS = MultiByteCommandDef(TMCC2_SET_ENGINE_ADDRESS_INDEX, d_min=1, d_max=99)
    ENGINE_STALL = MultiByteCommandDef(TMCC2_SET_ENGINE_STALL_INDEX)
    TRAIN_ADDRESS = MultiByteCommandDef(TMCC2_SET_TRAIN_ADDRESS_INDEX, d_max=99)
    TRAIN_UNIT = MultiByteCommandDef(TMCC2_SET_TRAIN_UNIT_INDEX, d_max=7)
    MAX_SPEED = MultiByteCommandDef(TMCC2_SET_MAX_SPEED_INDEX, d_min=32, d_max=200)
    DIRECTION = MultiByteCommandDef(TMCC2_SET_DIRECTION_INDEX, d_max=255)
    FLAGS = MultiByteCommandDef(TMCC2_SET_FLAGS_INDEX, d_max=63)
    CONTROL = MultiByteCommandDef(TMCC2_SET_CONTROL_INDEX, d_max=1)
    ENGINE_TYPE = MultiByteCommandDef(TMCC2_SET_ENGINE_TYPE_INDEX, d_max=7)
    SPEED_RESOLUTION = MultiByteCommandDef(TMCC2_SET_SPEED_RESOLUTION_INDEX, d_max=7)
    VARIABLE_RESOLUTION = MultiByteCommandDef(TMCC2_SET_VARIABLE_RESOLUTION_INDEX)
    INDIRECT = MultiByteCommandDef(TMCC2_SET_INDIRECT_INDEX)


#
# Variable length Multibyte commands
#
class VariableCommandDef(MultiByteCommandDef):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        command_bits: int,
        num_data_bytes: int,
        data_bytes: List[int] = None,
        d_min: int = 0,
        d_max: int = 0,
    ) -> None:
        super().__init__(command_bits, d_min=d_min, d_max=d_max)
        self._num_data_bytes = num_data_bytes
        self._data_bytes = data_bytes

    @property
    def num_data_bytes(self) -> int:
        return self._num_data_bytes

    @property
    def lsb(self) -> int:
        return 0x00FF & self.bits

    @property
    def msb(self) -> int:
        return (0xFF00 & self.bits) >> 8


TMCC2_VARIABLE_INDEX: int = 0x6F

TMCC2_SET_MASTER_VOLUME: int = 0xB000
TMCC2_SET_BLEND_VOLUME: int = 0xB001
TMCC2_SET_VOLUME_DIRECT: int = 0xB004
TMCC2_DCDS_FACTORY_DEFAULT = 0xF000
TMCC2_DCDS_STORE = 0xF001


class TMCC2VariableEnum(TMCC2MultiByteEnum):
    MASTER_VOLUME = VariableCommandDef(TMCC2_SET_MASTER_VOLUME, 1)
    BLEND_VOLUME = VariableCommandDef(TMCC2_SET_BLEND_VOLUME, 1)
    VOLUME_DIRECT = VariableCommandDef(TMCC2_SET_BLEND_VOLUME, 2)
    FACTORY_DEFAULT = VariableCommandDef(TMCC2_DCDS_FACTORY_DEFAULT, 2, [0xEF, 0xBF])
    STORE = VariableCommandDef(TMCC2_DCDS_FACTORY_DEFAULT, 1)

    @property
    def num_data_bytes(self) -> int:
        return self.value.num_data_bytes
