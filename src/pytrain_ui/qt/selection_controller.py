"""Selected-engine working set for the Qt cab."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.constants import CommandScope


class SelectedEngineController(QObject):
    """Track engines explicitly selected by the operator."""

    selectionChanged = Signal()

    def __init__(self, cab, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cab = cab
        self._selected_ids: list[int] = []
        self._cab.stateChanged.connect(self._sync_current_target)
        self._sync_current_target()

    def _sync_current_target(self) -> None:
        if self._cab.scope != CommandScope.ENGINE.name:
            self.selectionChanged.emit()
            return
        tmcc_id = self._cab.tmccId
        if tmcc_id not in self._selected_ids:
            self._selected_ids.insert(0, tmcc_id)
        self.selectionChanged.emit()

    @staticmethod
    def _direction(state) -> str:
        direction = getattr(state, "direction", None)
        name = str(getattr(direction, "name", direction) or "").upper()
        if "FORWARD" in name:
            return "F"
        if "REVERSE" in name:
            return "R"
        return "-"

    @staticmethod
    def _smoke(state) -> str:
        smoke = getattr(state, "smoke", None)
        if smoke is None:
            smoke = getattr(state, "smoke_level", None)
        name = str(getattr(smoke, "name", smoke) or "").upper()
        if "HIGH" in name:
            return "H"
        if "MED" in name:
            return "M"
        if "LOW" in name:
            return "L"
        if "OFF" in name or "NONE" in name or "ZERO" in name:
            return "-"
        if name in {"0", "1", "2", "3"}:
            return {"0": "-", "1": "L", "2": "M", "3": "H"}[name]
        return "+" if name else "-"

    @classmethod
    def _row(cls, tmcc_id: int, current_id: int) -> dict:
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        if state is None:
            return {
                "tmccId": tmcc_id,
                "roadName": "",
                "roadNumber": "",
                "direction": "-",
                "smoke": "-",
                "speed": 0,
                "current": tmcc_id == current_id,
            }
        return {
            "tmccId": tmcc_id,
            "roadName": str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip(),
            "roadNumber": str(getattr(state, "road_number", "") or "").strip(),
            "direction": cls._direction(state),
            "smoke": cls._smoke(state),
            "speed": int(getattr(state, "speed", 0) or 0),
            "current": tmcc_id == current_id,
        }

    @Property(list, notify=selectionChanged)
    def selectedEngines(self) -> list[dict]:
        current_id = self._cab.tmccId if self._cab.scope == CommandScope.ENGINE.name else -1
        return [self._row(tmcc_id, current_id) for tmcc_id in self._selected_ids]

    @Property(int, notify=selectionChanged)
    def count(self) -> int:
        return len(self._selected_ids)

    @Slot(int)
    def selectEngine(self, tmcc_id: int) -> None:
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        if state is None:
            return
        if tmcc_id in self._selected_ids:
            self._selected_ids.remove(tmcc_id)
        self._selected_ids.insert(0, tmcc_id)
        if self._cab.scope != CommandScope.ENGINE.name or self._cab.tmccId != tmcc_id:
            self._cab._switch_target(CommandScope.ENGINE, tmcc_id)
        else:
            self.selectionChanged.emit()

    @Slot(int)
    def dismissEngine(self, tmcc_id: int) -> None:
        if tmcc_id not in self._selected_ids or len(self._selected_ids) <= 1:
            return
        index = self._selected_ids.index(tmcc_id)
        was_current = self._cab.scope == CommandScope.ENGINE.name and self._cab.tmccId == tmcc_id
        self._selected_ids.remove(tmcc_id)
        if was_current:
            next_index = min(index, len(self._selected_ids) - 1)
            self.selectEngine(self._selected_ids[next_index])
        else:
            self.selectionChanged.emit()

    @Slot(int)
    def selectRelative(self, delta: int) -> None:
        if len(self._selected_ids) < 2 or self._cab.scope != CommandScope.ENGINE.name:
            return
        try:
            index = self._selected_ids.index(self._cab.tmccId)
        except ValueError:
            return
        self.selectEngine(self._selected_ids[(index + delta) % len(self._selected_ids)])
