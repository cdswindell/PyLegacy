#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import logging
from abc import ABC, ABCMeta, abstractmethod
from typing import Any, Callable, Generic, TypeVar

from ..pdi.base3_component import ConsistComponent, RouteComponent
from ..pdi.pdi_req import PdiReq
from ..protocol.command_req import CommandReq
from ..protocol.constants import LEGACY_CONTROL_TYPE, CommandScope
from ..protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..utils.text_utils import title

log = logging.getLogger(__name__)

BASE_TO_TMCC2_SMOKE_MAP = {
    0: TMCC2EffectsControl.SMOKE_OFF,
    1: TMCC2EffectsControl.SMOKE_LOW,
    2: TMCC2EffectsControl.SMOKE_MEDIUM,
    3: TMCC2EffectsControl.SMOKE_HIGH,
}

TMCC2_TO_BASE_SMOKE_MAP = {v: k for k, v in BASE_TO_TMCC2_SMOKE_MAP.items()}

BASE_TO_TMCC1_SMOKE_MAP = {
    0: TMCC1EngineCommandEnum.SMOKE_OFF,
    1: TMCC1EngineCommandEnum.SMOKE_ON,
}

TMCC1_TO_BASE_SMOKE_MAP = {v: k for k, v in BASE_TO_TMCC1_SMOKE_MAP.items()}


def default_from_func(t: bytes) -> int:
    return int.from_bytes(t, byteorder="little")


def default_to_func(t: int) -> bytes:
    return t.to_bytes(1, byteorder="little")


class CompDataHandler:
    """
    Helper class to read and write configuration data from and to bytes.
    Lionel component state is read from the Base 3 using the BASE_MEMORY,
    D4_ENGINE, and D4_TRAIN pdi commands. State is returned as a byte string.
    The CompDataHandler class defines the byte address where specific state
    is stored and allows lambda functions to convert the raw byte string to
    Python types as well as to write Python types to the byte string.
    """

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


class UpdatePkg:
    def __init__(self, field: str, offset: int, length: int, data_bytes: bytes) -> None:
        self.field: str = field
        self.offset: int = offset
        self.length: int = length
        self.data_bytes: bytes = data_bytes

    def __repr__(self) -> str:
        return f"{self.field}: Address: {hex(self.offset)} Length: {self.length} data: {self.data_bytes.hex()}"


#
# Base 3 memory locations where device state is stored. When commands are issued that change
# device characteristics, like engine speed or momentum, these changes must be explicitly
# written to the Base 3 so it can update other attached controllers and software.
#
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
    0x02: CompDataHandler("_unk_2"),
    0x03: CompDataHandler("_unk_3"),
    0x04: CompDataHandler(
        "_bt_id",
        2,
        lambda t: int.from_bytes(t[0:2], byteorder="little"),
        lambda t: t.to_bytes(2, byteorder="little"),
    ),
    0x06: CompDataHandler("_unk_6"),
    0x07: CompDataHandler("_speed"),
    0x08: CompDataHandler("_target_speed"),
    0x09: CompDataHandler("_train_brake"),
    0x0A: CompDataHandler("_unk_a"),
    0x0B: CompDataHandler("_unk_b"),
    0x0C: CompDataHandler("_rpm_labor"),
    0x0D: CompDataHandler("_fuel_level"),
    0x0E: CompDataHandler("_water_level"),
    0x0F: CompDataHandler("_unk_f"),
    0x11: CompDataHandler("_unk_11"),
    0x12: CompDataHandler("_unk_12"),
    0x13: CompDataHandler("_unk_13"),
    0x17: CompDataHandler("_unk_17"),
    0x18: CompDataHandler("_momentum"),
    0x1E: CompDataHandler("_road_name_len"),
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
    0x5C: CompDataHandler("_unk_5c"),
    0x5E: CompDataHandler("_unk_5e"),
    0x68: CompDataHandler("_unk_68"),
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
# build an inverse map from the token name to the address
FIELD_TO_ADDR_ENGINE_MAP = {v.field[1:]: k for k, v in BASE_MEMORY_ENGINE_READ_MAP.items()}

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

BASE_MEMORY_ACC_READ_MAP = {
    0x00: CompDataHandler("_prev_link"),
    0x01: CompDataHandler("_next_link"),
    0x1E: CompDataHandler("_device_code"),
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
}

