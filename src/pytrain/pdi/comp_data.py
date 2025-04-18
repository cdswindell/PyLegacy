#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from typing import Any, TypeVar, Generic, Callable

from .consist_component import ConsistComponent
from .pdi_req import PdiReq
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.constants import CommandScope

BASE_TO_TMCC_SMOKE_MAP = {
    0: TMCC2EffectsControl.SMOKE_OFF,
    1: TMCC2EffectsControl.SMOKE_LOW,
    2: TMCC2EffectsControl.SMOKE_MEDIUM,
    3: TMCC2EffectsControl.SMOKE_HIGH,
}

TMCC_TO_BASE_SMOKE_MAP = {v: k for k, v in BASE_TO_TMCC_SMOKE_MAP.items()}


def default_from_func(t: bytes) -> int:
    return int.from_bytes(t, byteorder="little")


def default_to_func(t: int) -> bytes:
    return t.to_bytes(1, byteorder="little")


class CompDataHandler:
    def __init__(
        self,
        field: str,
        length: int = 1,
        from_bytes: Callable = default_from_func,
        to_bytes: Callable = default_to_func,
        d4_only: bool = False,
    ) -> None:
        self.field: str = field
        self.length: int = length
        self.from_bytes: Callable = from_bytes
        self.to_bytes: Callable = to_bytes
        self._d4_only: bool = d4_only

    @property
    def is_d4_only(self) -> bool:
        return self._d4_only


BASE_MEMORY_ENGINE_READ_MAP = {
    0xB8: CompDataHandler(
        "_tmcc_id",
        4,
        lambda t: int(PdiReq.decode_text(t)),
        lambda t: PdiReq.encode_text(str(t).zfill(4), 4),
        True,
    ),
    0x00: CompDataHandler("_prev_link"),
    0x01: CompDataHandler("_next_link"),
    0x04: CompDataHandler(
        "_bt_id",
        2,
        lambda t: int.from_bytes(t[0:2], byteorder="little"),
        lambda t: t.to_bytes(2, byteorder="little"),
    ),
    0x07: CompDataHandler("_speed"),
    0x08: CompDataHandler("_target_speed"),
    0x09: CompDataHandler("_train_brake"),
    0x0C: CompDataHandler("_rpm_labor"),
    0x18: CompDataHandler("_momentum"),
    0x1F: CompDataHandler(
        "_road_name",
        31,
        lambda t: PdiReq.decode_text(t),
        lambda t: PdiReq.encode_text(t, 31),
    ),
    0x3E: CompDataHandler("_road_number_len"),
    0x3F: CompDataHandler(
        "_road_number",
        4,
        lambda t: PdiReq.decode_text(t),
        lambda t: PdiReq.encode_text(t, 4),
    ),
    0x43: CompDataHandler("_engine_type"),
    0x44: CompDataHandler("_control_type"),
    0x45: CompDataHandler("_sound_type"),
    0x46: CompDataHandler("_engine_class"),
    0x59: CompDataHandler("_tsdb_left"),
    0x5B: CompDataHandler("_tsdb_right"),
    0x69: CompDataHandler("_smoke"),
    0x6A: CompDataHandler("_speed_limit"),
    0x6B: CompDataHandler("_max_speed"),
    0xBC: CompDataHandler(
        "_timestamp",
        4,
        lambda t: int.from_bytes(t[0:4], byteorder="little"),
        lambda t: t.to_bytes(4, byteorder="little"),
        True,
    ),
}

