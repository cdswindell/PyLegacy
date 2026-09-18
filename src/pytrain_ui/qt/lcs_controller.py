"""Qt-facing controller for LCS module configuration."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from pytrain.utils.path_utils import find_file

from pytrain.gui.controller.lcs_config_panel import SCOPE_LABEL
from pytrain.gui.controller.lcs_device_registry import (
    MAX_TMCC_ID,
    SENSOR_TRACK_ACTION,
    configurable_devices,
    enabled_modes,
    programmed_options,
)
from pytrain.gui.controller.lcs_sequence_builder import build_program
from pytrain.gui.controller.lcs_id_map import occupants, occupants_of, overlaps, train_overlaps, trains_of


class LcsConfigController(QObject):
    """Expose the toolkit-neutral LCS registry to Qt Quick."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._device_key = ""
        self._mode_key = ""
        self._base_id = 1
        self._options: dict[str, object] = {}

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
    def deviceImage(self) -> str:
        images = {
            "amc2": "LCS-AMC2-6-81641.jpg",
            "asc2": "LCS-ASC2-6-81639.jpg",
            "bpc2": "LCS-BPC2-6-81640.jpg",
            "sensor_track": "LCS-Sensor-Track-6-81294.jpg",
        }
        filename = images.get(self._device_key)
        if not filename:
            return ""
        path = find_file(filename)
        return QUrl.fromLocalFile(str(path)).toString() if path else ""

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
    def options(self) -> list[dict]:
        device = self._device()
        mode = self._mode()
        if device is None or mode is None:
            return []
        rows = []
        for option in programmed_options(device, mode):
            choices = [
                {"index": index, "label": label, "selected": self._options.get(option.key, option.default) == value}
                for index, (label, value) in enumerate(option.choices)
            ]
            rows.append(
                {
                    "key": option.key,
                    "label": option.label,
                    "kind": option.kind.name,
                    "checked": bool(self._options.get(option.key, option.default)),
                    "choices": choices,
                    "note": option.note or "",
                }
            )
        return rows

    def _reported_occupant(self):
        device = self._device()
        mode = self._mode()
        if device is None or mode is None:
            return None
        return next(
            (
                item
                for item in occupants_of(self._base_id, scope=mode.scope)
                if item.device is device and item.base_id == self._base_id
            ),
            None,
        )

    def _load_reported_options(self) -> None:
        device = self._device()
        mode = self._mode()
        occupant = self._reported_occupant()
        self._options = {}
        if device is None or mode is None or occupant is None:
            return
        for option in programmed_options(device, mode):
            value = option.reported_by(occupant.config)
            if value is not None:
                self._options[option.key] = value

    @Property("QVariantList", notify=changed)
    def currentConfiguration(self) -> list[str]:
        """Describe the reported configuration at the address being edited."""
        occupant = self._reported_occupant()
        if occupant is None:
            return ["No matching configured module reported at this address."]
        scope = SCOPE_LABEL.get(occupant.effective_scope, occupant.effective_scope.name)
        mode = occupant.mode
        rows = [
            f"Module: {occupant.device.label}",
            f"TMCC ID: {occupant.base_id}",
            f"Scope: {scope}",
            f"Mode: {mode.name if mode is not None else scope}",
        ]
        device = self._device()
        selected_mode = self._mode()
        if device is not None and selected_mode is not None:
            for option in programmed_options(device, selected_mode):
                value = option.reported_by(occupant.config)
                if value is None:
                    continue
                if option.kind.name == "CHECKBOX":
                    display = "On" if bool(value) else "Off"
                else:
                    display = next((label for label, choice in option.choices if choice == value), str(value))
                rows.append(f"{option.label}: {display}")
        return rows

    @Property("QVariantList", notify=changed)
    def review(self) -> list[str]:
        device = self._device()
        mode = self._mode()
        if device is None or mode is None:
            return []
        try:
            return build_program(device, mode, self._base_id, self._options).display
        except ValueError:
            return []

    @Property(str, notify=changed)
    def programInstruction(self) -> str:
        device = self._device()
        mode = self._mode()
        if device is None or mode is None:
            return ""
        try:
            return build_program(device, mode, self._base_id, self._options).program_instruction
        except ValueError:
            return ""

    @Slot(str, int)
    def selectOption(self, key: str, index: int) -> None:
        device = self._device()
        if device is None:
            return
        try:
            option = device.option(key)
        except ValueError:
            return
        if not 0 <= index < len(option.choices):
            return
        self._options[key] = option.choices[index][1]
        self.changed.emit()

    @Slot(str, bool)
    def setOptionChecked(self, key: str, checked: bool) -> None:
        self._options[key] = checked
        self.changed.emit()

    @Slot(result=str)
    def configure(self) -> str:
        device = self._device()
        mode = self._mode()
        if device is None or mode is None:
            return "Select a module and mode first."
        try:
            program = build_program(device, mode, self._base_id, self._options)
        except ValueError as exc:
            return str(exc)
        for request in program.presses:
            request.send()
        for request in program.verify:
            request.send()
        return ""

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
        assigned = {
            (occupant.device.key, occupant.base_id, occupant.last_id, occupant.effective_scope)
            for occupant in occupants_of(self._base_id, scope=mode.scope)
        }
        for occupant in overlaps(self._base_id, mode.ports, scope=mode.scope):
            identity = (occupant.device.key, occupant.base_id, occupant.last_id, occupant.effective_scope)
            if identity in assigned:
                continue
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
        self._load_reported_options()
        self.changed.emit()

    @Slot(int)
    def setBaseId(self, value: int) -> None:
        mode = self._mode()
        maximum = mode.max_base if mode is not None else MAX_TMCC_ID
        value = min(max(int(value), 1), maximum)
        if value != self._base_id:
            self._base_id = value
            self._load_reported_options()
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
        self._load_reported_options()
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
        self._options = {}
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
        self._options = {}
        self.changed.emit()