BASE_MEMORY_SWITCH_READ_MAP = {
    0x00: CompDataHandler("_prev_link"),
    0x01: CompDataHandler("_next_link"),
    0x05: CompDataHandler(
        "_road_name",
        31,
        lambda t: PdiReq.decode_text(t),
        lambda t: PdiReq.encode_text(t, 31),
    ),
    0x24: CompDataHandler("_road_number_len"),
    0x25: CompDataHandler(
        "_road_number",
        4,
        lambda t: PdiReq.decode_text(t),
        lambda t: PdiReq.encode_text(t, 4),
    ),
}

BASE_MEMORY_ROUTE_READ_MAP = BASE_MEMORY_SWITCH_READ_MAP.copy()
BASE_MEMORY_ROUTE_READ_MAP.update(
    {
        0x60: CompDataHandler(
            "_components",
            32,
            lambda t: RouteComponent.from_bytes(t),
            lambda t: RouteComponent.to_bytes(t),
        ),
    }
)

SCOPE_TO_COMP_MAP = {
    CommandScope.ENGINE: BASE_MEMORY_ENGINE_READ_MAP,
    CommandScope.TRAIN: BASE_MEMORY_TRAIN_READ_MAP,
    CommandScope.ACC: BASE_MEMORY_ACC_READ_MAP,
    CommandScope.SWITCH: BASE_MEMORY_SWITCH_READ_MAP,
    CommandScope.ROUTE: BASE_MEMORY_ROUTE_READ_MAP,
}

#
# Map of Base 3 Command Requests to the corresponding Base 3 state updates
# that must be made.
#
REQUEST_TO_UPDATES_MAP = {
    "ABSOLUTE_SPEED": [
        ("speed",),
        ("target_speed",),
    ],
    "DIESEL_RPM": [("rpm",)],
    "ENGINE_LABOR": [("labor",)],
    "MOMENTUM": [("momentum",)],
    "MOMENTUM_HIGH": [("momentum", lambda t: 127)],
    "MOMENTUM_LOW": [("momentum", lambda t: 0)],
    "MOMENTUM_MEDIUM": [("momentum", lambda t: 63)],
    "RESET": [
        ("speed", lambda x: 0),
        ("target_speed", lambda x: 0),
        ("rpm_labor", lambda x: 0),
    ],
    "SHUTDOWN_DELAYED": [("rpm_labor", lambda x: 0)],
    "SHUTDOWN_IMMEDIATE": [("rpm_labor", lambda x: 0)],
    "SMOKE_HIGH": [("smoke", lambda t: 3)],
    "SMOKE_LOW": [("smoke", lambda t: 1)],
    "SMOKE_MEDIUM": [("smoke", lambda t: 2)],
    "SMOKE_OFF": [("smoke", lambda t: 0)],
    "SMOKE_ON": [("smoke", lambda t: 1)],
    "STOP_IMMEDIATE": [
        ("speed", lambda x: 0),
        ("target_speed", lambda x: 0),
        ("rpm_labor", lambda x: 0),
    ],
    "TRAIN_BRAKE": [("train_brake",)],
}

CONVERSIONS: dict[str, tuple[Callable, Callable]] = {
    "train_brake": (lambda x: min(round(x * 0.4667), 7), lambda x: min(round(x * 2.143), 15)),
    "momentum": (lambda x: min(round(x * 0.05512), 7), lambda x: min(round(x * 18.14), 127)),
    "smoke": (
        lambda map_dict, data, default: map_dict.get(data, default),
        lambda map_dict, data: map_dict.get(data, 0),
    ),
    "rpm": (lambda x: x & 0b111, lambda x: x & 0b111),
    "labor": (
        lambda x: (x >> 3) + 12 if (x >> 3) <= 19 else (x >> 3) - 20,
        lambda x: (x - 12 if x >= 12 else 20 + x) << 3,
    ),
    "rpm_labor": (
        lambda x: x,
        lambda rpm, labor: ((labor - 12 if labor >= 12 else 20 + labor) << 3) | rpm & 0b111,
    ),
}

C = TypeVar("C", bound="CompData")
R = TypeVar("R", bound=CommandReq)


