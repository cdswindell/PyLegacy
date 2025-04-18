from __future__ import annotations

from enum import unique, IntEnum

from src.pytrain.protocol.constants import Mixins


@unique
class UnitBits(Mixins, IntEnum):
    SINGLE = 0b0
    HEAD = 0b1
    MIDDLE = 0b10
    TAIL = 0b11


class ConsistComponent:
    @classmethod
    def from_bytes(cls, data: bytes) -> list[ConsistComponent]:
        consist_components: list[ConsistComponent] = []
        data_len = len(data)
        for i in range(0, 32, 2):
            if data_len > i:
                if data[i] != 0xFF and data[i + 1] != 0xFF:
                    consist_components.insert(0, ConsistComponent(tmcc_id=data[i + 1], flags=data[i]))
            else:
                break
        return consist_components

    @classmethod
    def to_bytes(cls, components: list[ConsistComponent]) -> bytes:
        byte_str = bytes()
        for comp in reversed(components):
            byte_str += comp.as_bytes
        return byte_str

    def __init__(self, tmcc_id: int, flags: int) -> None:
        self.tmcc_id = tmcc_id
        self.flags = flags

    def __repr__(self) -> str:
        d = "F" if self.is_forward else "R"
        tl = " T" if self.is_train_linked else ""
        hm = " H" if self.is_horn_masked else ""
        dm = " D" if self.is_dialog_masked else ""
        a = " A" if self.is_accessory else ""
        return f"[Engine {self.tmcc_id} {self.unit_type.name.title()} {d}{hm}{dm}{tl}{a} (0b{bin(self.flags)})]"

    @property
    def info(self) -> str:
        d = "F" if self.is_forward else "R"
        tl = " T" if self.is_train_linked else ""
        hm = " H" if self.is_horn_masked else ""
        dm = " D" if self.is_dialog_masked else ""
        a = " A" if self.is_accessory else ""
        return f"{self.unit_type.name.title()[0]} {d}{hm}{dm}{tl}{a} {self.flags}"

    @property
    def unit_type(self) -> UnitBits:
        return UnitBits(self.flags & 0b11)

    @property
    def is_single(self) -> bool:
        return 0b11 & self.flags == 0b0

    @property
    def is_head(self) -> bool:
        return 0b11 & self.flags == 0b1

    @property
    def is_middle(self) -> bool:
        return 0b11 & self.flags == 0b10

    @property
    def is_tail(self) -> bool:
        return 0b11 & self.flags == 0b11

    @property
    def is_forward(self) -> bool:
        return 0b100 & self.flags == 0b000

    @property
    def is_reverse(self) -> bool:
        return 0b100 & self.flags == 0b100

    @property
    def is_train_linked(self) -> bool:
        return 0b1000 & self.flags == 0b1000

    @property
    def is_horn_masked(self) -> bool:
        return 0b10000 & self.flags == 0b10000

    @property
    def is_dialog_masked(self) -> bool:
        return 0b100000 & self.flags == 0b100000

    @property
    def is_tmcc2(self) -> bool:
        return 0b1000000 & self.flags == 0b1000000

    @property
    def is_accessory(self) -> bool:
        return 0b10000000 & self.flags == 0b10000000

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.flags.to_bytes(1, byteorder="little")
        byte_str += self.tmcc_id.to_bytes(1, byteorder="little")
        return byte_str
