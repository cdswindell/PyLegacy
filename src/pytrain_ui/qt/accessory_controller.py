"""Unified accessory catalog model for the Qt UI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from time import monotonic

from PySide6.QtCore import Property, QCoreApplication, QObject, QTimer, QUrl, Signal, Slot

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.accessory_state import AccessoryState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.irda_state import IrdaState
from pytrain.gui.accessories.accessory_registry import OperationAssets
from pytrain.gui.accessories.configured_accessory import ConfiguredAccessory, ConfiguredAccessorySet
from pytrain.gui.controller.engine_gui_conf import SENSOR_TRACK_OPTS
from pytrain.gui.controller.lcs_id_map import occupants, occupants_of
from pytrain.pdi.amc2_req import Amc2Req
from pytrain.pdi.asc2_req import Asc2Req
from pytrain.pdi.bpc2_req import Bpc2Req
from pytrain.pdi.constants import Amc2Action, Asc2Action, Bpc2Action, IrdaAction, PdiCommand
from pytrain.pdi.irda_req import IrdaReq, IrdaSequence
from pytrain.pdi.pdi_listener import PdiDispatcher
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum, TMCC1HaltCommandEnum
from pytrain.utils.path_utils import find_file

from ..accessory_contracts import (
    AccessoryOperationViewState,
    AccessoryOperatingViewState,
    AccessoryPowerState,
    AnimationPolicy,
    animation_policy,
)
from .presentation import format_road_number


log = logging.getLogger(__name__)

_DEVICE_IMAGES = {
    "ASC2": "LCS-ASC2-6-81639.jpg",
    "BPC2": "LCS-BPC2-6-81640.jpg",
    "AMC2": "LCS-AMC2-6-81641.jpg",
    "SENSOR": "LCS-Sensor-Track-6-81294.jpg",
}


@dataclass(frozen=True, slots=True)
class Amc2OutputIntent:
    level: int
    on: bool
    deadline: float


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
    component_names: tuple[tuple[int, str], ...] = ()

    @property
    def kind(self) -> str:
        if self.configured_accessory is not None:
            return "OPERATING"
        if self.key.startswith("irda:"):
            return "SENSOR"
        return self.lcs_labels[0].split(" ", 1)[0] if self.lcs_labels else "TMCC"

    def as_row(self) -> dict:
        return {
            "key": self.key,
            "tmccIds": list(self.tmcc_ids),
            "primaryTmccId": self.primary_tmcc_id,
            "roadName": self.name,
            "roadNumber": format_road_number(self.road_number),
            "configured": self.configured_accessory is not None,
            "lcsAssociations": " · ".join(self.lcs_labels),
            "componentNames": " · ".join(name for _, name in self.component_names),
            "lcsTypes": sorted({label.split(" ", 1)[0] for label in self.lcs_labels}),
            "availableViews": [view.value for view in self.available_views],
            "preferredView": self.preferred_view.value,
            "userDefined": self.user_defined,
            "stateSummary": AccessoryCatalogController._state_summary(self),
            "quickActions": AccessoryCatalogController._quick_actions(self),
            "kind": self.kind,
            "imageSource": AccessoryCatalogController._image_source(
                self.configured_accessory.image_path if self.configured_accessory else _DEVICE_IMAGES.get(self.kind)
            ),
        }


class AccessoryCatalogController(QObject):
    """Merge configured, LCS-backed, and Base accessories into one catalog."""

    changed = Signal()
    commandReceived = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []
        self._held_asc2: set[int] = set()
        self._amc2_levels: dict[tuple[str, bool, int], int] = {}
        self._amc2_pending: dict[tuple[str, bool, int], Amc2OutputIntent] = {}
        self._amc2_timer = QTimer(self)
        self._amc2_timer.setSingleShot(True)
        self._amc2_timer.setInterval(1500)
        self._amc2_timer.timeout.connect(self.changed.emit)
        self._descriptors: dict[str, AccessoryDescriptor] = {}
        self._dispatcher = CommandDispatcher.get() if CommandDispatcher.is_built() else None
        self._pdi_dispatcher = PdiDispatcher.get() if PdiDispatcher.is_built() else None
        self.commandReceived.connect(self.reload)
        if self._dispatcher is not None:
            self._dispatcher.subscribe(self._accessory_command, CommandScope.ACC)
        if self._pdi_dispatcher is not None:
            # PDI dispatch topics are scope-based (ACC/IRDA), not raw RX
            # command values. Subscribe after ComponentStateStore so the
            # queued Qt refresh reads the newly observed state.
            self._pdi_dispatcher.subscribe(self._pdi_command, CommandScope.ACC)
            self._pdi_dispatcher.subscribe(self._pdi_command, CommandScope.IRDA)
        self.reload()

    def close(self) -> None:
        self._amc2_timer.stop()
        for tmcc_id in tuple(self._held_asc2):
            try:
                self.holdQuickAction(tmcc_id, False)
            except Exception:
                log.exception("Unable to release ASC2 accessory %s on close", tmcc_id)
        if self._dispatcher is not None:
            self._dispatcher.unsubscribe(self._accessory_command, CommandScope.ACC)
            self._dispatcher = None
        if self._pdi_dispatcher is not None:
            self._pdi_dispatcher.unsubscribe(self._pdi_command, CommandScope.ACC)
            self._pdi_dispatcher.unsubscribe(self._pdi_command, CommandScope.IRDA)
            self._pdi_dispatcher = None

    def _accessory_command(self, _command) -> None:
        # Queue the reload onto Qt's thread. Command traffic may introduce a new
        # accessory state, and ComponentStateStore is another dispatcher subscriber.
        self.commandReceived.emit()

    def _pdi_command(self, _command) -> None:
        # LCS control packets are authoritative for ASC2/BPC2/AMC2 and Sensor
        # Track state. Queue a catalog rebuild after the state store processes them.
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
        definition = configured.definition
        registry = configured.registry
        spec = registry.get_spec(definition.type)
        component_names: dict[int, list[str]] = {}
        for operation in spec.operations:
            try:
                tmcc_id = configured.tmcc_id_for(operation.key)
            except (KeyError, ValueError):
                continue
            label = registry.get_operation_label_for_state(spec, operation.key, variant=definition.variant)
            names = component_names.setdefault(tmcc_id, [])
            if label and label not in names:
                names.append(label)

        lcs_labels = cls._lcs_labels(tmcc_ids)
        views = cls._views(configured, lcs_labels)
        return AccessoryDescriptor(
            key=f"configured:{configured.instance_id or configured.label}",
            tmcc_ids=tmcc_ids,
            primary_tmcc_id=primary,
            name=configured.label,
            road_number="",
            configured_accessory=configured,
            lcs_labels=lcs_labels,
            available_views=views,
            preferred_view=AccessoryViewKind.CONFIGURED,
            user_defined=True,
            component_names=tuple((tmcc_id, " / ".join(names)) for tmcc_id, names in component_names.items() if names),
        )

    @classmethod
    def _base_descriptor(
        cls, tmcc_id: int, state: AccessoryState | None, lcs_labels: tuple[str, ...]
    ) -> AccessoryDescriptor:
        name, road_number = cls._identity(state)
        views = cls._views(None, lcs_labels)
        return AccessoryDescriptor(
            key=f"acc:{tmcc_id}" + (f":{lcs_labels[0]}" if lcs_labels else ""),
            tmcc_ids=(tmcc_id,),
            primary_tmcc_id=tmcc_id,
            name=name
            if name and name not in {"Acc", "NA"}
            else (lcs_labels[0] if lcs_labels else f"Accessory {tmcc_id}"),
            road_number=road_number,
            configured_accessory=None,
            lcs_labels=lcs_labels,
            available_views=views,
            preferred_view=AccessoryViewKind.LCS if lcs_labels else AccessoryViewKind.GENERIC,
            user_defined=bool(state and state.is_user_defined),
        )

    @staticmethod
    def _state_summary(descriptor: AccessoryDescriptor) -> str:
        summaries: list[str] = []
        component_names = dict(descriptor.component_names)
        for tmcc_id in descriptor.tmcc_ids:
            state = AccessoryCatalogController._state(tmcc_id)
            if state is None or not state.is_known:
                continue
            label = component_names.get(tmcc_id)
            if label and (state.is_asc2 or state.is_bpc2):
                value = f"{label}: {'ON' if state.is_aux_on else 'OFF'}"
            else:
                value = str(state.payload or "").strip()
                if label and value:
                    value = f"{label}: {value}"
            if value and value not in summaries:
                summaries.append(value)
        return " · ".join(summaries)

    @staticmethod
    def _supports_relay(tmcc_id: int, kind: str) -> bool:
        matches = [
            occupant for occupant in occupants_of(tmcc_id, scope=CommandScope.ACC) if occupant.device.label == kind
        ]
        if matches:
            return any(occupant.mode.key == "acc_8" if occupant.mode else kind == "BPC2" for occupant in matches)
        state = AccessoryCatalogController._state(tmcc_id)
        return bool(
            state
            and (
                (kind == "BPC2" and state.is_bpc2 and state.mode in (2, "NA", None))
                or (kind == "ASC2" and state.is_asc2 and state.mode == 0)
            )
        )

    @classmethod
    def _relay_feedback(cls, tmcc_id: int) -> AccessoryState | None:
        # The ACC state is shared if multiple modules occupy the same address.
        if len(cls._lcs_labels((tmcc_id,))) > 1:
            return None
        return cls._state(tmcc_id)

    @staticmethod
    def _quick_actions(descriptor: AccessoryDescriptor) -> list[dict]:
        if descriptor.kind not in {"BPC2", "ASC2"}:
            return []
        tmcc_id = descriptor.primary_tmcc_id
        if not AccessoryCatalogController._supports_relay(tmcc_id, descriptor.kind):
            return []
        state = AccessoryCatalogController._relay_feedback(tmcc_id)
        actions = [
            {"key": "ON", "label": "On", "selected": bool(state and state.is_aux_on)},
            {"key": "OFF", "label": "Off", "selected": bool(state and state.is_aux_off)},
        ]
        if descriptor.kind == "ASC2":
            actions.append({"key": "HOLD", "label": "Hold", "selected": False})
        return actions

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

    @staticmethod
    def _qt_operations(configured: ConfiguredAccessory) -> list[OperationAssets]:
        operations = configured.operation_assets
        replaced = {key.strip().lower() for operation in operations for key in operation.replaces}
        return [operation for operation in operations if operation.key.strip().lower() not in replaced]

    @classmethod
    def _configured_operating_state(
        cls,
        key: str,
        configured: ConfiguredAccessory,
    ) -> AccessoryOperatingViewState:
        registry = configured.registry
        spec = registry.get_spec(configured.accessory_type)
        operations: list[AccessoryOperationViewState] = []

        for assets in cls._qt_operations(configured):
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
                    analog_input=assets.analog_input,
                    repeat=assets.repeat,
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
        analog = operation.analog_input
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
            "analogInput": {
                "minimum": analog.minimum,
                "maximum": analog.maximum,
                "neutral": analog.neutral,
                "springReturn": analog.spring_return,
                "orientation": analog.orientation.value,
                "repeat": operation.repeat or 0,
            }
            if analog is not None
            else None,
        }

    @Slot()
    def halt(self) -> None:
        CommandReq.build(TMCC1HaltCommandEnum.HALT).send()

    @staticmethod
    def _send_asc2(tmcc_id: int, on: bool) -> None:
        Asc2Req(tmcc_id, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=int(on), time=0).send()

    @Slot(int, str)
    def toggleQuickAction(self, tmcc_id: int, kind: str) -> None:
        state = self._relay_feedback(tmcc_id)
        self.quickAction("OFF" if state and state.is_aux_on else "ON", tmcc_id, kind)

    @Slot(int, bool)
    def holdQuickAction(self, tmcc_id: int, pressed: bool) -> None:
        if pressed:
            if tmcc_id not in self._held_asc2 and self._supports_relay(tmcc_id, "ASC2"):
                self._send_asc2(tmcc_id, True)
                self._held_asc2.add(tmcc_id)
        elif tmcc_id in self._held_asc2:
            self._send_asc2(tmcc_id, False)
            self._held_asc2.remove(tmcc_id)

    @Slot(str, int, str)
    def quickAction(self, action: str, tmcc_id: int, kind: str) -> None:
        if action not in {"ON", "OFF"} or (kind == "ASC2" and tmcc_id in self._held_asc2):
            return
        if not self._supports_relay(tmcc_id, kind):
            return
        if kind == "BPC2":
            Bpc2Req(tmcc_id, PdiCommand.BPC2_SET, Bpc2Action.CONTROL3, state=int(action == "ON")).send()
        elif kind == "ASC2":
            self._send_asc2(tmcc_id, action == "ON")

    @Slot(str, str, int)
    def sendAnalogOperation(self, key: str, operation_key: str, value: int) -> None:
        descriptor = self._descriptors.get(key)
        if descriptor is None or descriptor.configured_accessory is None:
            return

        configured = descriptor.configured_accessory
        operation = next((op for op in self._qt_operations(configured) if op.key == operation_key), None)
        if operation is None or operation.analog_input is None or operation.command is None:
            return
        analog = operation.analog_input
        if not analog.minimum <= value <= analog.maximum or value == analog.neutral:
            return
        if operation.gated_by is not None:
            gate_id = configured.tmcc_id_for(operation.gated_by)
            if self._power_state(self._state(gate_id))[0] != AccessoryPowerState.ON:
                return
        CommandReq.build(operation.command, configured.tmcc_id_for(operation.key), value).send()

    @Slot(str, int, str, int)
    def tmccCommand(self, key: str, tmcc_id: int, name: str, value: int) -> None:
        descriptor = self._descriptors.get(key)
        if descriptor is None or descriptor.kind != "TMCC" or descriptor.primary_tmcc_id != tmcc_id:
            return
        if (name == "NUMERIC" and 0 <= value <= 9) or (name == "RELATIVE_SPEED" and -5 <= value <= 5):
            CommandReq.build(TMCC1AuxCommandEnum[name], tmcc_id, value).send()
        elif name in {
            "BOOST",
            "BRAKE",
            "SET_ADDRESS",
            "AUX1_ON",
            "AUX1_OFF",
            "AUX1_OPT_ONE",
            "AUX2_OPT_ONE",
            "FRONT_COUPLER",
            "REAR_COUPLER",
            "TOGGLE_DIRECTION",
        }:
            CommandReq.build(TMCC1AuxCommandEnum[name], tmcc_id).send()

    @Slot(str, int)
    def setSensorSequence(self, key: str, value: int) -> None:
        descriptor = self._descriptors.get(key)
        if descriptor is not None and descriptor.kind == "SENSOR" and value in {v for _, v in SENSOR_TRACK_OPTS}:
            IrdaReq(
                descriptor.primary_tmcc_id, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=IrdaSequence(value)
            ).send()

    def _amc2_descriptor(self, key: str, motor: bool, output: int) -> AccessoryDescriptor | None:
        descriptor = self._descriptors.get(key)
        if descriptor is not None and descriptor.kind == "AMC2" and 1 <= output <= (2 if motor else 4):
            return descriptor
        return None

    @staticmethod
    def _amc2_motor_power(address: int, output: int, on: bool) -> None:
        CommandReq.build(TMCC1AuxCommandEnum.NUMERIC, address, output).send()
        command = TMCC1AuxCommandEnum.AUX1_OPT_ONE if on else TMCC1AuxCommandEnum.AUX2_OPT_ONE
        CommandReq.build(command, address).send()

    @staticmethod
    def _amc2_lamp_level(address: int, output: int, level: int) -> None:
        Amc2Req(address, PdiCommand.AMC2_SET, Amc2Action.LAMP, lamp=output - 1, level=level).send()
        CommandReq.build(TMCC1AuxCommandEnum.NUMERIC, address, output + 2).send()

    def _amc2_reading(self, key: str, state: AccessoryState | None, motor: bool, output: int) -> dict:
        channel = (key, motor, output)
        if motor:
            reading = state.get_motor(output) if state is not None else None
            level = reading.speed if reading else 0
            on = bool(reading and state.is_motor_on(reading))
        else:
            reading = state.get_lamp(output) if state is not None else None
            level = reading.level if reading else 0
            on = level > 0

        pending = self._amc2_pending.get(channel)
        if pending is not None:
            if on == pending.on and (not on or level == pending.level):
                del self._amc2_pending[channel]
            elif monotonic() < pending.deadline:
                return {"level": pending.level, "on": pending.on}
            else:
                del self._amc2_pending[channel]

        if on:
            self._amc2_levels[channel] = level
        return {"level": level if on else self._amc2_levels.get(channel, level), "on": on}

    def _remember_amc2_output(self, key: str, motor: bool, output: int, level: int, on: bool) -> None:
        channel = (key, motor, output)
        self._amc2_levels[channel] = level
        self._amc2_pending[channel] = Amc2OutputIntent(level, on, monotonic() + 1.5)
        if QCoreApplication.instance() is not None:
            self._amc2_timer.start()
        self.changed.emit()

    @Slot(str, bool, int, bool)
    def setAmc2Power(self, key: str, motor: bool, output: int, on: bool) -> None:
        descriptor = self._amc2_descriptor(key, motor, output)
        if descriptor is None:
            return
        address = descriptor.primary_tmcc_id
        reading = self._amc2_reading(key, self._state(address), motor, output)
        level = reading["level"]
        if not on or level:
            self._send_amc2_level(address, motor, output, level if on else 0)
        self._remember_amc2_output(key, motor, output, level, on and level > 0)

    @Slot(str, bool, int, int)
    def setAmc2Output(self, key: str, motor: bool, output: int, level: int) -> None:
        descriptor = self._amc2_descriptor(key, motor, output)
        if descriptor is None or not 0 <= level <= 100:
            return
        address = descriptor.primary_tmcc_id
        self._send_amc2_level(address, motor, output, level)
        self._remember_amc2_output(key, motor, output, level, level > 0)

    def _send_amc2_level(self, address: int, motor: bool, output: int, level: int) -> None:
        if motor:
            state = self._state(address)
            reading = state.get_motor(output) if state is not None else None
            Amc2Req(
                address,
                PdiCommand.AMC2_SET,
                Amc2Action.MOTOR,
                motor=output - 1,
                speed=level,
                direction=reading.direction if reading else None,
            ).send()
            self._amc2_motor_power(address, output, level > 0)
        else:
            self._amc2_lamp_level(address, output, level)

    @Slot(str, result="QVariantMap")
    def operatingView(self, key: str) -> dict:
        descriptor = self._descriptors.get(key)
        if descriptor is None:
            return {}
        device_name = "Sensor Track" if descriptor.kind == "SENSOR" else descriptor.kind
        title = descriptor.name
        if descriptor.kind in _DEVICE_IMAGES and not title.casefold().startswith(device_name.casefold()):
            title = f"{device_name} {title}"
        panel = {
            "key": key,
            "kind": descriptor.kind,
            "tmccId": descriptor.primary_tmcc_id,
            "title": title,
            "artworkSource": self._image_source(_DEVICE_IMAGES.get(descriptor.kind)),
        }
        if descriptor.configured_accessory is not None:
            view = self._configured_operating_state(key, descriptor.configured_accessory)
            panel.update(
                artworkSource=view.artwork,
                artworkAspectRatio=view.artwork_aspect_ratio,
                powerState=view.power_state.value,
                powerStateAuthoritative=view.power_state_authoritative,
                operations=[self._operation_row(operation) for operation in view.operations],
            )
        elif descriptor.kind == "SENSOR":
            state = ComponentStateStore.get_state(CommandScope.IRDA, descriptor.primary_tmcc_id, create=False)
            panel["sequences"] = [{"label": label, "value": value} for label, value in SENSOR_TRACK_OPTS]
            panel["sequence"] = state.sequence.value if state and state.sequence is not None else -1
        elif descriptor.kind == "AMC2":
            state = self._state(descriptor.primary_tmcc_id)
            panel["motors"] = [self._amc2_reading(key, state, True, i) for i in (1, 2)]
            panel["lights"] = [self._amc2_reading(key, state, False, i) for i in (1, 2, 3, 4)]
        return panel

    @Slot()
    def reload(self) -> None:
        configured_set = ConfiguredAccessorySet.from_file()
        descriptors: list[AccessoryDescriptor] = []
        configured_ids: set[int] = set()

        for configured in configured_set.configured_all():
            descriptor = self._configured_descriptor(configured)
            if descriptor is None:
                continue
            descriptors.append(descriptor)
            configured_ids.update(descriptor.tmcc_ids)

        states = {
            int(state.tmcc_id): state
            for state in ComponentStateStore.get().get_all(CommandScope.ACC)
            if isinstance(state, AccessoryState)
        }
        accessory_ports = {
            tmcc_id
            for device in occupants(scope=CommandScope.ACC)
            if device.device.label in _DEVICE_IMAGES
            for tmcc_id in range(device.base_id, min(device.last_id, 98) + 1)
        }
        # Latching ASC2 switch configuration can be filed under ACC on the PDI bus.
        switch_ports = {
            tmcc_id
            for device in occupants(scope=CommandScope.SWITCH)
            if device.scope == CommandScope.ACC
            for tmcc_id in range(device.base_id, device.last_id + 1)
        }
        for tmcc_id in sorted(states.keys() | accessory_ports):
            state = states.get(tmcc_id)
            if state is not None and state.is_deleted:
                state = None
            labels = tuple(label for label in self._lcs_labels((tmcc_id,)) if label.split(" ", 1)[0] in _DEVICE_IMAGES)
            if labels:
                descriptors.extend(self._base_descriptor(tmcc_id, state, (label,)) for label in labels)
            elif (
                state is not None
                and tmcc_id not in switch_ports
                and tmcc_id not in configured_ids
                and not state.is_sensor_track
            ):
                descriptors.append(self._base_descriptor(tmcc_id, state, ()))

        # Sensor behavior is in IRDA scope; editable identity belongs to the ACC record.
        for state in ComponentStateStore.get().get_all(CommandScope.IRDA):
            if not isinstance(state, IrdaState) or state.is_deleted:
                continue
            tmcc_id = state.tmcc_id
            accessory_state = self._state(tmcc_id)
            name, road_number = self._identity(accessory_state)
            if not name or name in {"Acc", "NA"}:
                name = "Sensor Track"
            descriptors.append(
                AccessoryDescriptor(
                    key=f"irda:{tmcc_id}",
                    tmcc_ids=(tmcc_id,),
                    primary_tmcc_id=tmcc_id,
                    name=name,
                    road_number=road_number,
                    configured_accessory=None,
                    lcs_labels=(f"Sensor Track {tmcc_id}",),
                    available_views=(AccessoryViewKind.LCS,),
                    preferred_view=AccessoryViewKind.LCS,
                    user_defined=bool(accessory_state and accessory_state.is_user_defined),
                )
            )

        descriptors.sort(key=lambda item: (item.name.lower(), item.primary_tmcc_id))
        self._descriptors = {descriptor.key: descriptor for descriptor in descriptors}
        self._rows = [descriptor.as_row() for descriptor in self._descriptors.values()]
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
        return self._rows
