from __future__ import annotations

from enum import unique, IntEnum
from typing import Any, TypeVar, Generic

from .pdi_req import PdiReq
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.constants import CommandScope, Mixins

BASE_TO_TMCC_SMOKE_MAP = {
    0: TMCC2EffectsControl.SMOKE_OFF,
    1: TMCC2EffectsControl.SMOKE_LOW,
    2: TMCC2EffectsControl.SMOKE_MEDIUM,
    3: TMCC2EffectsControl.SMOKE_HIGH,
}

TMCC_TO_BASE_SMOKE_MAP = {v: k for k, v in BASE_TO_TMCC_SMOKE_MAP.items()}

BASE_MEMORY_ENGINE_READ_MAP = {
    0x00: ("_prev_link",),
    0x01: ("_next_link",),
    0x04: ("_bt_id", lambda t: int.from_bytes(t, byteorder="little"), 2),
    0x07: ("_speed",),
    0x08: ("_target_speed",),
    0x09: ("_train_brake",),
    0x0C: ("_rpm_labor",),
    0x18: ("_momentum",),
    0x1F: ("_road_name", lambda t: PdiReq.decode_text(t), 31),
    0x3F: ("_road_number", lambda t: PdiReq.decode_text(t), 4),
    0x43: ("_engine_type",),
    0x44: ("_control_type",),
    0x45: ("_sound_type",),
    0x46: ("_engine_class",),
    0x59: ("_tsdb_left",),
    0x5B: ("_tsdb_right",),
    0x69: ("_smoke",),
    0x6A: ("_speed_limit",),
    0x6B: ("_max_speed",),
    0xB8: ("_tmcc_id", lambda t: int(PdiReq.decode_text(t)), 4),
    0xBC: ("_timestamp", lambda t: int.from_bytes(t[0:4], byteorder="little"), 4),
}

BASE_MEMORY_TRAIN_READ_MAP = {
    0x6F: ("_consist_flags",),
    0x70: ("_consist_comps", lambda t: ConsistComponent.from_bytes(t), 32),
}
BASE_MEMORY_TRAIN_READ_MAP.update(BASE_MEMORY_ENGINE_READ_MAP)

SCOPE_TO_COMP_MAP = {
    CommandScope.ENGINE: BASE_MEMORY_ENGINE_READ_MAP,
    CommandScope.TRAIN: BASE_MEMORY_TRAIN_READ_MAP,
}

CONVERSIONS = {
    "train_brake": (lambda x: min(round(x * 0.4667), 7), lambda x: min(round(x * 2.143), 15)),
    "momentum": (lambda x: min(round(x * 0.05512), 7), lambda x: min(round(x * 18.14), 127)),
    "smoke": (
        lambda x: BASE_TO_TMCC_SMOKE_MAP.get(x, TMCC2EffectsControl.SMOKE_OFF),
        lambda x: TMCC_TO_BASE_SMOKE_MAP.get(x, 0),
    ),
    "rpm": (lambda x: x & 0b111, lambda x: x & 0b111),
    "labor": (
        lambda x: (x >> 3) + 12 if (x >> 3) <= 19 else (x >> 3) - 20,
        lambda x: (x - 12 if x >= 12 else 20 + x) << 3,
    ),
}


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
                    consist_components.insert(0, ConsistComponent(data[i], data[i + 1]))
            else:
                break
        return consist_components

    def __init__(self, flags: int, tmcc_id: int) -> None:
        self.flags = flags
        self.tmcc_id = tmcc_id

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


def default_func(t):
    return int.from_bytes(t, byteorder="little")


C = TypeVar("C", bound="CompData")


