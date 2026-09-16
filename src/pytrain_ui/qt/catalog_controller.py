"""Structured roster model for Qt catalog views."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

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


class EngineCatalogController(QObject):
    """Expose engine roster data without requiring QML to parse display labels."""

    catalogChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engines: list[dict] = []
        self._type_filters: list[dict] = []
        self.reload()

    @staticmethod
    def _engine_type(state) -> tuple[str, str]:
        engine_type = getattr(state, "engine_type_enum", None)
        raw_key = str(getattr(engine_type, "name", "") or "UNKNOWN")
        if raw_key in _ENGINE_TYPE_ALIASES:
            return _ENGINE_TYPE_ALIASES[raw_key]
        return raw_key, raw_key.replace("_", " ").title()

    @Slot()
    def reload(self) -> None:
        rows: list[dict] = []
        type_labels: dict[str, str] = {}
        states = sorted(ComponentStateStore.get().get_all(CommandScope.ENGINE), key=lambda state: state.tmcc_id)
        for source_index, state in enumerate(states):
            road_name = str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip()
            road_number = str(getattr(state, "road_number", "") or "").strip()
            type_key, type_label = self._engine_type(state)
            type_labels[type_key] = type_label
            rows.append(
                {
                    "sourceIndex": source_index,
                    "tmccId": int(state.tmcc_id),
                    "roadName": road_name,
                    "roadNumber": road_number,
                    "engineType": type_key,
                    "engineTypeLabel": type_label,
                }
            )
        self._engines = rows
        self._type_filters = [
            {"key": key, "label": label}
            for key, label in sorted(type_labels.items(), key=lambda item: item[1].lower())
        ]
        self.catalogChanged.emit()

    @Property(list, notify=catalogChanged)
    def engines(self) -> list[dict]:
        return self._engines

    @Property(list, notify=catalogChanged)
    def typeFilters(self) -> list[dict]:
        return self._type_filters
