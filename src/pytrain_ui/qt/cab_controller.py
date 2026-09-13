"""Qt bridge exposing a PyTrain cab through QObject properties and slots."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain_ui.contracts import EngineViewState


class CabController(QObject):
    stateChanged = Signal()

    def __init__(self, state_port, command_port, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state_port = state_port
        self._command_port = command_port
        self._snapshot = state_port.current()
        self._unsubscribe = state_port.subscribe(self._on_state)

    def close(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def _on_state(self, snapshot: EngineViewState) -> None:
        self._snapshot = snapshot
        self.stateChanged.emit()

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
