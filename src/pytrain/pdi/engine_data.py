from .base_req import BASE_MEMORY_READ_MAP
from ..protocol.constants import CommandScope


class EngineData:
    def __init__(self, data: bytes) -> None:
        self._tmcc_id: int | None = None
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
        self._tsdb_right: int | None = None
        self._smoke: int | None = None
        self._speed_limit: int | None = None
        self._max_speed: int | None = None
        self._timestamp: int | None = None
        self._scope = CommandScope.ENGINE

        # load the data from the byte string
        data_len = len(data)
        for k, v in BASE_MEMORY_READ_MAP.items():
            if isinstance(v, tuple) is False:
                continue
            item_len = v[2] if len(v) > 2 else 1
            if data_len >= ((k + item_len) - 1):
                value = v[1](data[k : k + item_len])
                print(f"{v[0]}: {value} {hasattr(self, v[0])}")
                if hasattr(self, v[0]):
                    setattr(self, v[0], value)


class TrainData(EngineData):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self._scope = CommandScope.TRAIN
