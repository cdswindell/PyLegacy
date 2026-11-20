"""Selected and active engine working set for the Qt cab."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.state_changes import StateChange
from pytrain.db.state_watcher import StateWatcher
from pytrain.protocol.constants import CommandScope

from .presentation import format_road_number, is_pseudo_train, target_kind


class SelectedEngineController(QObject):
    """Track engines selected by the operator and engines active on the railroad."""

    selectionChanged = Signal()
    trainCommandReceived = Signal(int)

    def __init__(self, cab, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cab = cab
        self._closed = False
        self._active_train_ids: list[int] = []
        self._train_operating_state: dict[int, tuple] = {}
        self._dismissed_trains: dict[int, tuple] = {}
        self._selected_ids: list[int] = []
        self._active_ids: list[int] = []
        self._operated_car_ids: set[int] = set()
        self._dismissed_activity: dict[int, tuple] = {}
        self._watchers: dict[int, StateWatcher] = {}
        self._sensor_watchers: dict[int, StateWatcher] = {}
        self._operating_state: dict[int, tuple] = {}
        self._dispatcher = CommandDispatcher.get() if CommandDispatcher.is_built() else None
        self._cab.stateChanged.connect(self.selectionChanged.emit)
        self._cab.stateChanged.connect(self._remember_current_train)
        self.trainCommandReceived.connect(self._mark_active_train)
        for train in ComponentStateStore.get().get_all(CommandScope.TRAIN):
            self._train_operating_state[train.tmcc_id] = self._operating_signature(train)
            if (
                not train.is_deleted
                and not is_pseudo_train(train)
                and (getattr(train, "speed", 0) or getattr(train, "target_speed", 0))
            ):
                self._active_train_ids.append(train.tmcc_id)
        self._remember_current_train()
        self._install_sensor_watchers()
        if self._dispatcher is not None:
            self._dispatcher.subscribe(self._engine_command, CommandScope.ENGINE)
            self._dispatcher.subscribe(self._train_command, CommandScope.TRAIN)

    def close(self) -> None:
        self._closed = True
        if self._dispatcher is not None:
            self._dispatcher.unsubscribe(self._engine_command, CommandScope.ENGINE)
            self._dispatcher.unsubscribe(self._train_command, CommandScope.TRAIN)
            self._dispatcher = None
        for watcher in self._watchers.values():
            watcher.shutdown()
        self._watchers.clear()
        for watcher in self._sensor_watchers.values():
            watcher.shutdown()
        self._sensor_watchers.clear()

    @Slot()
    def _remember_current_train(self) -> None:
        if self._cab.scope == CommandScope.TRAIN.name:
            self._mark_active_train(self._cab.tmccId)

    def _train_command(self, command) -> None:
        if not self._closed and getattr(command, "scope", None) == CommandScope.TRAIN:
            self.trainCommandReceived.emit(int(getattr(command, "address", 0) or 0))

    @Slot(int)
    def _mark_active_train(self, address: int) -> None:
        if self._closed:
            return
        state = ComponentStateStore.get_state(CommandScope.TRAIN, address, create=False)
        if state is None or state.is_deleted or is_pseudo_train(state):
            return
        self._dismissed_trains.pop(address, None)
        self._train_operating_state[address] = self._operating_signature(state)
        if address in self._active_train_ids:
            self._active_train_ids.remove(address)
        self._active_train_ids.insert(0, address)
        self.selectionChanged.emit()

    @Slot(object)
    def applyTrainStateChanges(self, changes: frozenset[StateChange]) -> None:
        if self._closed:
            return
        visible_ids = self._display_train_ids()
        refresh = visible_ids != self._active_train_ids
        self._active_train_ids = visible_ids
        for change in changes:
            if change.scope != CommandScope.TRAIN:
                continue
            address = change.address
            state = ComponentStateStore.get_state(CommandScope.TRAIN, address, create=False)
            if state is None or state.is_deleted or is_pseudo_train(state):
                if address in self._active_train_ids:
                    self._active_train_ids.remove(address)
                    refresh = True
                self._train_operating_state.pop(address, None)
                self._dismissed_trains.pop(address, None)
                continue
            signature = self._operating_signature(state)
            previous = self._train_operating_state.get(address)
            self._train_operating_state[address] = signature
            moving = bool(getattr(state, "speed", 0) or getattr(state, "target_speed", 0))
            if (previous is not None and signature != previous or previous is None and moving) and (
                self._dismissed_trains.get(address) != signature
            ):
                self._mark_active_train(address)
            elif address in self._active_train_ids:
                refresh = True
        if refresh:
            self.selectionChanged.emit()

    @Slot(int)
    def dismissTrain(self, address: int) -> None:
        if address not in self._active_train_ids:
            return
        self._active_train_ids.remove(address)
        state = ComponentStateStore.get_state(CommandScope.TRAIN, address, create=False)
        if state is not None:
            self._dismissed_trains[address] = self._operating_signature(state)
        self.selectionChanged.emit()

    @Slot(int, result=bool)
    def selectTrain(self, address: int) -> bool:
        state = ComponentStateStore.get_state(CommandScope.TRAIN, address, create=False)
        if state is None or state.is_deleted:
            return False
        return self._cab.selectAddress(CommandScope.TRAIN.name, address)

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

    def _watch_engine(self, tmcc_id: int) -> None:
        """Attach live state observation only while an engine is in the working set."""
        if tmcc_id in self._watchers:
            return
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        if state is None:
            return
        self._operating_state[tmcc_id] = self._operating_signature(state)
        self._watchers[tmcc_id] = StateWatcher(state, lambda s=state: self._engine_state_changed(s))

    def _prune_watchers(self) -> None:
        working_ids = set(self._selected_ids + self._active_ids)
        for tmcc_id in tuple(self._watchers):
            if tmcc_id not in working_ids:
                self._watchers.pop(tmcc_id).shutdown()
                self._operating_state.pop(tmcc_id, None)

    def _install_sensor_watchers(self) -> None:
        for state in ComponentStateStore.get().get_all(CommandScope.IRDA):
            sensor_id = int(state.tmcc_id)
            if sensor_id not in self._sensor_watchers:
                self._sensor_watchers[sensor_id] = StateWatcher(state, lambda s=state: self._sensor_track_changed(s))

    def _touch_active(self, tmcc_id: int) -> None:
        """Move a physical locomotive to the front of the activity-only group."""
        key = self._physical_key(tmcc_id)
        self._active_ids = [candidate for candidate in self._active_ids if self._physical_key(candidate) != key]
        self._active_ids.insert(0, tmcc_id)

    def _mark_active(self, tmcc_id: int) -> None:
        if tmcc_id <= 0:
            return
        if ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False) is None:
            return
        if (
            self._cab.scope == "ENGINE"
            and self._same_physical_engine(self._cab.tmccId, tmcc_id)
            and self._is_selected(tmcc_id)
        ):
            self._operated_car_ids.add(tmcc_id)
        self._dismissed_activity.pop(tmcc_id, None)
        self._touch_active(tmcc_id)
        self._watch_engine(tmcc_id)
        self.selectionChanged.emit()

    def _engine_command(self, command) -> None:
        """Treat received engine command traffic as activity even if state is unchanged."""
        if getattr(command, "scope", None) != CommandScope.ENGINE:
            return
        tmcc_id = int(getattr(command, "address", 0) or 0)
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
                self._touch_active(tmcc_id)
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
    def _row(
        cls,
        tmcc_id: int,
        current_id: int,
        selected: bool,
        active: bool,
        scope: CommandScope = CommandScope.ENGINE,
        train_id: int = 0,
    ) -> dict:
        state = ComponentStateStore.get_state(scope, tmcc_id, create=False)
        if state is None:
            return {
                "scope": scope.name,
                "kind": target_kind(state, scope),
                "trainId": train_id,
                "tmccId": tmcc_id,
                "roadName": "",
                "roadNumber": "",
                "direction": "-",
                "smoke": "-",
                "speed": 0,
                "momentum": "-",
                "brake": "-",
                "current": tmcc_id == current_id,
                "selected": selected,
                "active": active,
            }
        momentum = str(getattr(getattr(state, "momentum", None), "name", getattr(state, "momentum", "-")) or "-")
        brake = str(getattr(getattr(state, "train_brake", None), "name", getattr(state, "train_brake", "-")) or "-")
        return {
            "scope": scope.name,
            "kind": target_kind(state, scope),
            "trainId": train_id,
            "tmccId": tmcc_id,
            "roadName": str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip(),
            "roadNumber": format_road_number(getattr(state, "road_number", None)),
            "direction": cls._direction(state),
            "smoke": cls._smoke(state),
            "speed": int(getattr(state, "speed", 0) or 0),
            "momentum": momentum,
            "brake": brake,
            "current": tmcc_id == current_id,
            "selected": selected,
            "active": active,
        }

    def _working_ids(self) -> list[int]:
        selected = self._dedupe_physical(self._selected_ids)
        selected_keys = {self._physical_key(tmcc_id) for tmcc_id in selected}
        active_only = [tmcc_id for tmcc_id in self._active_ids if self._physical_key(tmcc_id) not in selected_keys]
        return selected + self._dedupe_physical(active_only)

    def _containing_active_train(self, address: int) -> int:
        state = ComponentStateStore.get_state(CommandScope.ENGINE, address, create=False)
        if state is None or getattr(state, "is_deleted", False):
            return 0
        physical_key = self._physical_key(address)
        for train_id in self._display_train_ids():
            train = ComponentStateStore.get_state(CommandScope.TRAIN, train_id, create=False)
            if train is None or train.is_deleted:
                continue
            if getattr(state, "train_tmcc_id", None) == train_id or any(
                self._physical_key(component.tmcc_id) == physical_key for component in train.consist_components or ()
            ):
                return train_id
        return 0

    @Property(int, notify=selectionChanged)
    def currentTrainId(self) -> int:
        return self._containing_active_train(self._cab.tmccId) if self._cab.scope == "ENGINE" else 0

    def _is_train_link_car(self, address: int) -> bool:
        physical_key = self._physical_key(address)
        return any(
            component.is_train_link and self._physical_key(component.tmcc_id) == physical_key
            for train in ComponentStateStore.get().get_all(CommandScope.TRAIN)
            if not train.is_deleted
            for component in train.consist_components or ()
        )

    def _car_tile_eligible(self, address: int) -> bool:
        return not self._is_train_link_car(address) or (
            self._is_selected(address)
            and any(self._same_physical_engine(address, candidate) for candidate in self._operated_car_ids)
        )

    def _display_ids(self) -> list[int]:
        display_ids = self._working_ids()
        current_id = self._cab.tmccId if self._cab.scope == "ENGINE" else 0
        current_key = self._physical_key(current_id) if current_id else None
        selected_member = current_id if self.currentTrainId else 0
        display_ids = [address for address in display_ids if self._physical_key(address) != current_key]
        if selected_member and self._car_tile_eligible(selected_member):
            display_ids.insert(0, selected_member)
        return [
            address
            for address in display_ids
            if self._car_tile_eligible(address)
            and (
                address == selected_member
                or not self._containing_active_train(address)
                or self._is_train_link_car(address)
            )
        ]

    def _display_train_ids(self) -> list[int]:
        return [
            address
            for address in self._active_train_ids
            if not is_pseudo_train(ComponentStateStore.get_state(CommandScope.TRAIN, address, create=False))
        ]

    def _is_selected(self, tmcc_id: int) -> bool:
        return any(self._same_physical_engine(tmcc_id, candidate) for candidate in self._selected_ids)

    def _is_active(self, tmcc_id: int) -> bool:
        return any(self._same_physical_engine(tmcc_id, candidate) for candidate in self._active_ids)

    @Property(list, notify=selectionChanged)
    def selectedEngines(self) -> list[dict]:
        current_id = self._cab.tmccId if self._cab.scope == CommandScope.ENGINE.name else -1
        return [
            dict(
                self._row(
                    tmcc_id,
                    current_id,
                    self._is_selected(tmcc_id),
                    self._is_active(tmcc_id),
                    train_id=self._containing_active_train(tmcc_id),
                ),
                trainLinked=self._is_train_link_car(tmcc_id),
            )
            for tmcc_id in self._display_ids()
        ] + [self._row(address, -1, False, True, CommandScope.TRAIN) for address in self._display_train_ids()]

    @Property(int, notify=selectionChanged)
    def count(self) -> int:
        return len(self._display_ids()) + len(self._display_train_ids())

    @Slot(int)
    def selectEngine(self, tmcc_id: int) -> None:
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        if state is None:
            return
        if tmcc_id in self._selected_ids:
            self._selected_ids.remove(tmcc_id)
        self._selected_ids.insert(0, tmcc_id)
        self._watch_engine(tmcc_id)
        if self._cab.scope != CommandScope.ENGINE.name or self._cab.tmccId != tmcc_id:
            self._cab._switch_target(CommandScope.ENGINE, tmcc_id)
        else:
            self.selectionChanged.emit()

    @Slot(int)
    def dismissEngine(self, tmcc_id: int) -> None:
        display_ids = self._display_ids()
        if tmcc_id not in display_ids:
            return
        key = self._physical_key(tmcc_id)
        aliases = [
            candidate for candidate in self._selected_ids + self._active_ids if self._physical_key(candidate) == key
        ]
        self._selected_ids = [candidate for candidate in self._selected_ids if self._physical_key(candidate) != key]
        self._active_ids = [candidate for candidate in self._active_ids if self._physical_key(candidate) != key]
        self._operated_car_ids = {
            candidate for candidate in self._operated_car_ids if self._physical_key(candidate) != key
        }
        for candidate in aliases:
            state = ComponentStateStore.get_state(CommandScope.ENGINE, candidate, create=False)
            if state is not None:
                self._dismissed_activity[candidate] = self._operating_signature(state)
        self._prune_watchers()
        self.selectionChanged.emit()

    @Slot()
    def pruneDeleted(self) -> None:
        self.applyTrainStateChanges(
            frozenset(StateChange(CommandScope.TRAIN, address) for address in self._active_train_ids)
        )
        remaining = {
            tmcc_id
            for tmcc_id in self._selected_ids + self._active_ids
            if ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False) is not None
        }
        self._selected_ids = [tmcc_id for tmcc_id in self._selected_ids if tmcc_id in remaining]
        self._active_ids = [tmcc_id for tmcc_id in self._active_ids if tmcc_id in remaining]
        self._prune_watchers()
        self.selectionChanged.emit()

    @Slot(int)
    def selectRelative(self, delta: int) -> None:
        if not delta or self._cab.scope != CommandScope.ENGINE.name:
            return
        ids = self._working_ids()
        if not ids:
            return

        current_id = self._cab.tmccId
        current_key = self._physical_key(current_id)
        index = next((i for i, tmcc_id in enumerate(ids) if self._physical_key(tmcc_id) == current_key), None)
        if index is None:
            # Keep a restored cab target available for the reverse swipe.
            self._selected_ids.insert(0, current_id)
            self._watch_engine(current_id)
            ids.insert(0, current_id)
            index = 0
        if len(ids) > 1:
            self._cab.selectAddress(CommandScope.ENGINE.name, ids[(index + delta) % len(ids)])
