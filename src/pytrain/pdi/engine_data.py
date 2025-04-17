from typing import Any

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

BASE_MEMORY_ENGINE_READ_MAP = {
    0x04: ("_bt_id", lambda t: int.from_bytes(t, byteorder="little"), 2),
    0x07: ("_speed", lambda t: int.from_bytes(t, byteorder="little")),
    0x08: ("_target_speed", lambda t: int.from_bytes(t, byteorder="little")),
    0x09: ("_train_brake", lambda t: int.from_bytes(t, byteorder="little")),
    0x0C: ("_rpm_labor", lambda t: int.from_bytes(t, byteorder="little")),
    0x18: ("_momentum", lambda t: int.from_bytes(t, byteorder="little")),
    0x1F: ("_road_name", lambda t: PdiReq.decode_text(t), 31),
    0x3F: ("_road_number", lambda t: PdiReq.decode_text(t), 4),
    0x43: ("_engine_type", lambda t: int.from_bytes(t, byteorder="little")),
    0x44: ("_control_type", lambda t: int.from_bytes(t, byteorder="little")),
    0x45: ("_sound_type", lambda t: int.from_bytes(t, byteorder="little")),
    0x46: ("_engine_class", lambda t: int.from_bytes(t, byteorder="little")),
    0x59: ("_tsdb_left", lambda t: int.from_bytes(t, byteorder="little")),
    0x5B: ("_tsdb_right", lambda t: int.from_bytes(t, byteorder="little")),
    0x69: ("_smoke", lambda t: int.from_bytes(t, byteorder="little")),
    0x6A: ("_speed_limit", lambda t: int.from_bytes(t, byteorder="little")),
    0x6B: ("_max_speed", lambda t: int.from_bytes(t, byteorder="little")),
    0xB8: ("_tmcc_id", lambda t: int(PdiReq.decode_text(t)), 4),
    0xBC: ("_timestamp", lambda t: int.from_bytes(t[0:4], byteorder="little"), 4),
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


class EngineData:
    def __init__(self, data: bytes, tmcc_id: int = None) -> None:
        self._tmcc_id: int | None = tmcc_id
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
        self._scope = CommandScope.ENGINE

        # load the data from the byte string
        data_len = len(data)
        for k, v in BASE_MEMORY_ENGINE_READ_MAP.items():
            if isinstance(v, tuple) is False:
                continue
            item_len = v[2] if len(v) > 2 else 1
            if data_len >= ((k + item_len) - 1) and hasattr(self, v[0]) and getattr(self, v[0]) is None:
                value = v[1](data[k : k + item_len])
                if hasattr(self, v[0]):
                    setattr(self, v[0], value)
                else:
                    raise AttributeError(f"'{type(self).__name__}' has no attribute '{v[0]}'")

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


class TrainData(EngineData):
    def __init__(self, data: bytes, tmcc_id: int = None) -> None:
        super().__init__(data, tmcc_id=tmcc_id)
        self._scope = CommandScope.TRAIN
