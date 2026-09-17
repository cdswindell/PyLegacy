"""Structured roster model for Qt catalog views."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.component_state_store import ComponentStateStore
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
    """Expose an engine roster without watching every engine's operating state."""

    catalogChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engines: list[dict] = []
        self._type_filters: list[dict] = []
        self._dispatcher = CommandDispatcher.get() if CommandDispatcher.is_built() else None
        if self._dispatcher is not None:
            self._dispatcher.subscribe(self._engine_command, CommandScope.ENGINE)
        self.reload()

    def close(self) -> None:
        if self._dispatcher is not None:
            self._dispatcher.unsubscribe(self._engine_command, CommandScope.ENGINE)
            self._dispatcher = None

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
        # catalog was created, so re-read the roster without watching every state.
        self.reload()

    @Slot()
    def reload(self) -> None:
        rows: list[dict] = []
        type_labels: dict[str, str] = {}
        states = sorted(ComponentStateStore.get().get_all(CommandScope.ENGINE), key=lambda state: state.tmcc_id)
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
