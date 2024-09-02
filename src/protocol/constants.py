from enum import Enum, verify, UNIQUE, IntFlag
from typing import Dict, Union


@verify(UNIQUE)
class SwitchState(Enum):
    """
        Switch State
    """
    THROUGH = 1
    OUT = 2
    SET_ADDRESS = 3

    @classmethod
    def by_name(cls, name: str) -> Enum | None:
        orig_name = name = name.strip()
        if name in cls.__members__:
            return cls[name]
        # fall back to case-insensitive s
        name = name.lower()
        for k, v in cls.__members__.items():
            if k.lower() == name:
                return v
        else:
            if name:
                raise ValueError(f"'{orig_name}' is not a valid {cls.__name__}")
            else:
                raise ValueError(f"None/Empty is not a valid {cls.__name__}")


@verify(UNIQUE)
class CommandFormat(Enum):
    TMCC1 = 1
    TMCC2 = 2


@verify(UNIQUE)
class AuxChoice(Enum):
    AUX1 = 1
    AUX2 = 2
    ON = 3
    OFF = 4
    SET_ADDRESS = 5


@verify(UNIQUE)
class AuxOption(Enum):
    ON = 1
    OFF = 2
    OPTION1 = 3
    OPTION2 = 4
    NUMERIC = 5


"""
    General Constants
"""
DEFAULT_BAUDRATE: int = 9600
DEFAULT_PORT: str = "/dev/ttyUSB0"

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
TMCC1_ACC_SET_ADDRESS_COMMAND: int = 0x802B

TMCC1_ACC_AUX_1_OFF_COMMAND: int = 0x8008
TMCC1_ACC_AUX_1_OPTION_1_COMMAND: int = 0x8009  # Cab1 Aux1 button
TMCC1_ACC_AUX_1_OPTION_2_COMMAND: int = 0x800A
TMCC1_ACC_AUX_1_ON_COMMAND: int = 0x800B

TMCC1_ACC_AUX_2_OFF_COMMAND: int = 0x800C
TMCC1_ACC_AUX_2_OPTION_1_COMMAND: int = 0x800D  # Cab1 Aux2 button
TMCC1_ACC_AUX_2_OPTION_2_COMMAND: int = 0x800E
TMCC1_ACC_AUX_2_ON_COMMAND: int = 0x800F

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
    AuxChoice.ON: TMCC1_ACC_ON_COMMAND,
    AuxChoice.OFF: TMCC1_ACC_OFF_COMMAND,
    AuxChoice.SET_ADDRESS: TMCC1_ACC_SET_ADDRESS_COMMAND,
}

"""
    Legacy/TMCC2 Protocol Constants
"""
LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX: int = 0xFA
LEGACY_ROUTE_COMMAND: int = 0x00FD

# Engine/Train 2 digit address are first 7 bits of first byte
LEGACY_ENGINE_COMMAND_PREFIX: int = 0xF8
LEGACY_TRAIN_COMMAND_PREFIX: int = 0xF9

# TMCC2 Commands with Bit 9 = "0"
TMCC2_SET_ABSOLUTE_SPEED_COMMAND: int = 0x0000  # encode speed in last byte (0 - 199)
TMCC2_SET_MOMENTUM_COMMAND: int = 0x00C8  # encode momentum in last 3 bits (0 - 7)
TMCC2_SET_BRAKE_COMMAND: int = 0x00E0  # encode brake level in last 3 bits (0 - 7)
TMCC2_SET_BOOST_COMMAND: int = 0x00E8  # encode boost level in last 3 bits (0 - 7)
TMCC2_SET_TRAIN_BRAKE_COMMAND: int = 0x00F0  # encode train brake in last 3 bits (0 - 7)
TMCC2_STALL_COMMAND: int = 0x00F8
TMCC2_STOP_IMMEDIATE_COMMAND: int = 0x00FB

# TMCC2 Commands with Bit 9 = "1"
TMCC2_HALT_COMMAND: int = 0x01AB
TMCC2_BELL_OFF_COMMAND: int = 0x01F4
TMCC2_BELL_ON_COMMAND: int = 0x01F5

LEGACY_PARAMETER_COMMAND_PREFIX: int = 0xFB


@verify(UNIQUE)
class TMCC2CommandScope(IntFlag):
    ENGINE = LEGACY_ENGINE_COMMAND_PREFIX
    TRAIN = LEGACY_TRAIN_COMMAND_PREFIX
    PARAMETER = LEGACY_PARAMETER_COMMAND_PREFIX
    EXTENDED = LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX


@verify(UNIQUE)
class EngineOption(IntFlag):
    ABSOLUTE_SPEED = TMCC2_SET_ABSOLUTE_SPEED_COMMAND
    MOMENTUM = TMCC2_SET_MOMENTUM_COMMAND
    BRAKE_LEVEL = TMCC2_SET_BRAKE_COMMAND
    BOOST_LEVEL = TMCC2_SET_BOOST_COMMAND
    TRAIN_BRAKE = TMCC2_SET_TRAIN_BRAKE_COMMAND
    SET_STALL = TMCC2_STALL_COMMAND
    STOP_IMMEDIATE = TMCC2_STOP_IMMEDIATE_COMMAND
    SYSTEM_HALT = TMCC2_HALT_COMMAND
    BELL_OFF = TMCC2_BELL_OFF_COMMAND
    BELL_ON_COMMAND = TMCC2_BELL_ON_COMMAND
