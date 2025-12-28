from __future__ import annotations

import sys
from enum import Enum, IntEnum, unique
from typing import Any, Dict, List, Set

if sys.version_info >= (3, 11):
    from typing import Self

"""
    General Constants
"""
DEFAULT_BAUDRATE: int = 9600
DEFAULT_VALID_BAUDRATES: List[int] = [9600, 19200, 38400, 57600, 115200]
DEFAULT_PORT: str = "/dev/ttyUSB0"
DEFAULT_ADDRESS: int = 99
BROADCAST_ADDRESS: int = 99
BROADCAST_TOPIC = "BROADCAST"
PROGRAM_NAME = "PyTrain"
PROGRAM_BASE = "pytrain"

DEFAULT_BASE_PORT: int = 50001

DEFAULT_SERVER_PORT: int = 5110  # unassigned by IANA as of 1/1/2025
DEFAULT_PULSE = 5  # send heartbeat periodically as proof of life

DEFAULT_QUEUE_SIZE: int = 2**12  # 4,096 entries

DEFAULT_SER2_THROTTLE_DELAY: int = 50  # milliseconds
DEFAULT_BASE_THROTTLE_DELAY: int = 50
DEFAULT_DURATION_INTERVAL_MSEC: int = 50
MINIMUM_DURATION_INTERVAL_MSEC: int = 20

DEFAULT_ENGINE_LABOR = 12

# AVAHI Service Constants
SERVICE_TYPE = f"_{PROGRAM_NAME.lower()}._tcp.local."
SERVICE_NAME = f"{PROGRAM_NAME}-Server.{SERVICE_TYPE}"


def all_descendants(cls):
    """
    Recursively retrieves all descendant classes for a given class.

    This function explores the inheritance hierarchy of a class and identifies
    all the subclasses derived from it, including nested subclasses at all
    levels of inheritance.

    Args:
        cls: The class whose descendants are to be retrieved.

    Returns:
        A list of all descendant classes including direct and indirect subclasses
        of the input class.
    """
    descendants = []
    for subclass in cls.__subclasses__():
        descendants.append(subclass)
        descendants.extend(all_descendants(subclass))
    return descendants


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
        # fall back to case-insensitive
        name = name.upper()
        for k, v in cls.__members__.items():
            if k != k.upper():
                continue
            if k.upper() == name:
                return cls[k]
        if not raise_exception:
            return None
        if name:
            raise ValueError(f"'{orig_name}' is not a valid {cls.__name__}")
        else:
            raise ValueError(f"None/Empty is not a valid {cls.__name__}")

    @classmethod
    def by_prefix(cls, name: str, raise_exception: bool = False) -> Self | None:
        if name is None or not name.strip():
            if raise_exception:
                raise ValueError(f"None is not a valid {cls.__name__}")
            else:
                return None
        orig_name = name = name.strip()
        name = name.strip().upper()
        for k, v in cls.__members__.items():
            if k != k.upper():
                continue
            if k.upper().startswith(name):
                return cls[k]
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
            if hasattr(member.value, "bits") and member.value.bits == value:
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
        elif type(value) is int:
            return cls.by_value(value, raise_exception=True)
        raise ValueError(f"{value} is not a valid {cls.__name__}")

    @property
    def title(self) -> str:
        return self.name.title()

    @property
    def label(self) -> str:
        return self.name.capitalize()


class OfficialRRSpeeds(Mixins):
    """
    Marker enum
    """

    @classmethod
    def to_rr_speed(cls, speed: int, exact: bool = True) -> Self | None:
        if speed is None:
            return None
        for _, member in cls.__members__.items():
            if exact:
                if speed == member.speed:
                    return member
            elif speed in member.value:
                return member
        return None

    @property
    def speed(self) -> int:
        return self.value[0]

    @property
    def range(self) -> int:
        return self.value


@unique
class CommandSyntax(Mixins):
    TMCC = 1
    LEGACY = 2
    PDI = 3


