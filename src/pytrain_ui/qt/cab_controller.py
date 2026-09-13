"""Qt bridge exposing a PyTrain cab through QObject properties and slots."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.constants import CommandScope
from pytrain.utils.path_utils import find_file

from pytrain_ui.adapters import PyTrainCabCommandAdapter, PyTrainCabStateAdapter
from pytrain_ui.contracts import EngineViewState

_ENGINE_ARTWORK = {
    "ACELA": "acela.jpg",
    "CRANE": "generic_crane_car.jpg",
    "DIESEL": "generic_diesel.jpg",
    "DIESEL_PULLMOR": "generic_diesel.jpg",
    "DIESEL_SWITCHER": "generic_diesel_switcher.jpg",
    "ELECTRIC": "generic_electric.jpg",
    "STEAM": "generic_steam.jpg",
}


class CabController(QObject):
    stateChanged = Signal()
    rosterChanged = Signal()

    def __init__(self, scope: CommandScope, tmcc_id: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state_port = None
        self._command_port = None
        self._unsubscribe = None
        self._snapshot = EngineViewState(scope=scope.name, tmcc_id=tmcc_id)
        self._targets: list[tuple[CommandScope, int, str]] = []
        self._target_labels: list[str] = []
        self._target_index = -1
        self._reload_roster()
        self._switch_target(scope, tmcc_id)

    def close(self) -> None:
        self._release_target()

    def _release_target(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._state_port is not None:
            self._state_port.shutdown()
            self._state_port = None
        self._command_port = None

    def _reload_roster(self) -> None:
        store = ComponentStateStore.get()
        targets: list[tuple[CommandScope, int, str]] = []
        for scope in (CommandScope.ENGINE, CommandScope.TRAIN):
            for state in store.get_all(scope):
                road_name = str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip()
                road_number = str(getattr(state, "road_number", "") or "").strip()
                detail = " ".join(part for part in (road_name, road_number) if part)
                label = f"{scope.label.title()} {state.tmcc_id}"
                if detail:
                    label += f" — {detail}"
                targets.append((scope, state.tmcc_id, label))
        targets.sort(key=lambda item: (0 if item[0] == CommandScope.ENGINE else 1, item[1]))
        self._targets = targets
        self._target_labels = [item[2] for item in targets]
        self.rosterChanged.emit()

    def _switch_target(self, scope: CommandScope, tmcc_id: int) -> None:
        self._release_target()
        self._state_port = PyTrainCabStateAdapter(scope, tmcc_id)
        self._command_port = PyTrainCabCommandAdapter(self._state_port)
        self._snapshot = self._state_port.current()
        self._unsubscribe = self._state_port.subscribe(self._on_state)
        self._target_index = next(
            (i for i, item in enumerate(self._targets) if item[0] == scope and item[1] == tmcc_id),
            -1,
        )
        self.stateChanged.emit()
        self.rosterChanged.emit()

    def _on_state(self, snapshot: EngineViewState) -> None:
        self._snapshot = snapshot
        self.stateChanged.emit()

    def _artwork_state(self):
        state = self._state_port.state if self._state_port is not None else None
        if state is not None and state.scope == CommandScope.TRAIN:
            head_id = int(getattr(state, "head_tmcc_id", 0) or 0)
            if head_id:
                head = ComponentStateStore.get_state(CommandScope.ENGINE, head_id, create=False)
                if head is not None:
                    state = head
        return state

    @Property(list, notify=rosterChanged)
    def targetLabels(self) -> list[str]:
        return self._target_labels

    @Property(int, notify=rosterChanged)
    def targetIndex(self) -> int:
        return self._target_index

    @Slot(int)
    def selectTarget(self, index: int) -> None:
        if 0 <= index < len(self._targets) and index != self._target_index:
            scope, tmcc_id, _ = self._targets[index]
            self._switch_target(scope, tmcc_id)

    @Slot()
    def refreshRoster(self) -> None:
        current_scope = CommandScope[self.scope]
        current_id = self.tmccId
        self._reload_roster()
        self._target_index = next(
            (i for i, item in enumerate(self._targets) if item[0] == current_scope and item[1] == current_id),
            -1,
        )
        self.rosterChanged.emit()

    @Property(str, notify=stateChanged)
    def scope(self) -> str:
        return self._snapshot.scope

    @Property(int, notify=stateChanged)
    def tmccId(self) -> int:
        return self._snapshot.tmcc_id

    @Property(str, notify=stateChanged)
    def roadName(self) -> str:
        return self._snapshot.road_name

    @Property(str, notify=stateChanged)
    def roadNumber(self) -> str:
        return self._snapshot.road_number

    @Property(str, notify=stateChanged)
    def artworkSource(self) -> str:
        state = self._artwork_state()
        engine_type = getattr(state, "engine_type_enum", None)
        name = str(getattr(engine_type, "name", "DIESEL") or "DIESEL")
        filename = _ENGINE_ARTWORK.get(name, "generic_diesel.jpg")
        path = find_file(filename)
        return QUrl.fromLocalFile(str(path)).toString() if path else ""

    @Property(int, notify=stateChanged)
    def speed(self) -> int:
        return self._snapshot.speed

    @Property(int, notify=stateChanged)
    def targetSpeed(self) -> int:
        return self._snapshot.target_speed

    @Property(int, notify=stateChanged)
    def speedMax(self) -> int:
        return self._snapshot.speed_max

    @Property(str, notify=stateChanged)
    def direction(self) -> str:
        return self._snapshot.direction

    @Property(int, notify=stateChanged)
    def momentum(self) -> int:
        return self._snapshot.momentum

    @Property(int, notify=stateChanged)
    def smoke(self) -> int:
        return self._snapshot.smoke

    @Property(int, notify=stateChanged)
    def labor(self) -> int:
        return self._snapshot.labor

    @Property(int, notify=stateChanged)
    def rpm(self) -> int:
        return self._snapshot.rpm

    @Slot(int)
    def setSpeed(self, speed: int) -> None:
        self._command_port.set_speed(speed)

    @Slot(int)
    def changeSpeed(self, delta: int) -> None:
        self._command_port.change_speed(delta)

    @Slot(str)
    def setDirection(self, direction: str) -> None:
        self._command_port.set_direction(direction)

    @Slot()
    def bell(self) -> None:
        self._command_port.bell()

    @Slot(bool)
    def horn(self, active: bool) -> None:
        self._command_port.horn(active)

    @Slot(bool)
    def boost(self, active: bool) -> None:
        self._command_port.boost(active)

    @Slot(bool)
    def brake(self, active: bool) -> None:
        self._command_port.brake(active)

    @Slot()
    def stop(self) -> None:
        self._command_port.stop()

    @Slot()
    def reset(self) -> None:
        self._command_port.reset()
