"""Qt-facing controller for LCS module configuration."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.gui.controller.lcs_config_panel import SCOPE_LABEL
from pytrain.gui.controller.lcs_device_registry import (
    MAX_TMCC_ID,
    SENSOR_TRACK_ACTION,
    configurable_devices,
    enabled_modes,
)
from pytrain.gui.controller.lcs_id_map import occupants, occupants_of, overlaps, train_overlaps, trains_of


class LcsConfigController(QObject):
    """Expose the toolkit-neutral LCS registry to Qt Quick."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._device_key = ""
        self._mode_key = ""
        self._base_id = 1

    @Property("QVariantList", notify=changed)
    def devices(self) -> list[dict]:
        return [
            {
                "key": device.key,
                "label": device.label,
                "blurb": device.blurb,
                "warning": device.warning or "",
                "modes": [
                    {
                        "key": mode.key,
                        "name": mode.name,
                        "scope": mode.scope.name,
                        "ports": mode.ports,
                        "note": mode.note or "",
                    }
                    for mode in enabled_modes(device)
                ],
            }
            for device in configurable_devices()
        ]

    @Property(str, notify=changed)
    def deviceKey(self) -> str:
        return self._device_key

    def _device(self):
        return next((device for device in configurable_devices() if device.key == self._device_key), None)

    def _mode(self):
        device = self._device()
        if device is None:
            return None
        modes = enabled_modes(device)
        return next((mode for mode in modes if mode.key == self._mode_key), modes[0] if modes else None)

    @Property(str, notify=changed)
    def deviceLabel(self) -> str:
        device = self._device()
        return device.label if device is not None else ""

    @Property(str, notify=changed)
    def modeKey(self) -> str:
        mode = self._mode()
        return mode.key if mode is not None else ""

    @Property(int, notify=changed)
    def baseId(self) -> int:
        return self._base_id

    @Property("QVariantList", notify=changed)
    def modes(self) -> list[dict]:
        device = self._device()
        if device is None:
            return []
        return [
            {
                "key": mode.key,
                "name": mode.name,
                "scope": SCOPE_LABEL.get(mode.scope, mode.scope.name),
                "ports": mode.ports,
                "maxBase": mode.max_base,
                "idsLabel": mode.ids_label(min(self._base_id, mode.max_base)),
                "note": mode.note or "",
            }
            for mode in enabled_modes(device)
        ]

    @Property("QVariantList", notify=changed)
    def assignments(self) -> list[dict]:
        mode = self._mode()
        if mode is None:
            return []
        rows = []
        for occupant in occupants_of(self._base_id, scope=mode.scope):
            rows.append(
                {
                    "text": (
                        f"{occupant.device.label} {SCOPE_LABEL.get(occupant.effective_scope, '')} "
                        f"{occupant.base_id} - {occupant.last_id}"
                    )
                }
            )
        if mode.scope.name == "TRAIN":
            rows.extend({"text": f"Train {train.base_id}: {train.name}"} for train in trains_of(self._base_id))
        return rows

    @Property("QVariantList", notify=changed)
    def conflicts(self) -> list[dict]:
        mode = self._mode()
        if mode is None:
            return []
        rows = []
        for occupant in overlaps(self._base_id, mode.ports, scope=mode.scope):
            rows.append(
                {
                    "text": (
                        f"{occupant.device.label} {SCOPE_LABEL.get(occupant.effective_scope, '')} "
                        f"{occupant.base_id} - {occupant.last_id}"
                    )
                }
            )
        if mode.scope.name == "TRAIN":
            rows.extend(
                {"text": f"Train {train.base_id}: {train.name}"} for train in train_overlaps(self._base_id, mode.ports)
            )
        return rows

    @Slot(str)
    def selectMode(self, key: str) -> None:
        device = self._device()
        if device is None:
            return
        mode = next((item for item in enabled_modes(device) if item.key == key), None)
        if mode is None:
            return
        self._mode_key = mode.key
        self._base_id = min(self._base_id, mode.max_base)
        self.changed.emit()

    @Slot(int)
    def setBaseId(self, value: int) -> None:
        mode = self._mode()
        maximum = mode.max_base if mode is not None else MAX_TMCC_ID
        value = min(max(int(value), 1), maximum)
        if value != self._base_id:
            self._base_id = value
            self.changed.emit()

    @Property("QVariantList", notify=changed)
    def modules(self) -> list[dict]:
        """Return the LCS modules currently reported by the layout."""
        rows = []
        for occupant in occupants():
            mode = occupant.mode
            scope = SCOPE_LABEL.get(occupant.effective_scope, "")
            action = ""
            if occupant.device.key == "sensor_track":
                value = SENSOR_TRACK_ACTION.reported_by(occupant.config)
                if value is not None:
                    action = next(
                        (label for label, choice in SENSOR_TRACK_ACTION.choices if choice == value),
                        str(getattr(value, "name", value)),
                    )
            rows.append(
                {
                    "deviceKey": occupant.device.key,
                    "module": "IR" if occupant.device.key == "sensor_track" else occupant.device.label,
                    "tmccId": occupant.base_id,
                    "scope": scope,
                    "mode": mode.name if mode is not None and mode.name != scope else "",
                    "ids": (
                        str(occupant.base_id)
                        if occupant.last_id == occupant.base_id
                        else f"{occupant.base_id} - {occupant.last_id}"
                    ),
                    "action": action,
                }
            )
        return rows

    @Slot(str, int, str)
    def selectConfiguredModule(self, key: str, base_id: int, scope: str) -> None:
        """Load a reported module into the configuration editor."""
        device = next((item for item in configurable_devices() if item.key == key), None)
        if device is None:
            return
        modes = enabled_modes(device)
        mode = next(
            (item for item in modes if SCOPE_LABEL.get(item.scope, item.scope.name) == scope),
            modes[0] if modes else None,
        )
        self._device_key = key
        self._mode_key = mode.key if mode is not None else ""
        maximum = mode.max_base if mode is not None else MAX_TMCC_ID
        self._base_id = min(max(int(base_id), 1), maximum)
        self.changed.emit()

    @Slot(str)
    def selectDevice(self, key: str) -> None:
        if key == self._device_key:
            return
        if key and key not in {device.key for device in configurable_devices()}:
            return
        self._device_key = key
        device = self._device()
        modes = enabled_modes(device) if device is not None else ()
        self._mode_key = modes[0].key if modes else ""
        if modes:
            self._base_id = min(self._base_id, modes[0].max_base)
        self.changed.emit()

    @Slot()
    def refreshModules(self) -> None:
        self.changed.emit()

    @Slot()
    def reset(self) -> None:
        self._device_key = ""
        self._mode_key = ""
        self._base_id = 1
        self.changed.emit()
