"""PyTrain state adapter for the presentation package."""

from __future__ import annotations

from threading import RLock

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.engine_state import EngineState, TrainState
from pytrain.db.state_watcher import StateWatcher
from pytrain.protocol.constants import CommandScope

from pytrain_ui.contracts import EngineViewState, StateListener, Unsubscribe

EngineOrTrainState = EngineState | TrainState


def _enum_name(value: object | None) -> str:
    return "" if value is None else str(getattr(value, "name", value))


def _int_value(value: object | None) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def snapshot_from_state(state: EngineOrTrainState) -> EngineViewState:
    default_speed_max = 199 if state.is_legacy else 31
    speed_max = _int_value(getattr(state, "speed_max", default_speed_max)) or default_speed_max
    return EngineViewState(
        scope=state.scope.name,
        tmcc_id=state.tmcc_id,
        road_name=str(getattr(state, "road_name", "") or getattr(state, "name", "") or ""),
        road_number=str(getattr(state, "road_number", "") or ""),
        speed=_int_value(getattr(state, "speed", 0)),
        target_speed=_int_value(getattr(state, "target_speed", 0)),
        speed_max=speed_max,
        direction=_enum_name(getattr(state, "direction", None)),
        momentum=_int_value(getattr(state, "momentum", 0)),
        smoke=_int_value(getattr(state, "smoke", 0)),
        labor=_int_value(getattr(state, "labor", 0)),
        rpm=_int_value(getattr(state, "rpm", 0)),
    )


class PyTrainCabStateAdapter:
    def __init__(self, scope: CommandScope, tmcc_id: int) -> None:
        if scope not in {CommandScope.ENGINE, CommandScope.TRAIN}:
            raise ValueError(f"Cab scope must be ENGINE or TRAIN, not {scope}")
        state = ComponentStateStore.get_state(scope, tmcc_id, create=True)
        if not isinstance(state, (EngineState, TrainState)):
            raise TypeError(f"Expected engine/train state, got {type(state).__name__}")
        self._state = state
        self._listeners: set[StateListener] = set()
        self._lock = RLock()
        self._snapshot = snapshot_from_state(state)
        self._watcher = StateWatcher(state, self._on_state_change)

    @property
    def state(self) -> EngineOrTrainState:
        return self._state

    def current(self) -> EngineViewState:
        with self._lock:
            return self._snapshot

    def subscribe(self, listener: StateListener) -> Unsubscribe:
        with self._lock:
            self._listeners.add(listener)
        listener(self.current())

        def unsubscribe() -> None:
            with self._lock:
                self._listeners.discard(listener)

        return unsubscribe

    def shutdown(self) -> None:
        self._watcher.shutdown()
        with self._lock:
            self._listeners.clear()

    def _on_state_change(self) -> None:
        snapshot = snapshot_from_state(self._state)
        with self._lock:
            self._snapshot = snapshot
            listeners = tuple(self._listeners)
        for listener in listeners:
            listener(snapshot)