class CompData(ABC, Generic[R]):
    """
    CompData and it's subclasses are used to hold component state
    received from the Lionel Base 3 on Engines, Trains, Routes, Switches,
    and Accessories. Using the appropriate dict of CompDataHandler objects,
    encoded byte strings from the Base 3 are parsed into Python types. This
    information is used by ComponentState subclasses to maintain the current
    state of a specific component, as well as communicate that state to
    PyTrain clients from the server

    Each CompData subclass defines a set of fields that will contain the
    state information. By overriding __getattr__ and __setattr__, we can
    access the state as simple python properties as well as set them. Only
    those fields defined in the subclass are accessible; attempting to access
    others results in an AttributeError exception.
    """

    __metaclass__ = ABCMeta

    @classmethod
    def from_bytes(cls, data: bytes, scope: CommandScope, tmcc_id: int = None) -> C:
        """
        Parse byte packet into a CompData object, based on scope.
        """
        if scope == CommandScope.ENGINE:
            return EngineData(data, tmcc_id=tmcc_id)
        elif scope == CommandScope.TRAIN:
            return TrainData(data, tmcc_id=tmcc_id)
        elif scope == CommandScope.ACC:
            return AccessoryData(data, tmcc_id=tmcc_id)
        elif scope == CommandScope.SWITCH:
            return SwitchData(data, tmcc_id=tmcc_id)
        elif scope == CommandScope.ROUTE:
            return RouteData(data, tmcc_id=tmcc_id)
        else:
            raise ValueError(f"Invalid scope: {scope}")

    @classmethod
    def encode_rpm_labor(cls, rpm: int, labor: int) -> int:
        conv = CONVERSIONS.get("rpm_labor")
        return conv[1](rpm, labor)

    @classmethod
    def rpm_labor_to_pkg(cls, rpm: int, labor: int) -> UpdatePkg:
        return UpdatePkg("rpm_labor", 0x0C, 1, default_to_func(cls.encode_rpm_labor(rpm, labor)))

    # noinspection PyTypeChecker
    @classmethod
    def request_to_updates(cls, req: R) -> list[UpdatePkg] | None:
        """
        Pushes derivative state changes to Base 3 in response to a CommandReq.
        For example, when an engine is reset (Numeric 0), its speed and RPM
        must be reset to zero, and its labor must be set to 12. Derivative
        states are maintained in a dict keyed by the enum name corresponding
        to the CommandReq.
        """
        if not isinstance(req, CommandReq):
            raise AttributeError(f"'Argument is not a CommandReq: {req}'")

        update_pkgs: list[UpdatePkg] = []
        cmd = req.command
        updates = REQUEST_TO_UPDATES_MAP.get(cmd.name, None)
        if updates is None:
            return None
        for update in updates:
            if isinstance(update, tuple) and len(update) >= 1:
                field = sub_field = update[0]
                addr = FIELD_TO_ADDR_ENGINE_MAP.get(field, None)
                # special case for rpm/labor
                if addr is None and field in {"rpm", "labor"}:
                    field = "rpm_labor"
                    addr = FIELD_TO_ADDR_ENGINE_MAP.get(field, None)
                if addr is None:
                    log.warning(f"Field {field} not found in FIELD_TO_ADDR_ENGINE_MAP ({req})")
                    continue
                handler = BASE_MEMORY_ENGINE_READ_MAP.get(addr, None)
                if handler is None:
                    if addr is None:
                        log.warning(f"Field {field} handler not found in BASE_MEMORY_ENGINE_READ_MAP ({req})")
                    continue
                if len(update) == 1:
                    # have to convert data from command into Base 3 format
                    # is there a converter?
                    conv_tpl = CONVERSIONS.get(field, None)
                    if conv_tpl:
                        # more special case handling for rpm/labor
                        if sub_field != field and field == "rpm_labor":
                            from ..db.component_state_store import ComponentStateStore

                            state = ComponentStateStore.build().get_state(req.scope, req.address, False)
                            assert state is not None
                            with state.synchronizer:
                                if sub_field == "rpm":
                                    rpm = req.data
                                    labor = state.labor
                                else:
                                    rpm = state.rpm
                                    labor = req.data
                            base_value = conv_tpl[1](rpm, labor)
                        elif sub_field == "smoke":
                            if cmd.is_tmcc1:
                                base_value = conv_tpl[1](TMCC1_TO_BASE_SMOKE_MAP, req.data)
                            else:
                                base_value = conv_tpl[1](TMCC1_TO_BASE_SMOKE_MAP, req.data)
                        else:
                            base_value = conv_tpl[1](req.data)
                    else:
                        base_value = req.data
                else:
                    base_value = update[1](0)
                data_bytes = handler.to_bytes(base_value)
                if len(data_bytes) < handler.length:
                    data_bytes += b"\xff" * (handler.length - len(data_bytes))
                update_pkgs.append(UpdatePkg(field, addr, handler.length, data_bytes))
        return update_pkgs

    @abstractmethod
    def __init__(self, data: bytes | None, scope: CommandScope, tmcc_id: int = None) -> None:
        super().__init__()
        self._tmcc_id: int | None = tmcc_id
        self._scope = scope
        self._road_name_len: int | None = None
        self._road_name: str | None = None
        self._road_number_len: int | None = None
        self._road_number: str | None = None
        self._next_link: int | None = None
        self._prev_link: int | None = None

        # load the data from the byte string
        if data:
            self._parse_bytes(data, SCOPE_TO_COMP_MAP.get(self.scope))

    def __repr__(self) -> str:
        nm = nu = ""
        if self.road_name is not None:
            nm = f" {title(self.road_name)}"
        if self.road_number is not None:
            nu = f" #{self.road_number}"
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
            return f"{self.scope.title} {self.tmcc_id:04}: {self.payload()}{nm}{nu}"
        else:
            return f"{self.scope.title} {self.tmcc_id:>2}: {self.payload()}{nm}{nu}"

    def __getattr__(self, name: str) -> Any:
        if name in self.__dict__:
            return self.__dict__[name]
        if "_" + name in self.__dict__:
            return self.__dict__["_" + name]
        elif name.endswith("_tmcc") and name.replace("_tmcc", "") in CONVERSIONS:
            name = name.replace("_tmcc", "")
            tpl = CONVERSIONS[name]
            # special case labor/rpm
            if name in {"rpm", "labor"}:
                name = "rpm_labor"
            value = self.__dict__["_" + name]
            if name == "smoke" and isinstance(self, EngineData):
                if self.is_legacy:
                    map_dict = BASE_TO_TMCC2_SMOKE_MAP
                    default = TMCC2EffectsControl.SMOKE_OFF
                else:
                    map_dict = BASE_TO_TMCC1_SMOKE_MAP
                    default = TMCC1EngineCommandEnum.SMOKE_OFF
                return tpl[0](map_dict, value, default) if value is not None else value
            else:
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
            # Special case rpm and labor, as they are encoded into a single value.
            # We determine the original values of each, then use our conversion
            # mechanism to use the conversion function to set the combined value.
            if name in {"rpm", "labor"}:
                rpm = self.rpm_tmcc if name == "labor" else value
                labor = self.labor_tmcc if name == "rpm" else value
                self.rpm_labor_tmcc = (rpm, labor)
            elif name == "smoke" and isinstance(self, EngineData):
                map_dict = TMCC2_TO_BASE_SMOKE_MAP if self.is_legacy is True else TMCC1_TO_BASE_SMOKE_MAP
                self.__dict__["_" + name] = tpl[1](map_dict, value) if value is not None else value
            else:
                # For RPM or Labor, we have to pass the 2 raw values to the conversion function
                # as a tuple, thus requiring the isinstance check below.
                if isinstance(value, tuple):
                    self.__dict__["_" + name] = tpl[1](*value) if value is not None else value
                else:
                    self.__dict__["_" + name] = tpl[1](value) if value is not None else value
        else:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def _signal_initializing(self) -> None:
        self.__dict__["__initializing__"] = True

    def __signal_initialized(self) -> None:
        self.__dict__["__initializing__"] = False

    def payload(self) -> str:
        return ""

    def as_bytes(self) -> bytes:
        comp_map = SCOPE_TO_COMP_MAP.get(self.scope)
        schema = {key: comp_map[key] for key in sorted(comp_map.keys())}
        if self.tmcc_id <= 99:
            # delete any entries that are 4-digit specific
            for k in list(schema.keys()):
                if schema[k].is_d4_only:
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
        rec_len = PdiReq.scope_record_length(self.scope)
        if len(byte_str) < rec_len:
            byte_str += b"\xff" * (rec_len - len(byte_str))

        return byte_str

    def _parse_bytes(self, data: bytes, pmap: dict) -> None:
        if data is None:
            print(f"TMCC_ID: {self.tmcc_id} Scope: {self.scope}")
        data_len = len(data)
        for k, v in pmap.items():
            if not isinstance(v, CompDataHandler):
                continue
            item_len = v.length
            if data_len >= ((k + item_len) - 1) and hasattr(self, v.field) and getattr(self, v.field) is None:
                func = v.from_bytes
                try:
                    value = func(data[k : k + item_len])
                    if hasattr(self, v.field):
                        setattr(self, v.field, value)
                except Exception as e:
                    log.exception(f"Exception decoding {v.field} {e}", exc_info=e)


