"""Qt-facing controller for LCS module configuration."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.gui.controller.lcs_device_registry import configurable_devices, enabled_modes


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

    @Slot(str)
    def selectDevice(self, key: str) -> None:
        if key == self._device_key:
            return
        if key and key not in {device.key for device in configurable_devices()}:
            return
        self._device_key = key
        self.changed.emit()

    @Slot()
    def reset(self) -> None:
        self._device_key = ""
        self.changed.emit()
