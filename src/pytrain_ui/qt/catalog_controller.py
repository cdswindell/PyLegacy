"""Structured roster model for Qt catalog views."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.state_watcher import StateWatcher
from pytrain.protocol.constants import CommandScope


_ENGINE_TYPE_ALIASES = {
    "FREIGHT_SOUNDS": ("FREIGHT", "Freight"),
    "PASSENGER_CAR": ("PASSENGER", "Passenger"),
    "PASSENGER_CARS": ("PASSENGER", "Passenger"),
    "ACELA": ("ELECTRIC", "Electric"),
    "STEAM_PULLMOR": ("STEAM", "Steam"),
    "DIESEL_PULLMOR": ("DIESEL", "Diesel"),
}

_ENGINE_TYPE_PRIORITY = {
    "STEAM": 0,
    "DIESEL": 1,
    "ELECTRIC": 2,
    "STEAM_SWITCHER": 3,
    "DIESEL_SWITCHER": 4,
}


class EngineCatalogController(QObject):
    """Expose a live engine roster without requiring QML to parse display labels."""

    catalogChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engines: list[dict] = []
        self._type_filters: list[dict] = []
        self._watchers: dict[int, StateWatcher] = {}
        self._dispatcher = CommandDispatcher.get() if CommandDispatcher.is_built() else None
        if self._dispatcher is not None:
            self._dispatcher.subscribe(self._engine_command, CommandScope.ENGINE)
        self.reload()

    def close(self) -> None:
        if self._dispatcher is not None:
            self._dispatcher.unsubscribe(self._engine_command, CommandScope.ENGINE)
            self._dispatcher = None
        for watcher in self._watchers.values():
            watcher.shutdown()
        self._watchers.clear()

    @staticmethod
    def _engine_type(state) -> tuple[str, str]:
        engine_type = getattr(state, "engine_type_enum", None)
        raw_key = str(getattr(engine_type, "name", "") or "UNKNOWN")
        if raw_key in _ENGINE_TYPE_ALIASES:
            return _ENGINE_TYPE_ALIASES[raw_key]
        return raw_key, raw_key.replace("_", " ").title()

    @staticmethod
    def _type_sort_key(item: tuple[str, str]) -> tuple[int, str]:
        key, label = item
        priority = _ENGINE_TYPE_PRIORITY.get(key)
        if priority is not None:
            return priority, ""
        return len(_ENGINE_TYPE_PRIORITY), label.lower()

    def _engine_command(self, _command) -> None:
        # Command traffic can introduce a state that was not present when the Qt
        # catalog was created. Re-read the store and attach watchers as needed.
        self.reload()

    def _state_changed(self) -> None:
        self.reload()

    def _install_watchers(self, states) -> None:
        current_ids = {int(state.tmcc_id) for state in states}
        for tmcc_id in tuple(self._watchers):
            if tmcc_id not in current_ids:
                self._watchers.pop(tmcc_id).shutdown()
        for state in states:
            tmcc_id = int(state.tmcc_id)
            if tmcc_id not in self._watchers:
                self._watchers[tmcc_id] = StateWatcher(state, self._state_changed)

    @Slot()
    def reload(self) -> None:
        rows: list[dict] = []
        type_labels: dict[str, str] = {}
        states = sorted(ComponentStateStore.get().get_all(CommandScope.ENGINE), key=lambda state: state.tmcc_id)
        self._install_watchers(states)
        for state in states:
            road_name = str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip()
            road_number = str(getattr(state, "road_number", "") or "").strip()
            type_key, type_label = self._engine_type(state)
            type_labels[type_key] = type_label
            rows.append(
                {
                    "tmccId": int(state.tmcc_id),
                    "roadName": road_name,
                    "roadNumber": road_number,
                    "engineType": type_key,
                    "engineTypeLabel": type_label,
                }
            )
        self._engines = rows
        self._type_filters = [
            {"key": key, "label": label} for key, label in sorted(type_labels.items(), key=self._type_sort_key)
        ]
        self.catalogChanged.emit()

    @Property(list, notify=catalogChanged)
    def engines(self) -> list[dict]:
        return self._engines

    @Property(list, notify=catalogChanged)
    def typeFilters(self) -> list[dict]:
        return self._type_filters
