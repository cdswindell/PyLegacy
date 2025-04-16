class EngineData:
    def __init__(self) -> None:
        self._bt_id: int | None = None
        self._speed: int | None = None
        self._target_speed: int | None = None
        self._train_brake: int | None = None