class CompData:
    @classmethod
    def from_bytes(cls, data: bytes, scope: CommandScope, tmcc_id: int = None) -> C:
        if scope == CommandScope.ENGINE:
            return EngineData(data, tmcc_id=tmcc_id)
        elif scope == CommandScope.TRAIN:
            return TrainData(data, tmcc_id=tmcc_id)
        else:
            raise ValueError(f"Invalid scope: {scope}")

    def __init__(self, data: bytes, scope: CommandScope, tmcc_id: int = None) -> None:
        self._tmcc_id: int | None = tmcc_id
        self._scope = scope

        # load the data from the byte string
        self._parse_bytes(data, SCOPE_TO_COMP_MAP.get(self.scope))

    @property
    def as_bytes(self) -> bytes:
        comp_map = SCOPE_TO_COMP_MAP.get(self.scope)
        schema = {key: comp_map[key] for key in sorted(comp_map.keys())}
        byte_str = bytes()
        last_idx = 0
        for idx, tpl in schema.items():
            if idx > last_idx:
                byte_str += bytes() * (idx - last_idx)
            data_len = tpl[2] if len(tpl) > 2 else 1

            last_idx = idx + data_len

        return byte_str

    def __getattr__(self, name: str) -> Any:
        if "_" + name in self.__dict__:
            return self.__dict__["_" + name]
        elif name.endswith("_tmcc") and name.replace("_tmcc", "") in CONVERSIONS:
            name = name.replace("_tmcc", "")
            tpl = CONVERSIONS[name]
            # special case labor/rpm
            if name in {"rpm", "labor"}:
                name = "rpm_labor"
            value = self.__dict__["_" + name]
            return tpl[0](value) if value is not None else value
        else:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    # def __setattr__(self, name: str, value: Any) -> None:
    #     if "_" + name in self.__dict__:
    #         self.__dict__["_" + name] = value
    #     elif name.endswith("_tmcc") and name.replace("_tmcc", "") in CONVERSIONS:
    #         name = name.replace("_tmcc", "")
    #         tpl = CONVERSIONS[name]
    #         if name in {"rpm", "labor"}:
    #             pass
    #         # TODO: handle setting of rpm/labor
    #         else:
    #             self.__dict__["_" + name] = tpl[2](value) if value is not None else value
    #     else:
    #         super().__setattr__(name, value)
    #         # raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def _parse_bytes(self, data: bytes, pmap: dict) -> None:
        data_len = len(data)
        for k, v in pmap.items():
            if isinstance(v, tuple) is False:
                continue
            item_len = v[2] if len(v) > 2 else 1
            if data_len >= ((k + item_len) - 1) and hasattr(self, v[0]) and getattr(self, v[0]) is None:
                if len(v) == 1:
                    func = default_func
                else:
                    func = v[1]
                value = func(data[k : k + item_len])
                if hasattr(self, v[0]):
                    setattr(self, v[0], value)


class EngineData(CompData):
    def __init__(self, data: bytes, scope: CommandScope = CommandScope.ENGINE, tmcc_id: int = None) -> None:
        self._prev_link: int | None = None
        self._next_link: int | None = None
        self._bt_id: int | None = None
        self._speed: int | None = None
        self._target_speed: int | None = None
        self._train_brake: int | None = None
        self._rpm_labor: int | None = None
        self._momentum: int | None = None
        self._road_name: str | None = None
        self._road_number: str | None = None
        self._engine_type: int | None = None
        self._control_type: int | None = None
        self._sound_type: int | None = None
        self._engine_class: int | None = None
        self._tsdb_left: int | None = None
        self._tsdb_right: int | None = None
        self._smoke: int | None = None
        self._speed_limit: int | None = None
        self._max_speed: int | None = None
        self._timestamp: int | None = None
        super().__init__(data, scope, tmcc_id=tmcc_id)


class TrainData(EngineData):
    def __init__(self, data: bytes, tmcc_id: int = None) -> None:
        self._consist_flags: int | None = None
        self._consist_comps: list[ConsistComponent] | None = None
        super().__init__(data, scope=CommandScope.TRAIN, tmcc_id=tmcc_id)


class CompDataMixin(Generic[C]):
    def __init__(self):
        super().__init__()
        self._comp_data: C | None = None
        self._comp_data_record: bool = False

    @property
    def comp_data(self) -> C:
        return self._comp_data

    @property
    def is_comp_data_record(self) -> bool:
        return self.comp_data and self._comp_data_record is True
