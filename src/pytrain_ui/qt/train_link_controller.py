"""Train Link membership and the selected car's independent control target."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Property, Signal, Slot

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.state_changes import StateChange
from pytrain.protocol.constants import CommandScope, EngineType

from .presentation import format_road_number


log = logging.getLogger(__name__)


class TrainLinkController(QObject):
    """Observe the active train and its cars through the shared state bridge."""

    changed = Signal()
    selectionInvalidated = Signal(int)
    trainUnavailable = Signal(int)

    def __init__(self, cab, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cab = cab
        self._rows: list[dict] = []
        self._member_ids: set[int] = set()
        self._closed = False
        self._selected_cab = None
        self._retired_cabs: list[QObject] = []
        self._unavailable_train_id = 0
        self._train_id = cab.tmccId
        cab.stateChanged.connect(self.refresh)
        self.refresh()

    @Property(QObject, notify=changed)
    def selectedCab(self):
        return self._selected_cab

    @Property(int, notify=changed)
    def selectedId(self) -> int:
        return self._selected_cab.tmccId if self._selected_cab is not None else 0

    @Slot(int, result=bool)
    def select(self, address: int) -> bool:
        if self._closed or address not in {row["tmccId"] for row in self._rows}:
            return False
        if self.selectedId == address:
            return True
        from .cab_controller import CabController

        self.clearSelection()
        self._selected_cab = CabController(CommandScope.ENGINE, address, self, remember_initial=False)
        self.changed.emit()
        return True

    @Slot()
    def clearSelection(self) -> None:
        if self._selected_cab is not None:
            selected, self._selected_cab = self._selected_cab, None
            self._close_car(selected)
            self.changed.emit()

    def _close_car(self, selected) -> None:
        try:
            selected.close()
        except Exception:
            self._retired_cabs.append(selected)
            log.warning("Unable to close Train Link car controls; retaining them for retry", exc_info=True)
        else:
            selected.deleteLater()

    @Property(list, notify=changed)
    def rows(self) -> list[dict]:
        return [dict(row) for row in self._rows]

    @Slot()
    def refresh(self) -> None:
        if self._closed:
            return
        if self._cab.scope != CommandScope.TRAIN.name or self._train_id != self._cab.tmccId:
            self.clearSelection()
        self._train_id = self._cab.tmccId
        rows = []
        self._member_ids.clear()
        if self._cab.scope == CommandScope.TRAIN.name:
            train = ComponentStateStore.get_state(CommandScope.TRAIN, self._cab.tmccId, create=False)
            if train is None or train.is_deleted:
                if self._cab.tmccId and self._unavailable_train_id != self._cab.tmccId:
                    self._unavailable_train_id = self._cab.tmccId
                    self.trainUnavailable.emit(self._cab.tmccId)
            else:
                self._unavailable_train_id = 0
                for component in train.consist_components or ():
                    address = component.tmcc_id
                    if not component.is_train_link or address in self._member_ids:
                        continue
                    self._member_ids.add(address)
                    car = ComponentStateStore.get_state(CommandScope.ENGINE, address, create=False)
                    if car is None or car.is_deleted:
                        continue
                    rows.append(
                        {
                            "tmccId": address,
                            "roadName": str(car.road_name or car.name or "Train-linked Car").strip(),
                            "roadNumber": format_road_number(car.road_number),
                            "engineType": (
                                "Freight Sounds"
                                if getattr(car, "engine_type", None) == EngineType.FREIGHT_SOUNDS.value
                                else str(getattr(car, "engine_type_label", "NA") or "NA")
                            ),
                        }
                    )
        if self.selectedId and self.selectedId not in {row["tmccId"] for row in rows}:
            address = self.selectedId
            self.clearSelection()
            self.selectionInvalidated.emit(address)
        if rows != self._rows:
            self._rows = rows
            self.changed.emit()

    @Slot(object)
    def applyStateChanges(self, changes: frozenset[StateChange]) -> None:
        if self._closed or self._cab.scope != CommandScope.TRAIN.name:
            return
        if any(
            change.scope == CommandScope.TRAIN
            and change.address == self._cab.tmccId
            or change.scope == CommandScope.ENGINE
            and change.address in self._member_ids
            for change in changes
        ):
            self.refresh()

    def close(self) -> None:
        # The existing cab owns its state subscription; this model creates no watchers.
        self._closed = True
        pending, self._retired_cabs = self._retired_cabs, []
        self.clearSelection()
        for selected in pending:
            self._close_car(selected)