BASE_MEMORY_TRAIN_READ_MAP = {
    0x6F: CompDataHandler("_consist_flags"),
    0x70: CompDataHandler(
        "_consist_comps",
        32,
        lambda t: ConsistComponent.from_bytes(t),
        lambda t: ConsistComponent.to_bytes(t),
    ),
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
        super().__init__()
        self._tmcc_id: int | None = tmcc_id
        self._scope = scope
        # self.__signal_initialized()
        # load the data from the byte string
        self._parse_bytes(data, SCOPE_TO_COMP_MAP.get(self.scope))

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

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        if "_" + name in self.__dict__:
            self.__dict__["_" + name] = value
        elif name.endswith("_tmcc") and name.replace("_tmcc", "") in CONVERSIONS:
            name = name.replace("_tmcc", "")
            tpl = CONVERSIONS[name]
            if name in {"rpm", "labor"}:
                pass
            # TODO: handle setting of rpm/labor
            else:
                self.__dict__["_" + name] = tpl[2](value) if value is not None else value
        else:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def _signal_initializing(self) -> None:
        self.__dict__["__initializing__"] = True

    def __signal_initialized(self) -> None:
        self.__dict__["__initializing__"] = False

    def as_bytes(self) -> bytes:
        comp_map = SCOPE_TO_COMP_MAP.get(self.scope)
        schema = {key: comp_map[key] for key in sorted(comp_map.keys())}
        if self.tmcc_id <= 99:
            # delete any entries that are 4-digit specific
            for k in list(schema.keys()):
                if schema[k].is_d4_only is True:
                    del schema[k]
        byte_str = bytes()
        last_idx = 0
        for idx, tpl in schema.items():
            if idx > last_idx:
                byte_str += b"\xff" * (idx - last_idx)
            data_len = tpl.length
            new_bytes = tpl.to_bytes(getattr(self, tpl.field))
            if len(new_bytes) < data_len:
                new_bytes += b"\xff" * (data_len - len(new_bytes))
            byte_str += new_bytes
            last_idx = idx + data_len
        # final check
        if len(byte_str) < PdiReq.LIONEL_RECORD_LENGTH:
            byte_str += b"\x00" * (PdiReq.LIONEL_RECORD_LENGTH - len(byte_str))

        return byte_str

    def _parse_bytes(self, data: bytes, pmap: dict) -> None:
        data_len = len(data)
        for k, v in pmap.items():
            if isinstance(v, CompDataHandler) is False:
                continue
            item_len = v.length
            if data_len >= ((k + item_len) - 1) and hasattr(self, v.field) and getattr(self, v.field) is None:
                func = v.from_bytes
                value = func(data[k : k + item_len])
                if hasattr(self, v.field):
                    setattr(self, v.field, value)


class EngineData(CompData):
    def __init__(self, data: bytes, scope: CommandScope = CommandScope.ENGINE, tmcc_id: int = None) -> None:
        self._signal_initializing()
        self._prev_link: int | None = None
        self._next_link: int | None = None
        self._bt_id: int | None = None
        self._speed: int | None = None
        self._target_speed: int | None = None
        self._train_brake: int | None = None
        self._rpm_labor: int | None = None
        self._momentum: int | None = None
        self._road_name: str | None = None
        self._road_number_len: int | None = None
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
    """
    Represents train data within a Lionel layout.

    This class extends the functionality of `EngineData` to handle train-specific
    information. It is designed to process and manage data related to the train's
    operation, such as consist flags and consist components, in addition to providing
    integration capabilities with the engine control system.

    Attributes:
        _consist_flags (int | None): Flags representing the state or configuration of the
            train. This value is optional and may be set to `None` if not applicable.
        _consist_comps (list[ConsistComponent] | None): A list of components that make
            up the train's consist. This is optional and can remain `None` if no consist
            components are defined.
    """

    def __init__(self, data: bytes, tmcc_id: int = None) -> None:
        self._signal_initializing()
        self._consist_flags: int | None = None
        self._consist_comps: list[ConsistComponent] | None = None
        super().__init__(data, scope=CommandScope.TRAIN, tmcc_id=tmcc_id)


class CompDataMixin(Generic[C]):
    """
    Provides a mixin class for managing component-related data and
    recording state in generic types.

    This mixin class is designed to extend the functionality of a
    base class by adding attributes for component-related data
    and a recording state flag. The generic type `C` is used to
    allow flexibility in the type of component data stored.
    The mixin includes properties to access the component data
    and determine whether the recording state is set.

    Attributes:
        _comp_data: A generic component-related data attribute
            of type `C`. Defaults to None.
        _comp_data_record: A flag indicating whether component
            data recording is active. Defaults to False.
    """

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
