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


"""
    TMCC1 Protocol Constants
"""
TMCC1_COMMAND_PREFIX: int = 0xFE

TMCC1_HALT_COMMAND: int = 0xFFFF

TMCC1_ROUTE_COMMAND: int = 0xD01F

TMCC1_SWITCH_THROUGH_COMMAND: int = 0x4000
TMCC1_SWITCH_OUT_COMMAND: int = 0x401F

TMCC1_ACC_AUX_1_COMMAND: int = 0x8009
TMCC1_ACC_AUX_2_COMMAND: int = 0x800D

"""
    Legacy/TMCC2 Protocol Constants
"""
LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX: int = 0xFA

LEGACY_EXTENDED_ROUTE_COMMAND: int = 0x00FD
