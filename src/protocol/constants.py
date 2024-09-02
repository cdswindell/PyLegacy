from enum import Enum, verify, UNIQUE


@verify(UNIQUE)
class SwitchState(Enum):
    """
        Switch State
    """
    THROUGH = 1
    OUT = 2

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
class TMCC2CommandScope(Enum):
    ENGINE = 1
    TRAIN = 2
    PARAMETER = 3
    EXTENDED = 4


@verify(UNIQUE)
class CommandFormat(Enum):
    TMCC1 = 1
    TMCC2 = 2


"""
    General Constants
"""
DEFAULT_BAUDRATE: int = 9600
DEFAULT_PORT: str = "/dev/ttyUSB0"

"""
    TMCC1 Protocol Constants
"""
TMCC1_COMMAND_PREFIX: bytes = int(0xFE).to_bytes(1, 'big')

TMCC1_HALT_COMMAND: int = 0xFFFF
TMCC1_ROUTE_COMMAND: int = 0xD01F
TMCC1_SWITCH_THROUGH_COMMAND: int = 0x4000
TMCC1_SWITCH_OUT_COMMAND: int = 0x401F
TMCC1_ACC_AUX_1_COMMAND: int = 0x8009
TMCC1_ACC_AUX_2_COMMAND: int = 0x800D

"""
    Legacy/TMCC2 Protocol Constants
"""
LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX: bytes = int(0xFA).to_bytes(1, 'big')
LEGACY_ROUTE_COMMAND: int = 0x00FD

# Engine/Train 2 digit address are first 7 bits of first byte
LEGACY_ENGINE_COMMAND_PREFIX: bytes = int(0xF8).to_bytes(1, 'big')
LEGACY_TRAIN_COMMAND_PREFIX: bytes = int(0xF9).to_bytes(1, 'big')

# TMCC2 Commands with Bit 9 = "0"
TMCC2_SET_ABSOLUTE_SPEED_COMMAND: int = 0x0000  # encode speed in last byte (0 - 199)
TMCC2_SET_MOMENTUM_COMMAND: int = 0x00C8  # encode momentum in last 3 bits (0 - 7)
TMCC2_SET_BRAKE_COMMAND: int = 0x00E0  # encode brake level in last 3 bits (0 - 7)
TMCC2_SET_BOOST_COMMAND: int = 0x00E8  # encode boost level in last 3 bits (0 - 7)
TMCC2_SET_TRAIN_BRAKE_COMMAND: int = 0x00F0  # encode train brake in last 3 bits (0 - 7)
TMCC2_STALL_COMMAND: int = 0x00F8
TMCC2_STOP_IMMEDIATE_COMMAND: int = 0x00FB

# TMCC2 Commands with Bit 9 = "1"
LEGACY_HALT_COMMAND: int = 0x01AB

LEGACY_PARAMETER_COMMAND_PREFIX: bytes = int(0xFB).to_bytes(1, 'big')

"""
    map TMCC2CommandScope to command prefixes
"""
TMCC2_COMMAND_SCOPE_TO_COMMAND_PREFIX = {
    TMCC2CommandScope.ENGINE: LEGACY_ENGINE_COMMAND_PREFIX,
    TMCC2CommandScope.TRAIN: LEGACY_TRAIN_COMMAND_PREFIX,
    TMCC2CommandScope.PARAMETER: LEGACY_PARAMETER_COMMAND_PREFIX,
    TMCC2CommandScope.EXTENDED: LEGACY_ENGINE_COMMAND_PREFIX
}