class EngineData(CompData):
    def __init__(
        self,
        data: bytes | None,
        tmcc_id: int = None,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        self._signal_initializing()
        self._bt_id: int | None = None
        self._control_type: int | None = None
        self._engine_class: int | None = None
        self._engine_type: int | None = None
        self._max_speed: int | None = None
        self._momentum: int | None = None
        self._rpm_labor: int | None = None
        self._smoke: int | None = None
        self._sound_type: int | None = None
        self._speed: int | None = None
        self._speed_limit: int | None = None
        self._target_speed: int | None = None
        self._timestamp: int | None = None
        self._train_brake: int | None = None
        self._tsdb_left: int | None = None
        self._tsdb_right: int | None = None
        self._fuel_level: int | None = None
        self._water_level: int | None = None
        self._unk_2: int | None = None
        self._unk_3: int | None = None
        self._unk_6: int | None = None
        self._unk_a: int | None = None
        self._unk_b: int | None = None
        self._unk_f: int | None = None
        self._unk_11: int | None = None
        self._unk_12: int | None = None
        self._unk_13: int | None = None
        self._unk_17: int | None = None
        self._unk_5c: int | None = None
        self._unk_5e: int | None = None
        self._unk_68: int | None = None
        super().__init__(data, scope, tmcc_id=tmcc_id)

    @property
    def is_legacy(self) -> bool:
        return self._control_type == LEGACY_CONTROL_TYPE


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

    def __init__(self, data: bytes | None, tmcc_id: int = None) -> None:
        self._signal_initializing()
        self._consist_flags: int | None = None
        self._consist_comps: list[ConsistComponent] | None = None
        super().__init__(data, tmcc_id=tmcc_id, scope=CommandScope.TRAIN)


class SwitchData(CompData):
    """
    Represents the SwitchData class which extends the CompData class.

    This class is designed to handle and initialize switch-related data operations,
    using the base functionality provided by the CompData class. It incorporates
    specialized operations required for switch data management and processing. Primarily,
    it initializes TMCC ID, Name, Number, and state during its construction phase.
    """

    def __init__(self, data: bytes, tmcc_id: int = None) -> None:
        self._signal_initializing()
        super().__init__(data, scope=CommandScope.SWITCH, tmcc_id=tmcc_id)


class AccessoryData(CompData):
    def __init__(self, data: bytes, tmcc_id: int = None) -> None:
        self._signal_initializing()
        self._device_code: int | None = None
        super().__init__(data, scope=CommandScope.ACC, tmcc_id=tmcc_id)


class RouteData(CompData):
    def __init__(self, data: bytes, tmcc_id: int = None) -> None:
        self._signal_initializing()
        self._components: list[RouteComponent] | None = None
        super().__init__(data, scope=CommandScope.ROUTE, tmcc_id=tmcc_id)

    def payload(self) -> str:
        sw = ""
        if self._components:
            sw = "Switches: "
            sep = ""
            for c in self._components:
                state = "thru" if c.is_thru else "out"
                sw += f"{sep}{c.tmcc_id:>2} [{state}]"
                sep = ", "
        return sw


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
        return self._comp_data is not None and self._comp_data_record is True

    def initialize(self, scope: CommandScope, tmcc_id: int) -> None:
        data_len = PdiReq.scope_record_length(scope)
        if scope == CommandScope.SWITCH:
            # noinspection PyTypeChecker
            self._comp_data = SwitchData(b"\xff" * data_len, tmcc_id)
        elif scope == CommandScope.ENGINE:
            self._comp_data = EngineData(b"\xff" * data_len, tmcc_id)
        elif scope == CommandScope.TRAIN:
            self._comp_data = TrainData(b"\xff" * data_len, tmcc_id)
        elif scope == CommandScope.ROUTE:
            self._comp_data = RouteData(b"\xff" * data_len, tmcc_id)
        elif scope == CommandScope.ACC:
            self._comp_data = AccessoryData(b"\xff" * data_len, tmcc_id)
        else:
            raise NotImplementedError(f"Unknown scope {scope.name}")
        self._comp_data_record = True
