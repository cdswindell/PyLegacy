"""Unified accessory catalog model for the Qt UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.accessory_state import AccessoryState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.gui.accessories.configured_accessory import ConfiguredAccessory, ConfiguredAccessorySet
from pytrain.gui.controller.lcs_id_map import occupants_of
from pytrain.protocol.constants import CommandScope


class AccessoryViewKind(str, Enum):
    """The operating views that can represent one accessory."""

    CONFIGURED = "CONFIGURED"
    LCS = "LCS"
    GENERIC = "ACC"


@dataclass(frozen=True, slots=True)
class AccessoryDescriptor:
    """Toolkit-neutral identity for one row in the unified accessory catalog."""

    key: str
    tmcc_ids: tuple[int, ...]
    primary_tmcc_id: int
    name: str
    road_number: str
    configured_accessory: ConfiguredAccessory | None
    lcs_labels: tuple[str, ...]
    available_views: tuple[AccessoryViewKind, ...]
    preferred_view: AccessoryViewKind
    user_defined: bool

    def as_row(self) -> dict:
        return {
            "key": self.key,
            "tmccIds": list(self.tmcc_ids),
            "primaryTmccId": self.primary_tmcc_id,
            "roadName": self.name,
            "roadNumber": self.road_number,
            "configured": self.configured_accessory is not None,
            "lcsAssociations": " · ".join(self.lcs_labels),
            "availableViews": [view.value for view in self.available_views],
            "preferredView": self.preferred_view.value,
            "userDefined": self.user_defined,
        }


class AccessoryCatalogController(QObject):
    """Merge configured, LCS-backed, and Base accessories into one catalog."""

    changed = Signal()
    commandReceived = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []
        self._descriptors: dict[str, AccessoryDescriptor] = {}
        self._dispatcher = CommandDispatcher.get() if CommandDispatcher.is_built() else None
        self.commandReceived.connect(self.reload)
        if self._dispatcher is not None:
            self._dispatcher.subscribe(self._accessory_command, CommandScope.ACC)
        self.reload()

    def close(self) -> None:
        if self._dispatcher is not None:
            self._dispatcher.unsubscribe(self._accessory_command, CommandScope.ACC)
            self._dispatcher = None

    def _accessory_command(self, _command) -> None:
        # Queue the reload onto Qt's thread. Command traffic may introduce a new
        # accessory state, and ComponentStateStore is another dispatcher subscriber.
        self.commandReceived.emit()

    @staticmethod
    def _identity(state: AccessoryState | None) -> tuple[str, str]:
        if state is None:
            return "", ""
        name = str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip()
        number = str(getattr(state, "road_number", "") or "").strip()
        return name, number

    @staticmethod
    def _lcs_labels(tmcc_ids: tuple[int, ...]) -> tuple[str, ...]:
        labels: list[str] = []
        seen: set[tuple[str, int, int | None]] = set()
        for tmcc_id in tmcc_ids:
            for occupant in occupants_of(tmcc_id, scope=CommandScope.ACC):
                identity = (occupant.device.key, occupant.base_id, occupant.port_index)
                if identity in seen:
                    continue
                seen.add(identity)
                label = f"{occupant.device.label} {occupant.base_id}"
                if occupant.port_index is not None:
                    label += f" Port {occupant.port_index}"
                labels.append(label)
        return tuple(labels)

    @staticmethod
    def _state(tmcc_id: int) -> AccessoryState | None:
        state = ComponentStateStore.get_state(CommandScope.ACC, tmcc_id, create=False)
        return state if isinstance(state, AccessoryState) else None

    @classmethod
    def _views(
        cls,
        configured: ConfiguredAccessory | None,
        lcs_labels: tuple[str, ...],
    ) -> tuple[AccessoryViewKind, ...]:
        views: list[AccessoryViewKind] = []
        if configured is not None:
            views.append(AccessoryViewKind.CONFIGURED)
        if lcs_labels:
            views.append(AccessoryViewKind.LCS)
        views.append(AccessoryViewKind.GENERIC)
        return tuple(views)

    @classmethod
    def _configured_descriptor(cls, configured: ConfiguredAccessory) -> AccessoryDescriptor | None:
        tmcc_ids = tuple(configured.tmcc_ids)
        if not tmcc_ids:
            return None
        primary = int(configured.tmcc_id if configured.tmcc_id is not None else tmcc_ids[0])
        state = cls._state(primary)
        _base_name, road_number = cls._identity(state)
        lcs_labels = cls._lcs_labels(tmcc_ids)
        views = cls._views(configured, lcs_labels)
        return AccessoryDescriptor(
            key=f"configured:{configured.instance_id or configured.label}",
            tmcc_ids=tmcc_ids,
            primary_tmcc_id=primary,
            name=configured.label,
            road_number=road_number,
            configured_accessory=configured,
            lcs_labels=lcs_labels,
            available_views=views,
            preferred_view=AccessoryViewKind.CONFIGURED,
            user_defined=True,
        )

    @classmethod
    def _base_descriptor(cls, state: AccessoryState) -> AccessoryDescriptor:
        tmcc_id = int(state.tmcc_id)
        name, road_number = cls._identity(state)
        lcs_labels = cls._lcs_labels((tmcc_id,))
        views = cls._views(None, lcs_labels)
        return AccessoryDescriptor(
            key=f"acc:{tmcc_id}",
            tmcc_ids=(tmcc_id,),
            primary_tmcc_id=tmcc_id,
            name=name or f"Accessory {tmcc_id}",
            road_number=road_number,
            configured_accessory=None,
            lcs_labels=lcs_labels,
            available_views=views,
            preferred_view=AccessoryViewKind.LCS if lcs_labels else AccessoryViewKind.GENERIC,
            user_defined=bool(state.is_user_defined),
        )

    @Slot()
    def reload(self) -> None:
        configured_set = ConfiguredAccessorySet.from_file()
        descriptors: list[AccessoryDescriptor] = []
        covered_ids: set[int] = set()

        for configured in configured_set.configured_all():
            descriptor = self._configured_descriptor(configured)
            if descriptor is None:
                continue
            descriptors.append(descriptor)
            covered_ids.update(descriptor.tmcc_ids)

        states = sorted(ComponentStateStore.get().get_all(CommandScope.ACC), key=lambda state: state.tmcc_id)
        for state in states:
            if not isinstance(state, AccessoryState) or state.is_deleted:
                continue
            if int(state.tmcc_id) in covered_ids:
                continue
            descriptors.append(self._base_descriptor(state))

        descriptors.sort(key=lambda item: (item.name.lower(), item.primary_tmcc_id))
        self._descriptors = {descriptor.key: descriptor for descriptor in descriptors}
        self._rows = [descriptor.as_row() for descriptor in descriptors]
        self.changed.emit()

    @Slot(str, result="QVariantMap")
    def descriptor(self, key: str) -> dict:
        descriptor = self._descriptors.get(key)
        return descriptor.as_row() if descriptor is not None else {}

    @Property(list, notify=changed)
    def rows(self) -> list[dict]:
        return self._rows
