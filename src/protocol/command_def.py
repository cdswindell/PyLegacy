import abc
import math
from abc import ABC
from enum import Enum
from typing import Dict, Any, Self

from .constants import CommandSyntax, CommandScope, Mixins


class CommandDef(ABC):
    __metaclass__ = abc.ABCMeta
    """
        Marker class for TMCC1 and TMCC2 Command Defs, allowing the CLI layer
        to work with them in a command format agnostic manner.
    """

    def __init__(self,
                 command_bits: int,
                 is_addressable: bool = True,
                 d_min: int = 0,
                 d_max: int = 0,
                 d_map: Dict[int, int] = None) -> None:
        self._command_bits = command_bits
        self._is_addressable = is_addressable
        self._d_min = d_min
        self._d_max = d_max
        self._d_map = d_map
        self._d_bits = 0
        if d_max:
            self._d_bits = math.ceil(math.log2(d_max))
        elif d_map is not None:
            self._d_bits = math.ceil(math.log2(max(d_map.values())))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} 0x{self.bits:04x}: {self.num_data_bits} data bits"

    @property
    def bits(self) -> int:
        return self._command_bits

    @property
    def is_addressable(self) -> bool:
        return self._is_addressable

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


class CommandDefMixins(Mixins):
    @classmethod
    def by_value(cls, value: Any, raise_exception: bool = False) -> Self | None:
        """
            We redefine by_value to allow handling of command defs
        """
        for _, member in cls.__members__.items():
            if member.value == value:
                return member
            if isinstance(member, CommandDef) and CommandDef(value).bits == value:
                return member
        if raise_exception:
            raise ValueError(f"'{value}' is not a valid {cls.__name__}")
        else:
            return None


class CommandDefEnum(CommandDefMixins, Enum):
    """
        Marker Interface to allow TMCC1EngineCommandDef and TMCC2EngineCommandDef enums
        to be handled by engine commands
    """

    @property
    def command_def(self) -> CommandDef:
        return self.value

    @property
    def scope(self) -> CommandScope:
        return self.command_def.scope

    @property
    def syntax(self) -> CommandSyntax:
        return self.value.syntax