from enum import Enum, unique, IntEnum
from typing import Any, List

import sys
if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

"""
    General Constants
"""
DEFAULT_BAUDRATE: int = 9600
DEFAULT_VALID_BAUDRATES: List[int] = [9600, 19200, 38400, 57600, 115200]
DEFAULT_PORT: str = "/dev/ttyUSB0"
DEFAULT_ADDRESS: int = 99
BROADCAST_ADDRESS: int = 99
BROADCAST_TOPIC = "BROADCAST"

DEFAULT_BASE3_PORT: int = 50001

DEFAULT_SERVER_PORT: int = 5110  # unassigned by IANA as of 9/16/2024

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


class OfficialRRSpeeds(Mixins, Enum):
    """
        Marker enum
    """


@unique
class CommandSyntax(Mixins, Enum):
    TMCC = 1
    LEGACY = 2


@unique
class CommandScope(Mixins, Enum):
    ENGINE = 1
    TRAIN = 2
    SWITCH = 3
    ROUTE = 4
    ACC = 5
    SYSTEM = 6

    @property
    def friendly(self) -> str:
        return self.name.capitalize()


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


"""
    Relative speed is specified with values ranging from -5 to 5 that are
    mapped to values 0 - 10
"""
RELATIVE_SPEED_MAP = dict(zip(range(-5, 6), range(0, 11)))
