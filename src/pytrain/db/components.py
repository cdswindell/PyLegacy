#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
#

from __future__ import annotations

from enum import IntEnum, unique

from ..protocol.multibyte.multibyte_constants import UnitAssignment
from ..protocol.constants import Mixins
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum


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
                # Prepends valid component from byte pair when present
                if data[i] != 0xFF and data[i + 1] != 0xFF:
                    consist_components.insert(0, ConsistComponent(tmcc_id=data[i + 1], flags=data[i]))
            else:
                break
        return consist_components

    # noinspection PyTypeChecker
    @classmethod
    def from_d4_bytes(cls, data: bytes) -> list[ConsistComponent]:
        from .component_state_store import ComponentStateStore

        consist_components: list[ConsistComponent] = []
        data_len = len(data)
        for i in range(0, 64, 4):
            if data_len > i:
                if data[i + 1] != 0xFF and data[i + 2] != 0xFF and data[i + 3] != 0xFF:
                    flags = data[i + 1]
                    rec_no = int.from_bytes(data[i + 2 : i + 4], byteorder="little")
                    state = ComponentStateStore.by_record_no(rec_no)
                    if state:
                        consist_components.append(ConsistComponent(state.tmcc_id, flags, rec_no, data[0]))
            else:
                break
        return consist_components

    @classmethod
    def to_bytes(cls, components: list[ConsistComponent]) -> bytes:
        byte_str = bytes()
        for comp in reversed(components):
            byte_str += comp.as_bytes
        byte_str += b"\xff" * (32 - len(byte_str))
        return byte_str

    @classmethod
    def to_d4_bytes(cls, components: list[ConsistComponent]) -> bytes:
        byte_str = bytes()
        for comp in components:
            byte_str += comp.as_bytes
        byte_str += b"\xff" * (64 - len(byte_str))
        return byte_str

    def __init__(self, tmcc_id: int, flags: int, rec_no: int = None, extra: int = 0xFF) -> None:
        self.tmcc_id = tmcc_id
        self.flags = flags
        self.extra = extra
        self.rec_no = rec_no
        self._ua = UnitAssignment(0b111 & flags)

    def __repr__(self) -> str:
        d = "F" if self.is_forward else "R"
        tl = " T" if self.is_train_link else ""
        hm = " H" if self.is_horn_masked else ""
        dm = " D" if self.is_dialog_masked else ""
        a = " A" if self.is_accessory else ""
        return f"[Engine {self.tmcc_id} {self.unit_type.name.title()} {d}{hm}{dm}{tl}{a} ({bin(self.flags)})]"

    @property
    def info(self) -> str:
        d = "F" if self.is_forward else "R"
        tl = " T" if self.is_train_link else ""
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
        return (0b11 & self.flags == 0b1) | self.is_single

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
    def is_train_link(self) -> bool:
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
    def is_d4(self) -> bool:
        return self.rec_no is not None

    @property
    def direction(self) -> str:
        return self._ua.direction

    @property
    def position(self) -> str:
        return self._ua.position

    @property
    def as_bytes(self) -> bytes:
        if self.is_d4:
            byte_str = b"\xff"
            byte_str += self.flags.to_bytes(1, byteorder="little")
            byte_str += self.rec_no.to_bytes(2, byteorder="little")
        else:
            byte_str = self.flags.to_bytes(1, byteorder="little")
            byte_str += self.tmcc_id.to_bytes(1, byteorder="little")
        return byte_str


class RouteComponent:
    from ..protocol.command_req import CommandReq

    @classmethod
    def from_bytes(cls, data: bytes) -> list[RouteComponent]:
        """Parses fixed‑length route components; sorts by ID"""
        route_comps: list[RouteComponent] = list()
        data_len = len(data)
        for i in range(0, 32, 2):
            if data_len > i:
                if data[i] != 0xFF and data[i + 1] != 0xFF:
                    route_comps.insert(0, RouteComponent(tmcc_id=data[i + 1], flags=data[i]))
            else:
                break
        route_comps = sorted(route_comps, key=lambda s: s.tmcc_id)
        return route_comps

    @classmethod
    def to_bytes(cls, components: list[RouteComponent]) -> bytes:
        byte_str = bytes()
        for comp in components:
            byte_str += comp.as_bytes
        byte_str += b"\xff" * (32 - len(byte_str))
        return byte_str

    def __init__(self, tmcc_id: int, flags: int) -> None:
        self.tmcc_id = tmcc_id
        self.flags = flags

    @property
    def is_thru(self) -> bool:
        return 0x03 & self.flags == 0

    @property
    def is_out(self) -> bool:
        return 0x03 & self.flags == 1

    @property
    def is_route(self) -> bool:
        return 0x03 & self.flags == 3

    @property
    def is_switch(self) -> bool:
        return not self.is_route

    @property
    def as_signature(self) -> dict[str, bool]:
        if self.is_switch:
            return {f"S{self.tmcc_id}": self.is_thru}
        else:
            return {f"R{self.tmcc_id}": True}

    @property
    def as_request(self) -> CommandReq:
        from ..protocol.command_req import CommandReq

        cmd_enum = TMCC1SwitchCommandEnum.THRU if self.is_thru is True else TMCC1SwitchCommandEnum.OUT
        return CommandReq(cmd_enum, self.tmcc_id)

    @property
    def as_bytes(self) -> bytes:
        byte_str = self.flags.to_bytes(1, byteorder="little")
        byte_str += self.tmcc_id.to_bytes(1, byteorder="little")
        return byte_str
