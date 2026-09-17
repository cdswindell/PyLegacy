"""Selected and active engine working set for the Qt cab."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.state_watcher import StateWatcher
from pytrain.protocol.constants import CommandScope


class SelectedEngineController(QObject):
    """Track engines selected by the operator and engines active on the railroad."""

    selectionChanged = Signal()

    def __init__(self, cab, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cab = cab
        self._selected_ids: list[int] = []
        self._active_ids: list[int] = []
        self._dismissed_activity: dict[int, tuple] = {}
        self._watchers: dict[int, StateWatcher] = {}
        self._sensor_watchers: dict[int, StateWatcher] = {}
        self._operating_state: dict[int, tuple] = {}
        self._dispatcher = CommandDispatcher.get() if CommandDispatcher.is_built() else None
        self._cab.stateChanged.connect(self._sync_current_target)
        self._install_watchers()
        self._install_sensor_watchers()
        if self._dispatcher is not None:
            self._dispatcher.subscribe(self._engine_command, CommandScope.ENGINE)
        self._sync_current_target()

    def close(self) -> None:
        if self._dispatcher is not None:
            self._dispatcher.unsubscribe(self._engine_command, CommandScope.ENGINE)
            self._dispatcher = None
        for watcher in self._watchers.values():
            watcher.shutdown()
        self._watchers.clear()
        for watcher in self._sensor_watchers.values():
            watcher.shutdown()
        self._sensor_watchers.clear()

    @staticmethod
    def _operating_signature(state) -> tuple:
        return (
            getattr(state, "speed", None),
            getattr(state, "target_speed", None),
            getattr(state, "direction", None),
            getattr(state, "train_brake", None),
            getattr(state, "momentum", None),
            getattr(state, "smoke", None),
            getattr(state, "labor", None),
            getattr(state, "rpm", None),
        )

    @staticmethod
    def _physical_key(tmcc_id: int) -> tuple[str, int]:
        """Return stable physical identity when Bluetooth identity is known."""
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        bt_id = int(getattr(state, "bt_int", 0) or 0) if state is not None else 0
        return ("bt", bt_id) if bt_id else ("tmcc", tmcc_id)

    def _same_physical_engine(self, left: int, right: int) -> bool:
        return self._physical_key(left) == self._physical_key(right)

    def _dedupe_physical(self, ids: list[int]) -> list[int]:
        result: list[int] = []
        seen: set[tuple[str, int]] = set()
        for tmcc_id in ids:
            key = self._physical_key(tmcc_id)
            if key not in seen:
                seen.add(key)
                result.append(tmcc_id)
        return result

    def _install_watchers(self) -> None:
        for state in ComponentStateStore.get().get_all(CommandScope.ENGINE):
            tmcc_id = int(state.tmcc_id)
            if tmcc_id in self._watchers:
                continue
            self._operating_state[tmcc_id] = self._operating_signature(state)
            self._watchers[tmcc_id] = StateWatcher(state, lambda s=state: self._engine_state_changed(s))

    def _install_sensor_watchers(self) -> None:
        for state in ComponentStateStore.get().get_all(CommandScope.IRDA):
            sensor_id = int(state.tmcc_id)
            if sensor_id not in self._sensor_watchers:
                self._sensor_watchers[sensor_id] = StateWatcher(state, lambda s=state: self._sensor_track_changed(s))

    def _mark_active(self, tmcc_id: int) -> None:
        if tmcc_id <= 0:
            return
        if ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False) is None:
            return
        self._dismissed_activity.pop(tmcc_id, None)
        if tmcc_id not in self._active_ids:
            self._active_ids.append(tmcc_id)
        self.selectionChanged.emit()

    def _engine_command(self, command) -> None:
        """Treat received engine command traffic as activity even if state is unchanged."""
        if getattr(command, "scope", None) != CommandScope.ENGINE:
            return
        tmcc_id = int(getattr(command, "address", 0) or 0)
        self._install_watchers()
        self._install_sensor_watchers()
        self._mark_active(tmcc_id)

    def _sensor_track_changed(self, state) -> None:
        """A Sensor Track sighting makes the already-resolved engine active."""
        if getattr(state, "is_train", False):
            return
        tmcc_id = int(getattr(state, "last_engine_id", 0) or 0)
        self._mark_active(tmcc_id)

    def _engine_state_changed(self, state) -> None:
        tmcc_id = int(state.tmcc_id)
        signature = self._operating_signature(state)
        previous = self._operating_state.get(tmcc_id)
        self._operating_state[tmcc_id] = signature
        if previous is not None and signature != previous:
            if self._dismissed_activity.get(tmcc_id) != signature:
                self._dismissed_activity.pop(tmcc_id, None)
                if tmcc_id not in self._active_ids:
                    self._active_ids.append(tmcc_id)
        self.selectionChanged.emit()

    def _sync_current_target(self) -> None:
        if self._cab.scope != CommandScope.ENGINE.name:
            self.selectionChanged.emit()
            return
        tmcc_id = self._cab.tmccId
        if tmcc_id in self._selected_ids:
            self._selected_ids.remove(tmcc_id)
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
    def _row(cls, tmcc_id: int, current_id: int, selected: bool, active: bool) -> dict:
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
                "selected": selected,
                "active": active,
            }
        return {
            "tmccId": tmcc_id,
            "roadName": str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip(),
            "roadNumber": str(getattr(state, "road_number", "") or "").strip(),
            "direction": cls._direction(state),
            "smoke": cls._smoke(state),
            "speed": int(getattr(state, "speed", 0) or 0),
            "current": tmcc_id == current_id,
            "selected": selected,
            "active": active,
        }

    def _display_ids(self) -> list[int]:
        return self._dedupe_physical(self._selected_ids + self._active_ids)

    def _is_selected(self, tmcc_id: int) -> bool:
        return any(self._same_physical_engine(tmcc_id, candidate) for candidate in self._selected_ids)

    def _is_active(self, tmcc_id: int) -> bool:
        return any(self._same_physical_engine(tmcc_id, candidate) for candidate in self._active_ids)

    @Property(list, notify=selectionChanged)
    def selectedEngines(self) -> list[dict]:
        current_id = self._cab.tmccId if self._cab.scope == CommandScope.ENGINE.name else -1
        return [
            self._row(tmcc_id, current_id, self._is_selected(tmcc_id), self._is_active(tmcc_id))
            for tmcc_id in self._display_ids()
        ]

    @Property(int, notify=selectionChanged)
    def count(self) -> int:
        return len(self._display_ids())

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
        display_ids = self._display_ids()
        if tmcc_id not in display_ids or len(display_ids) <= 1:
            return
        key = self._physical_key(tmcc_id)
        was_current = self._cab.scope == CommandScope.ENGINE.name and self._physical_key(self._cab.tmccId) == key
        aliases = [
            candidate for candidate in self._selected_ids + self._active_ids if self._physical_key(candidate) == key
        ]
        self._selected_ids = [candidate for candidate in self._selected_ids if self._physical_key(candidate) != key]
        self._active_ids = [candidate for candidate in self._active_ids if self._physical_key(candidate) != key]
        for candidate in aliases:
            state = ComponentStateStore.get_state(CommandScope.ENGINE, candidate, create=False)
            if state is not None:
                self._dismissed_activity[candidate] = self._operating_signature(state)
        if was_current:
            remaining = self._display_ids()
            if remaining:
                self.selectEngine(remaining[0])
        else:
            self.selectionChanged.emit()

    @Slot(int)
    def selectRelative(self, delta: int) -> None:
        # Artwork swiping intentionally traverses explicit selections, not engines
        # that merely appeared because command or Sensor Track activity was observed.
        ids = self._dedupe_physical(self._selected_ids)
        if len(ids) < 2 or self._cab.scope != CommandScope.ENGINE.name:
            return
        current_key = self._physical_key(self._cab.tmccId)
        try:
            index = next(i for i, tmcc_id in enumerate(ids) if self._physical_key(tmcc_id) == current_key)
        except StopIteration:
            return
        tmcc_id = ids[(index + delta) % len(ids)]
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        if state is not None:
            self._cab._switch_target(CommandScope.ENGINE, tmcc_id)
