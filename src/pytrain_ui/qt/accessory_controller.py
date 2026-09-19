"""Unified accessory catalog model for the Qt UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.accessory_state import AccessoryState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.irda_state import IrdaState
from pytrain.gui.accessories.configured_accessory import ConfiguredAccessory, ConfiguredAccessorySet
from pytrain.gui.accessories.accessory_registry import PortBehavior
from pytrain.gui.controller.lcs_id_map import occupants, occupants_of
from pytrain.pdi.asc2_req import Asc2Req
from pytrain.pdi.bpc2_req import Bpc2Req
from pytrain.pdi.constants import Asc2Action, Bpc2Action, PdiCommand
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum
from pytrain.utils.path_utils import find_file

from pytrain_ui.accessory_contracts import (
    AccessoryOperationViewState,
    AccessoryOperatingViewState,
    AccessoryPowerState,
    AnimationPolicy,
    animation_policy,
)


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
            "lcsTypes": sorted({label.split(" ", 1)[0] for label in self.lcs_labels}),
            "availableViews": [view.value for view in self.available_views],
            "preferredView": self.preferred_view.value,
            "userDefined": self.user_defined,
            "stateSummary": AccessoryCatalogController._state_summary(self),
            "quickActions": AccessoryCatalogController._quick_actions(self),
            "componentRows": AccessoryCatalogController._component_rows(self),
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

    @staticmethod
    def _state_summary(descriptor: AccessoryDescriptor) -> str:
        summaries: list[str] = []
        for tmcc_id in descriptor.tmcc_ids:
            state = AccessoryCatalogController._state(tmcc_id)
            if state is None or not state.is_known:
                continue
            value = str(state.payload or "").strip()
            if value and value not in summaries:
                summaries.append(value)
        return " · ".join(summaries)

    @staticmethod
    def _component_rows(descriptor: AccessoryDescriptor) -> list[dict]:
        configured = descriptor.configured_accessory
        if configured is None:
            return []
        rows: list[dict] = []
        registry = configured.registry
        spec = registry.get_spec(configured.accessory_type)
        power_ids = {
            configured.tmcc_id_for(op.key)
            for op in configured.operation_assets
            if op.behavior == PortBehavior.LATCH and op.key.strip().lower() == "power"
        }
        power_on = all(
            (state := AccessoryCatalogController._state(tmcc_id)) is not None and state.is_aux_on
            for tmcc_id in power_ids
        )
        for operation in configured.operation_assets:
            tmcc_id = configured.tmcc_id_for(operation.key)
            state = AccessoryCatalogController._state(tmcc_id)
            label = registry.get_operation_label(spec, operation.key, variant=configured.definition.variant)
            requires_power = operation.behavior != PortBehavior.LATCH and bool(power_ids) and tmcc_id not in power_ids
            enabled = not requires_power or power_on
            if operation.behavior == PortBehavior.LATCH:
                actions = [
                    {"key": "ON", "label": "ON", "selected": bool(state and state.is_aux_on), "enabled": enabled},
                    {"key": "OFF", "label": "OFF", "selected": bool(state and state.is_aux_off), "enabled": enabled},
                ]
            else:
                actions = [
                    {
                        "key": "MOMENTARY",
                        "label": "MOMENTARY",
                        "selected": False,
                        "enabled": enabled,
                    }
                ]
            rows.append(
                {
                    "tmccId": tmcc_id,
                    "label": f"{configured.label} {label}",
                    "operation": operation.key,
                    "behavior": operation.behavior.value,
                    "enabled": enabled,
                    "quickActions": actions,
                }
            )
        return rows

    @staticmethod
    def _quick_actions(descriptor: AccessoryDescriptor) -> list[dict]:
        if descriptor.configured_accessory is not None:
            return []
        state = AccessoryCatalogController._state(descriptor.primary_tmcc_id)
        if state is None:
            return []
        lcs_types = {label.split(" ", 1)[0] for label in descriptor.lcs_labels}
        if "BPC2" in lcs_types:
            return [
                {"key": "ON", "label": "ON", "selected": state.is_aux_on},
                {"key": "OFF", "label": "OFF", "selected": state.is_aux_off},
            ]
        if "ASC2" in lcs_types:
            momentary = not state.is_aux_on and not state.is_aux_off
            return [
                {"key": "ON", "label": "ON", "selected": state.is_aux_on},
                {"key": "OFF", "label": "OFF", "selected": state.is_aux_off},
                {"key": "MOMENTARY", "label": "MOMENTARY", "selected": momentary},
            ]
        return []

    @staticmethod
    def _sensor_summary(state: IrdaState) -> str:
        parts: list[str] = []
        if state.sequence_str and state.sequence_str != "NA":
            parts.append(state.sequence_str.replace("_", " "))
        if state.is_train:
            parts.append(f"Train {state.last_train_id}")
        elif state.is_engine:
            parts.append(f"Engine {state.last_engine_id}")
        if state.last_direction.name != "UNKNOWN":
            parts.append(state.last_direction.name)
        return " · ".join(parts) or "Waiting for sensor activity"

    @staticmethod
    def _image_source(filename: str | None) -> str:
        if not filename:
            return ""
        path = find_file(filename)
        return QUrl.fromLocalFile(str(path)).toString() if path else ""

    @staticmethod
    def _power_state(state: AccessoryState | None) -> tuple[AccessoryPowerState, bool]:
        if state is None or not state.is_known:
            return AccessoryPowerState.UNKNOWN, False
        if state.is_aux_on:
            value = AccessoryPowerState.ON
        elif state.is_aux_off:
            value = AccessoryPowerState.OFF
        else:
            value = AccessoryPowerState.UNKNOWN
        # LCS proxy state is authoritative once PDI control/config traffic has
        # populated it. Generic TMCC state remains useful but is command-inferred.
        authoritative = bool(getattr(state, "_pdi_source", False))
        return value, authoritative

    @classmethod
    def _configured_operating_state(
        cls,
        key: str,
        configured: ConfiguredAccessory,
    ) -> AccessoryOperatingViewState:
        registry = configured.registry
        spec = registry.get_spec(configured.accessory_type)
        operations: list[AccessoryOperationViewState] = []

        for assets in configured.operation_assets:
            tmcc_id = configured.tmcc_id_for(assets.key)
            state = cls._state(tmcc_id)
            power, authoritative = cls._power_state(state)
            is_on = power == AccessoryPowerState.ON
            label = registry.get_operation_label_for_state(
                spec,
                assets.key,
                variant=configured.definition.variant,
                is_on=is_on if power != AccessoryPowerState.UNKNOWN else None,
            )
            policy = animation_policy(assets.behavior)
            operations.append(
                AccessoryOperationViewState(
                    key=assets.key,
                    label=label,
                    tmcc_id=tmcc_id,
                    behavior=assets.behavior,
                    state=power,
                    state_authoritative=authoritative,
                    image=cls._image_source(assets.image),
                    off_image=cls._image_source(assets.off_image),
                    on_image=cls._image_source(assets.on_image),
                    animation_policy=policy,
                    animation_running=is_on and policy in {AnimationPolicy.STATE, AnimationPolicy.MOMENTARY},
                    width=assets.width,
                    height=assets.height,
                )
            )

        power_operation = next((op for op in operations if op.key.strip().lower() == "power"), None)
        if power_operation is None and len(operations) == 1:
            power_operation = operations[0]
        power = power_operation.state if power_operation is not None else AccessoryPowerState.UNKNOWN
        authoritative = power_operation.state_authoritative if power_operation is not None else False
        return AccessoryOperatingViewState(
            key=key,
            title=configured.label,
            artwork=cls._image_source(configured.image_path),
            artwork_aspect_ratio=3.0,
            power_state=power,
            power_state_authoritative=authoritative,
            operations=tuple(operations),
        )

    @staticmethod
    def _operation_row(operation: AccessoryOperationViewState) -> dict:
        return {
            "key": operation.key,
            "label": operation.label,
            "tmccId": operation.tmcc_id,
            "behavior": operation.behavior.value,
            "state": operation.state.value,
            "stateAuthoritative": operation.state_authoritative,
            "imageSource": operation.image,
            "offImageSource": operation.off_image,
            "onImageSource": operation.on_image,
            "animationPolicy": operation.animation_policy.value,
            "animationRunning": operation.animation_running,
            "width": operation.width or 0,
            "height": operation.height or 0,
        }

    @Slot()
    def halt(self) -> None:
        CommandReq.build(TMCC1HaltCommandEnum.HALT).send()

    @Slot(str, int)
    def quickAction(self, action: str, tmcc_id: int) -> None:
        """Send a direct PDI action to an ASC2/BPC2-backed accessory."""

        state = self._state(tmcc_id)
        if state is None:
            return
        value = 0 if action == "OFF" else 1
        if state.is_bpc2:
            Bpc2Req(tmcc_id, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, state=value).send()
        elif state.is_asc2:
            Asc2Req(tmcc_id, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=value).send()

    @Slot(str, result="QVariantMap")
    def operatingView(self, key: str) -> dict:
        """Return the common operating-view contract for a catalog accessory."""

        descriptor = self._descriptors.get(key)
        if descriptor is None:
            return {}
        if descriptor.configured_accessory is not None:
            view = self._configured_operating_state(key, descriptor.configured_accessory)
            return {
                "key": view.key,
                "title": view.title,
                "artworkSource": view.artwork,
                "artworkAspectRatio": view.artwork_aspect_ratio,
                "powerState": view.power_state.value,
                "powerStateAuthoritative": view.power_state_authoritative,
                "operations": [self._operation_row(operation) for operation in view.operations],
            }

        state = self._state(descriptor.primary_tmcc_id)
        power, authoritative = self._power_state(state)
        return {
            "key": key,
            "title": descriptor.name,
            "artworkSource": "",
            "artworkAspectRatio": 3.0,
            "powerState": power.value,
            "powerStateAuthoritative": authoritative,
            "operations": [],
        }

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

        # Sensor Tracks are stored in IRDA scope rather than ACC.
        for occupant in occupants():
            if occupant.device.label != "IR Sensor Track":
                continue
            state = ComponentStateStore.get_state(CommandScope.IRDA, occupant.base_id, create=False)
            if not isinstance(state, IrdaState):
                continue
            name, road_number = self._identity(state)
            descriptors.append(
                AccessoryDescriptor(
                    key=f"irda:{occupant.base_id}",
                    tmcc_ids=(occupant.base_id,),
                    primary_tmcc_id=occupant.base_id,
                    name=name or f"Sensor Track {occupant.base_id}",
                    road_number=road_number,
                    configured_accessory=None,
                    lcs_labels=(f"Sensor Track {occupant.base_id}",),
                    available_views=(AccessoryViewKind.LCS,),
                    preferred_view=AccessoryViewKind.LCS,
                    user_defined=True,
                )
            )

        descriptors.sort(key=lambda item: (item.name.lower(), item.primary_tmcc_id))
        self._descriptors = {descriptor.key: descriptor for descriptor in descriptors}
        self._rows = [descriptor.as_row() for descriptor in descriptors]
        for row in self._rows:
            if row["key"].startswith("irda:"):
                state = ComponentStateStore.get_state(CommandScope.IRDA, row["primaryTmccId"], create=False)
                row["lcsTypes"] = ["SENSOR_TRACK"]
                row["stateSummary"] = self._sensor_summary(state) if isinstance(state, IrdaState) else ""
        self.changed.emit()

    @Slot(str, result="QVariantMap")
    def descriptor(self, key: str) -> dict:
        descriptor = self._descriptors.get(key)
        return descriptor.as_row() if descriptor is not None else {}

    @Property(list, notify=changed)
    def rows(self) -> list[dict]:
        return self._rows    @Slot(str, int)
    def quickAction(self, action: str, tmcc_id: int) -> None:
        """Send a direct PDI action to an ASC2/BPC2-backed accessory."""

        state = self._state(tmcc_id)
        if state is None:
            return
        value = 0 if action == "OFF" else 1
        if state.is_bpc2:
            Bpc2Req(tmcc_id, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, state=value).send()
        elif state.is_asc2:
            Asc2Req(tmcc_id, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=value).send()


