"""Qt-facing controller for LCS module configuration."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.gui.controller.lcs_config_panel import SCOPE_LABEL
from pytrain.gui.controller.lcs_device_registry import configurable_devices, enabled_modes
from pytrain.gui.controller.lcs_id_map import occupants


class LcsConfigController(QObject):
    """Expose the toolkit-neutral LCS registry to Qt Quick."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._device_key = ""

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

    @Property("QVariantList", notify=changed)
    def modules(self) -> list[dict]:
        """Return the LCS modules currently reported by the layout."""
        rows = []
        for occupant in sorted(
            occupants(),
            key=lambda item: (
                item.device.label.upper(),
                item.base_id,
                SCOPE_LABEL.get(item.effective_scope, ""),
            ),
        ):
            mode = occupant.mode
            scope = SCOPE_LABEL.get(occupant.effective_scope, "")
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
                }
            )
        return rows

    @Slot(str)
    def selectDevice(self, key: str) -> None:
        if key == self._device_key:
            return
        if key and key not in {device.key for device in configurable_devices()}:
            return
        self._device_key = key
        self.changed.emit()

    @Slot()
    def refreshModules(self) -> None:
        self.changed.emit()

    @Slot()
    def reset(self) -> None:
        self._device_key = ""
        self.changed.emit()