@unique
class CommandScope(Mixins):
    ENGINE = 1
    TRAIN = 2
    SWITCH = 3
    ROUTE = 4
    ACC = 5
    SYSTEM = 6
    ASC2 = 7
    AMC2 = 8
    BPC2 = 9
    IRDA = 10
    STM2 = 11
    BASE = 12
    SYNC = 13
    BLOCK = 14

    @classmethod
    def by_prefix(cls, name: str, raise_exception: bool = False) -> Self | None:
        value = super().by_prefix(name, False)
        if isinstance(value, CommandScope):
            return value
        elif name and name.lower().startswith("rt"):
            return cls.ROUTE
        elif not raise_exception:
            return None
        else:
            raise ValueError(f"'{name}' is not a valid {cls.__name__}")


@unique
class Direction(Mixins):
    UNKNOWN = 0
    L2R = 1
    R2L = 2


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
        return self.as_int.to_bytes(1, byteorder="big")


"""
    Relative speed is specified with values ranging from -5 to 5 that are
    mapped to values 0-10
"""
RELATIVE_SPEED_MAP = dict(zip(range(-5, 6), range(0, 11)))
REVERSE_SPEED_MAP = dict(zip(range(-3, 0), range(1, 4)))
CONTROL_TYPE: Dict[int, str] = {
    0: "Cab-1",
    1: "TMCC",
    2: "Legacy",
    3: "R100",
}
SOUND_TYPE: Dict[int, str] = {
    0: "None",
    1: "RailSounds",
    2: "RailSounds 5",
    3: "LegacySounds",
}
LOCO_TYPE: Dict[int, str] = {
    0: "Diesel",
    1: "Steam",
    2: "Electric",
    3: "Subway",
    4: "Accessory/Operating Car",
    5: "Passenger",
    6: "Breakdown",
    7: "reserved",
    8: "Acela",
    9: "Track Crane",
    10: "Diesel Switcher",
    11: "Steam Switcher",
    12: "Freight",
    13: "Diesel Pullmor",
    14: "Steam Pullmor",
    15: "Transformer",
}
LOCO_CLASS: Dict[int, str] = {
    0: "Locomotive",
    1: "Switcher",
    2: "Subway",
    10: "Pullmor",
    20: "Transformer",
    255: "Universal",
}


class EngineType(Mixins, IntEnum):
    DIESEL = 0
    STEAM = 1
    ELECTRIC = 2
    SUBWAY = 3
    ACCESSORY = 4
    PASSENGER_CAR = 5
    BREAKDOWN = 6
    RESERVED = 7
    ACELA = 8
    CRANE = 9
    DIESEL_SWITCHER = 10
    STEAM_SWITCHER = 11
    FREIGHT_SOUNDS = 12
    DIESEL_PULLMOR = 13
    STEAM_PULLMOR = 14
    TRANSFORMER = 15

    def label(self) -> str:
        return self.name.replace("_", " ").title()


TMCC_CONTROL_TYPE = 1
LEGACY_CONTROL_TYPE = 2
CAB1_CONTROL_TYPE = 0
LOCO_ACCESSORY = 4
LOCO_TRACK_CRANE: int = 9
TRACK_CRANE_STATE_NUMERICS: Set[int] = {1, 2, 3}

RPM_TYPE = {0, 10, 13}
STEAM_TYPE = {1, 11, 14}
DIESEL_TYPE = {0, 10, 13}
ELECTRIC_TYPE = {2, 8}
CRANE_TYPE = {LOCO_TRACK_CRANE}
PASSENGER_TYPE = {5}
ACELA_TYPE = {8}
FREIGHT_TYPE = {12}


# Turn some of these into enums
class ControlTypeDef:
    def __init__(self, control_type: int, is_legacy: bool = False) -> None:
        self._control_type = control_type
        self._is_legacy = is_legacy

    @property
    def is_legacy(self) -> bool:
        return self._is_legacy

    @property
    def control_type(self) -> int:
        return self._control_type

    @property
    def bits(self) -> int:
        return self._control_type

    @property
    def label(self) -> str:
        return CONTROL_TYPE[self.control_type]


@unique
class ControlType(Mixins):
    CAB1 = ControlTypeDef(0)
    TMCC = ControlTypeDef(1)
    LEGACY = ControlTypeDef(2, True)
    R100 = ControlTypeDef(3)

    @property
    def is_legacy(self) -> bool:
        return self.value.is_legacy

    @property
    def label(self) -> str:
        return self.value.label
