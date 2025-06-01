from __future__ import annotations

import abc
import math
import sys
from abc import ABC
from enum import Enum
from typing import Any, Dict, Tuple, TypeVar

if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from .constants import CommandScope, CommandSyntax, Mixins

E = TypeVar("E", bound="CommandDefEnum")


class CommandDef(ABC):
    __metaclass__ = abc.ABCMeta
    """
        Marker class for TMCC1 and TMCC2 Command Defs, allowing the CLI layer
        to work with them in a command format agnostic manner.
    """

    def __init__(
        self,
        command_bits: int,
        is_addressable: bool = True,
        num_address_bits: int = 7,
        d_min: int = 0,
        d_max: int = 0,
        d_map: Dict[int, int] = None,
        do_reverse_lookup: bool = True,
        alias: str = None,
        data: int = None,
        filtered: bool = False,
        interval: int = None,
    ) -> None:
        self._command_bits: int = command_bits
        self._is_addressable = is_addressable
        self._num_address_bits = num_address_bits
        self._do_reverse_lookup = do_reverse_lookup
        self._alias: str = alias.strip().upper() if alias else None
        self._data: int = data
        self._d_min = d_min
        self._d_max = d_max
        self._d_map = d_map
        self._d_bits = 0
        if d_max:
            self._d_bits = math.ceil(math.log2(d_max))
        elif d_map is not None:
            self._d_bits = math.ceil(math.log2(max(d_map.values())))
        self._filtered = filtered
        self._interval = interval

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} 0x{self.bits:04x}: {self.num_data_bits} data bits"

    @property
    def bits(self) -> int:
        return self._command_bits

    @property
    def as_bytes(self) -> bytes:
        return self.bits.to_bytes(3, byteorder="big")

    @property
    def is_addressable(self) -> bool:
        return self._is_addressable

    @property
    def is_data(self) -> bool:
        return self.num_data_bits != 0

    @property
    def is_filtered(self) -> bool:
        return self._filtered

    @property
    def interval(self) -> int:
        return self._interval

    @property
    def is_aux1_prefixed(self) -> bool:
        return False

    def is_valid_data(self, candidate: int, from_bytes: bool = False) -> bool:
        """
        Determine if a candidate value is valid, given the constraints on this
        CommandDef. If from_bytes is True, the candidate value will be treated
        as coming from a bytes value, and the values (not keys) in data_map are
        used to validate.
        """
        if self.is_data is True:
            if self.data_map:
                if from_bytes is True:
                    return candidate in [v for k, v in self.data_map.items()]
                elif from_bytes is False:
                    return candidate in self.data_map
            else:
                return self.data_min <= candidate <= self.data_max
        return False

    def data_from_bytes(self, byte_data: bytes) -> int:
        if self.is_data:
            value = int.from_bytes(byte_data, byteorder="big")
            data = 0xFFFF & (~self.data_mask & value)
            if self.data_map:
                for k, v in self.data_map.items():
                    if v == data:
                        return k
            else:
                return data
        return 0

    @property
    def is_alias(self) -> bool:
        return self._alias is not None

    @property
    def num_data_bits(self) -> int:
        return self._d_bits

    @property
    def num_address_bits(self) -> int:
        if self.is_addressable:
            return self._num_address_bits
        else:
            return 0

    @property
    def data_mask(self) -> int:
        return 0xFFFF & ~(2**self.num_data_bits - 1)

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
    def is_tmcc1(self) -> bool:
        return self.syntax == CommandSyntax.TMCC

    @property
    def is_tmcc2(self) -> bool:
        return self.syntax == CommandSyntax.LEGACY

    @property
    def is_legacy(self) -> bool:
        return self.is_tmcc2

    @property
    def identifier(self) -> int | None:
        """
        Only relevant for TMCC1-style commands
        """
        return None

    @property
    def do_reverse_lookup(self) -> bool:
        return self._do_reverse_lookup

    @property
    @abc.abstractmethod
    def address_mask(self) -> int | None:
        return None

    @property
    @abc.abstractmethod
    def first_byte(self) -> bytes | None:
        return None

    @property
    @abc.abstractmethod
    def scope(self) -> CommandScope | None:
        return None

    @property
    @abc.abstractmethod
    def alias(self) -> E | Tuple[E, int] | None:
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
            if hasattr(member.value, "bits") and member.value.bits == value:
                return member
            if isinstance(member, CommandDef) and CommandDef(value).bits == value:
                return member
            if isinstance(member, CommandDefEnum) and isinstance(value, int) and not member.value.is_alias:
                cd = member.value  # CommandDef
                if cd.is_data is True:
                    data = 0xFFFF & (~cd.data_mask & value)
                    if value & cd.address_mask & cd.data_mask == member.value.bits and cd.is_valid_data(
                        data, from_bytes=True
                    ):
                        return member
                elif value & cd.address_mask == member.value.bits:
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
        return self.command_def.syntax

    @property
    def is_tmcc1(self) -> bool:
        return self.command_def.is_tmcc1

    @property
    def is_tmcc2(self) -> bool:
        return self.command_def.is_tmcc2

    @property
    def is_legacy(self) -> bool:
        return self.command_def.is_tmcc2

    @property
    def bits(self) -> int:
        return self.value.bits

    @property
    def is_alias(self) -> bool:
        return self.command_def.is_alias

    @property
    def is_filtered(self) -> bool:
        return self.command_def.is_filtered

    @property
    def alias(self) -> E | Tuple[E, int]:
        return self.command_def.alias

    @property
    def as_bytes(self) -> bytes:
        return self.value.as_bytes
